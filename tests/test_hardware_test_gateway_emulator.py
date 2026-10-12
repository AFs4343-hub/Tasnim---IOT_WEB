"""Signed device -> RTDB emulator -> V2 prototype AI integration tests.

This is an isolated demo project. No HTTP gateway, TLS server, firmware,
production database, or secret-account key is used.
"""
import os
import unittest

import firebase_admin
from firebase_admin import db

from ai.hardware_test_analysis_writer_v2 import (
    prepare_analysis_record, commit_verified_analysis,
)
from ai.hardware_test_preview_v2 import preview_pending
from ai.predict import predict_latest
from ai.realtime_inference import load_model
from iot.hardware_test_gateway_auth_v1 import (
    DeviceAuthError, NonceConflict, accept_signed_measurement,
)
from test_hardware_test_gateway_auth_v1 import KEYS, signed
from test_hardware_test_ingestion_core import sample, TS

HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
NOW = TS + 3_600_000
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"


class AppDatabase:
    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


class FailLatestOnce:
    def __init__(self, inner):
        self.inner = inner
        self.failed = False

    def reference(self, path):
        if path == "hardware_test/nodes/N0/latest" and not self.failed:
            parent = self

            class Fault:
                def transaction(self, callback):
                    parent.failed = True
                    raise ConnectionError("injected failure after nonce and history")

            return Fault()
        return self.inner.reference(path)


class SignedGatewayEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST:
            raise RuntimeError("REFUSED: Firebase emulator host mismatch")
        if os.getenv("GCLOUD_PROJECT") != PROJECT:
            raise RuntimeError("REFUSED: demo project mismatch")
        cls.app = firebase_admin.initialize_app(
            options={"databaseURL": URL, "projectId": PROJECT, "httpTimeout": 15},
            name="tasnim-signed-gateway-emulator",
        )
        cls.adapter = AppDatabase(cls.app)
        print("\n[SAFE] Signed gateway candidate on localhost demo emulator only")

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference("hardware_test", app=self.app).delete()
        db.reference("gateway_state", app=self.app).delete()

    def receive(self, packet, *, nonce="gatewaynonce00000001", adapter=None,
                node=None, secret=None, request_time=NOW):
        body, headers = signed(
            packet, nonce=nonce, node=node, secret=secret, stamp=request_time,
        )
        return accept_signed_measurement(
            adapter or self.adapter, body, headers, KEYS, now_ms=NOW,
        )

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def test_01_valid_signed_packet_persists(self):
        result = self.receive(sample())
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")
        self.assertEqual(self.read("hardware_test/nodes/N0/latest")["ph"], 7.2)

    def test_02_identical_retry_does_not_duplicate(self):
        packet = sample()
        self.receive(packet)
        self.receive(packet)
        self.assertEqual(len(self.read("gateway_state/nonces/N0")), 1)

    def test_03_nonce_reuse_different_signed_body_denied(self):
        self.receive(sample())
        with self.assertRaises(NonceConflict):
            self.receive(sample(ph=8.3))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest")["ph"], 7.2)

    def test_04_wrong_node_secret_rejected(self):
        with self.assertRaises(DeviceAuthError):
            self.receive(sample(), secret=KEYS["N1"])
        self.assertIsNone(self.read("gateway_state"))

    def test_05_partial_failure_recovers_same_signed_request(self):
        packet = sample()
        faulty = FailLatestOnce(self.adapter)
        with self.assertRaises(ConnectionError):
            self.receive(packet, adapter=faulty)
        self.assertIsNone(self.read("hardware_test/nodes/N0/latest"))
        self.receive(packet)
        self.assertEqual(self.read("hardware_test/nodes/N0/latest")["ph"], 7.2)

    def test_06_old_measurement_fresh_request_preserves_latest(self):
        newer = sample(ts=TS+300_000, seq=5)
        older = sample(ts=TS, seq=3)
        self.receive(newer, nonce="gatewaynonce00000002")
        result = self.receive(older, nonce="gatewaynonce00000003")
        self.assertEqual(result["latest"], "OLDER_REPLAY_PRESERVED")
        self.assertEqual(self.read("hardware_test/nodes/N0/latest")["timestamp"],
                         newer["timestamp"])

    def test_07_three_nodes_are_isolated(self):
        for node in ("N0", "N1", "N2"):
            self.receive(sample(node=node), nonce=f"gatewaynonce{node}00001")
        slot = (TS // 300_000) * 300_000
        self.assertEqual(set(self.read(f"hardware_test/history/{slot}")),
                         {"N0", "N1", "N2"})

    def test_08_real_model_e2e_gateway_ingestion_to_analysis(self):
        """Full prototype path: signed input -> stored history -> AI -> analysis."""
        for tick in range(3):
            for index, node in enumerate(("N0", "N1", "N2")):
                packet = sample(node=node, ts=TS + tick*300_000,
                                seq=tick+1,
                                ph=7.1+index*.12+tick*.01,
                                tds=180+index*20+tick*.5,
                                turbidity=9+index*1.1+tick*.15)
                self.receive(packet, nonce=f"gatewaynonce{node}{tick:04d}XYZ")

        all_history = self.read("hardware_test/history")
        self.assertEqual(len(all_history), 3)
        preview = preview_pending(
            all_history, session_id="DEMO_E2E_SESSION",
            model_bundle=load_model(), predict_fn=predict_latest,
        )
        self.assertEqual(len(preview["predictions"]), 2)
        slots = sorted(int(value) for value in preview["predictions"])
        for index, slot in enumerate(slots):
            record = prepare_analysis_record(
                preview["predictions"][str(slot)], model_version="prototype-v1",
                inference_timestamp_ms=NOW + index,
            )
            result = commit_verified_analysis(self.adapter, record)
            self.assertEqual(result["history"], "CONFIRMED")
            self.assertEqual(record["model_stage"], "PROTOTYPE_SIMULATION")
        latest = self.read("hardware_test/analysis/latest")
        self.assertEqual(latest["source_timestamp_ms"], slots[-1])
        self.assertEqual(set(self.read(f"hardware_test/history/{slots[-1]}")),
                         {"N0", "N1", "N2", "analysis"})
        self.assertIsNone(self.read("hardware_test/history/0"))


if __name__ == "__main__":
    unittest.main()
