"""Real RTDB Emulator acceptance: existing latest -> archived history slots.

Only local demo project. This test does not touch production Firebase or
change any original latest records.
"""
import copy
import os
import unittest
from unittest.mock import patch

import firebase_admin
from firebase_admin import db

from iot.hardware_test_legacy_history_capture_v1 import capture_latest_as_history
from test_field_legacy_history_capture_v1 import LATEST, NOW

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


class FieldLatestCaptureEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.getenv("GCLOUD_PROJECT") != PROJECT
                or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST
                or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
            raise RuntimeError("REFUSED: only localhost test Emulator")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-legacy-history-emulator-test",
        )
        cls.adapter = EmulatorAdapter(cls.app)

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def test_three_real_format_latest_are_captured_only_once_and_preserved(self):
        root = db.reference("hardware_test", app=self.app)
        root.delete()
        try:
            latest = {node: {"latest": sample} for node, sample in LATEST.items()}
            db.reference("hardware_test/nodes", app=self.app).set(latest)
            with patch.dict(os.environ, {"TASNIM_FIELD_HISTORY_EMULATOR_ONLY": "YES"}):
                dry = capture_latest_as_history(self.adapter, now_ms=NOW)
                self.assertTrue(dry["dry_run"])
                self.assertIsNone(db.reference("hardware_test/history", app=self.app).get())
                saved = capture_latest_as_history(self.adapter, now_ms=NOW, dry_run=False)
                self.assertEqual(saved["nodes"], dict.fromkeys(LATEST, "CAPTURED"))
                before = root.get()
                self.assertEqual(before["nodes"], latest)
                replay = capture_latest_as_history(self.adapter, now_ms=NOW, dry_run=False)
                self.assertEqual(replay["nodes"], saved["nodes"])
                self.assertEqual(root.get(), before)
                for node, measurement in LATEST.items():
                    slot = measurement["timestamp"] // 300000 * 300000
                    archive = db.reference(f"hardware_test/history/{slot}/{node}",
                                           app=self.app).get()
                    self.assertEqual(archive["timestamp"], measurement["timestamp"])
                    self.assertEqual(archive["schema_version"], 2)
                    if node == "N1":
                        self.assertNotIn("ph", archive)
                        self.assertIn("PH_INVALID", archive["quality_flags"])
        finally:
            root.delete()


if __name__ == "__main__":
    unittest.main()
