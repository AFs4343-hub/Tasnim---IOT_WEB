"""AI run-once worker integration tests on localhost RTDB Emulator ONLY."""
import os
import unittest
from unittest.mock import patch

import firebase_admin
from firebase_admin import db

from ai.hardware_test_worker_v2 import (
    WorkerReviewRequired, run_emulator_cycle,
)
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot
from test_hardware_test_worker_v2 import prediction

HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"


class Adapter:
    emulator_only = True
    emulator_host = HOST
    emulator_project = PROJECT

    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


class FailLatestOnce:
    emulator_only = True
    emulator_host = HOST
    emulator_project = PROJECT

    def __init__(self, adapter):
        self.adapter = adapter
        self.failed = False

    def reference(self, path):
        if path == "hardware_test/analysis/latest" and not self.failed:
            parent = self

            class BrokenTransaction:
                def transaction(self, update):
                    parent.failed = True
                    raise ConnectionError("injected failure after history commit")

            return BrokenTransaction()
        return self.adapter.reference(path)


class RealWorkerEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST:
            raise RuntimeError("REFUSED: localhost emulator required")
        if os.getenv("GCLOUD_PROJECT") != PROJECT:
            raise RuntimeError("REFUSED: demo project required")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-v2-worker-demo-tests",
        )
        cls.adapter = Adapter(cls.app)

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference("hardware_test", app=self.app).delete()
        self.history = {
            str(SLOT0+i*INTERVAL): slot(SLOT0+i*INTERVAL)
            for i in range(3)
        }
        db.reference("hardware_test/history", app=self.app).set(self.history)

    def cycle(self, adapter=None, predict=prediction):
        with patch.dict(os.environ, {"TASNIM_AI_WORKER_EMULATOR_ONLY": "YES"}):
            return run_emulator_cycle(
                adapter or self.adapter,
                session_id="DEMO_WORKER_SESSION",
                model_version="prototype-v1",
                model_bundle=None, predict_fn=predict,
                now_ms=SLOT0+10*INTERVAL,
            )

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def test_01_archive_latest_restart(self):
        first = self.cycle()
        self.assertEqual(first["processed_slots"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        prior = self.read(f"hardware_test/history/{SLOT0+INTERVAL}/analysis")
        self.assertEqual(len(prior["source_digest_sha256"]), 64)
        self.assertEqual(self.read("hardware_test/analysis/latest")["source_timestamp_ms"],
                         SLOT0+2*INTERVAL)
        second = self.cycle(predict=lambda frame, bundle: self.fail("duplicate inference"))
        self.assertEqual(second["processed_slots"], [])
        self.assertEqual(self.read(f"hardware_test/history/{SLOT0+INTERVAL}/analysis"), prior)

    def test_02_partial_history_latest_write_recovers_after_restart(self):
        broken = FailLatestOnce(self.adapter)
        with self.assertRaises(ConnectionError):
            self.cycle(adapter=broken)
        key = f"hardware_test/history/{SLOT0+INTERVAL}/analysis"
        stored = self.read(key)
        self.assertIsNotNone(stored)
        self.assertIsNone(self.read("hardware_test/analysis/latest"))
        second = self.cycle()
        self.assertEqual(second["recovered_slots"], [SLOT0+INTERVAL])
        self.assertEqual(second["processed_slots"], [SLOT0+2*INTERVAL])
        self.assertEqual(self.read(key), stored)

    def test_03_late_backfill_stops_stale_checkpoints(self):
        db.reference(f"hardware_test/history/{SLOT0+INTERVAL}", app=self.app).delete()
        db.reference(f"hardware_test/history/{SLOT0+3*INTERVAL}", app=self.app).set(
            slot(SLOT0+3*INTERVAL)
        )
        self.cycle()
        db.reference(f"hardware_test/history/{SLOT0+INTERVAL}", app=self.app).set(
            slot(SLOT0+INTERVAL)
        )
        with self.assertRaises(WorkerReviewRequired):
            self.cycle()


if __name__ == "__main__":
    unittest.main()
