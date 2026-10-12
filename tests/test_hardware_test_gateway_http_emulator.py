"""HTTP -> signed verifier -> real demo RTDB emulator integration.

No public listener, real credentials, production URL, or firmware.
"""
import json
import os
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import firebase_admin
from firebase_admin import db

from iot.hardware_test_gateway_http_v1 import create_demo_server
from test_hardware_test_gateway_auth_v1 import KEYS, NOW, signed
from test_hardware_test_ingestion_core import sample, TS

HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"


class RealHTTPGatewayEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("FIREBASE_DATABASE_EMULATOR_HOST") != HOST:
            raise RuntimeError("REFUSED: localhost emulator required")
        if os.environ.get("GCLOUD_PROJECT") != PROJECT:
            raise RuntimeError("REFUSED: demo project required")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 10},
            name="tasnim-http-integration-demo",
        )

        class Adapter:
            def reference(self, path):
                return db.reference(path, app=cls.app)

        cls.server = create_demo_server(Adapter(), KEYS, port=0,
                                        clock_ms=lambda: NOW)
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference("hardware_test", app=self.app).delete()
        db.reference("gateway_state", app=self.app).delete()

    def receive(self, packet, *, node=None, nonce="emulatorhttpnonce00001",
                secret=None):
        body, headers = signed(packet, node=node, nonce=nonce,
                               stamp=NOW, secret=secret)
        req = Request(self.base + "/v1/measurements", data=body,
                      headers=headers, method="POST")
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def test_01_signed_post_persists_both_paths(self):
        packet = sample()
        status, ack = self.receive(packet)
        self.assertEqual((status, ack["code"]),
                         (200, "HISTORY_AND_LATEST_CONFIRMED"))
        slot = (TS // 300_000) * 300_000
        self.assertEqual(self.read(f"hardware_test/history/{slot}/N0")["ph"], 7.2)
        self.assertEqual(self.read("hardware_test/nodes/N0/latest")["ph"], 7.2)

    def test_02_identical_http_retry_is_safe(self):
        packet = sample()
        first = self.receive(packet)
        second = self.receive(packet)
        self.assertEqual(first, second)
        self.assertEqual(len(self.read("gateway_state/nonces/N0")), 1)

    def test_03_changed_slot_record_is_conflict(self):
        self.assertEqual(self.receive(sample())[0], 200)
        status, ack = self.receive(sample(ph=8.1),
                                   nonce="emulatorhttpnonce00002")
        self.assertEqual((status, ack["code"]),
                         (409, "CONFLICT_REVIEW_REQUIRED"))

    def test_04_other_node_secret_is_unauthorized(self):
        status, ack = self.receive(sample(), secret=KEYS["N1"])
        self.assertEqual((status, ack["code"]), (401, "UNAUTHORIZED"))
        self.assertIsNone(self.read("gateway_state"))

    def test_05_three_devices_share_history_slot(self):
        for node in ("N0", "N1", "N2"):
            status, _ = self.receive(sample(node=node),
                                     nonce=f"emulatorhttpnonce{node}001")
            self.assertEqual(status, 200)
        slot = (TS // 300_000) * 300_000
        self.assertEqual(
            set(self.read(f"hardware_test/history/{slot}")),
            {"N0", "N1", "N2"},
        )


if __name__ == "__main__":
    unittest.main()
