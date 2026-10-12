"""Real RTDB Emulator coverage for the opt-in cooperative worker lock."""
import os
import unittest
from unittest.mock import patch

import firebase_admin
from firebase_admin import db

from ai.hardware_test_worker_lease_v2 import (
    LEASE_PATH, WorkerLeaseBusy, WorkerLeaseOwnershipLost,
    acquire_exclusive_emulator_lock, release_exclusive_emulator_lock,
    run_exclusive_emulator_cycle,
)
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot
from test_hardware_test_worker_v2 import prediction

PROJECT = "demo-tasnim-security"
HOST = "127.0.0.1:19003"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"


class EmulatorAdapter:
    emulator_only = True
    emulator_project = PROJECT
    emulator_host = HOST

    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


class ExclusiveWorkerDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST
                or os.getenv("GCLOUD_PROJECT") != PROJECT):
            raise RuntimeError("REFUSED: localhost demo RTDB Emulator only")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-worker-lock-demo-tests",
        )
        cls.adapter = EmulatorAdapter(cls.app)

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference(LEASE_PATH, app=self.app).delete()
        db.reference("hardware_test", app=self.app).delete()
        db.reference("hardware_test/history", app=self.app).set({
            str(SLOT0 + i*INTERVAL): slot(SLOT0 + i*INTERVAL)
            for i in range(3)
        })
        p = patch.dict(os.environ, {
            "TASNIM_AI_WORKER_EMULATOR_ONLY": "YES",
            "TASNIM_AI_COORDINATION_EMULATOR_ONLY": "YES",
        })
        p.start()
        self.addCleanup(p.stop)

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def cycle(self, **extra):
        predictor = extra.pop("predict_fn", prediction)
        return run_exclusive_emulator_cycle(
            self.adapter, session_id="EXCLUSIVE_EMULATOR_SESSION",
            model_version="prototype-v1", model_bundle=None,
            predict_fn=predictor, now_ms=SLOT0+10*INTERVAL, **extra,
        )

    def test_second_worker_is_blocked_until_owner_releases(self):
        first = acquire_exclusive_emulator_lock(self.adapter)
        existing = self.read(LEASE_PATH)
        with self.assertRaises(WorkerLeaseBusy):
            acquire_exclusive_emulator_lock(self.adapter)
        self.assertEqual(self.read(LEASE_PATH), existing)
        with self.assertRaises(WorkerLeaseOwnershipLost):
            release_exclusive_emulator_lock(self.adapter, owner_id="0"*32)
        self.assertEqual(self.read(LEASE_PATH), existing)
        release_exclusive_emulator_lock(self.adapter, owner_id=first)
        self.assertIsNone(self.read(LEASE_PATH))
        result = self.cycle()
        self.assertEqual(result["processed_slots"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertIsNone(self.read(LEASE_PATH))
        self.assertIsNotNone(self.read("hardware_test/analysis/latest"))

    def test_dry_run_does_not_even_create_a_lock(self):
        result = self.cycle(
            dry_run=True,
            predict_fn=lambda frame, bundle: self.fail("unexpected prediction"),
        )
        self.assertEqual(result["would_process_slots"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertIsNone(self.read(LEASE_PATH))
        self.assertIsNone(self.read("hardware_test/analysis/latest"))

    def test_exception_releases_owned_lock_but_never_infers(self):
        with self.assertRaisesRegex(ValueError, "synthetic prediction failure"):
            self.cycle(predict_fn=lambda frame, bundle: (
                _ for _ in ()
            ).throw(ValueError("synthetic prediction failure")))
        self.assertIsNone(self.read(LEASE_PATH))
        self.assertIsNone(self.read("hardware_test/analysis/latest"))


if __name__ == "__main__":
    unittest.main()
