"""AI run-once worker integration tests on localhost RTDB Emulator ONLY."""
import os
import unittest
from unittest.mock import patch

import firebase_admin
from firebase_admin import db

from ai.hardware_test_worker_v2 import (
    WorkerReviewRequired, run_emulator_cycle,
)
from ai.hardware_test_checkpoint_integrity_v1 import (
    CheckpointIntegrityReviewRequired, inspect_demo_checkpoints,
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
                def get(self):
                    # Worker V2 first reads latest to check its checkpoint.
                    # Only the subsequent transaction is fault-injected.
                    return parent.adapter.reference(path).get()

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

    def test_05_read_only_integrity_audit_confirms_archived_model_provenance(self):
        self.cycle()
        with patch.dict(os.environ, {"TASNIM_AI_WORKER_EMULATOR_ONLY": "YES"}):
            outcome = inspect_demo_checkpoints(
                self.adapter, session_id="DEMO_WORKER_SESSION",
                model_version="prototype-v1",
            )
        self.assertEqual(outcome["state"], "ALIGNED")
        self.assertEqual(outcome["archived_count"], 2)
        self.assertTrue(outcome["read_only"])
        self.assertEqual(
            self.read("hardware_test/analysis/latest")["source_timestamp_ms"],
            SLOT0 + 2*INTERVAL,
        )

    def test_06_read_only_integrity_audit_detects_late_backfill(self):
        db.reference(f"hardware_test/history/{SLOT0+INTERVAL}", app=self.app).delete()
        db.reference(f"hardware_test/history/{SLOT0+3*INTERVAL}", app=self.app).set(
            slot(SLOT0+3*INTERVAL)
        )
        self.cycle()
        db.reference(f"hardware_test/history/{SLOT0+INTERVAL}", app=self.app).set(
            slot(SLOT0+INTERVAL)
        )
        before = self.read("hardware_test/analysis/latest")
        with patch.dict(os.environ, {"TASNIM_AI_WORKER_EMULATOR_ONLY": "YES"}):
            with self.assertRaises(CheckpointIntegrityReviewRequired):
                inspect_demo_checkpoints(
                    self.adapter, session_id="DEMO_WORKER_SESSION",
                    model_version="prototype-v1",
                )
        self.assertEqual(self.read("hardware_test/analysis/latest"), before)

    def test_04_preview_dry_run_has_no_emulator_writes(self):
        with patch.dict(os.environ, {"TASNIM_AI_WORKER_EMULATOR_ONLY": "YES"}):
            report = run_emulator_cycle(
                self.adapter, session_id="DEMO_WORKER_SESSION",
                model_version="prototype-v1", model_bundle=None,
                predict_fn=lambda frame, bundle: self.fail("dry run predicted"),
                now_ms=SLOT0+10*INTERVAL, dry_run=True,
                max_actions_per_cycle=1,
            )
        self.assertEqual(report["would_process_slots"], [SLOT0+INTERVAL])
        self.assertEqual(report["deferred_slots"], [SLOT0+2*INTERVAL])
        self.assertIsNone(self.read("hardware_test/analysis/latest"))
        self.assertIsNone(self.read(f"hardware_test/history/{SLOT0+INTERVAL}/analysis"))

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
