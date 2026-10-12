"""Isolated synthetic backup/restore drill on localhost RTDB Emulator only.

Touches ONLY /__tasnim_candidate_restore_drill_v1, never the real
/hardware_test or /gateway_state roots. Not a production backup service.
"""
import copy
import os
import unittest

import firebase_admin
from firebase_admin import db

from iot.hardware_test_backup_rehearsal_v1 import (
    prepare_synthetic_backup, rehearse_synthetic_restore,
    DemoRestoreReviewRequired,
)
from test_hardware_test_history_v2 import SLOT0, slot

PROJECT = "demo-tasnim-security"
HOST = "127.0.0.1:19003"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"
ROOT = "__tasnim_candidate_restore_drill_v1"


class DemoBackupRestoreEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            os.getenv("GCLOUD_PROJECT") != PROJECT
            or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        ):
            raise RuntimeError("REFUSED: demo restore drill requires localhost Emulator")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-restore-drill-demo",
        )

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def test_sandbox_snapshot_restore_and_detect_tamper(self):
        base = db.reference(ROOT, app=self.app)
        # Only test-owned namespace; never delete real hardware_test.
        base.delete()
        try:
            synthetic = {"history": {str(SLOT0): slot(SLOT0)}}
            base.child("original").set(synthetic)
            readback = base.child("original").get()
            envelope = prepare_synthetic_backup(readback)
            restored = rehearse_synthetic_restore(envelope)
            self.assertEqual(restored, readback)

            damaged = copy.deepcopy(envelope)
            damaged["hardware_test"]["history"][str(SLOT0)]["N1"]["ph"] = -49
            with self.assertRaises(DemoRestoreReviewRequired):
                rehearse_synthetic_restore(damaged)
            self.assertIsNone(base.child("restored").get())

            base.child("restored").set(restored)
            self.assertEqual(base.child("restored").get(), readback)
            self.assertEqual(base.child("original").get(), readback)
        finally:
            base.delete()


if __name__ == "__main__":
    unittest.main()
