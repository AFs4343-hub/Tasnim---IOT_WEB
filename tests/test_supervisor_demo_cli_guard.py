"""No-network guard tests for the one-shot *synthetic* demo CLI."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_supervisor_demo_once as cli


class OneShotDemoSafetyTests(unittest.TestCase):
    def test_model_prediction_is_explicitly_synthetic(self):
        class Frame:
            iloc = None
        class Row:
            def __getitem__(self, key):
                return {"session_id": cli.SESSION}[key]
        class Iloc:
            def __getitem__(self, key):
                return Row()
        frame = Frame()
        frame.iloc = Iloc()
        result = cli.predictor(frame, None)
        self.assertEqual(result["status"], "NORMAL")
        self.assertEqual(result["timestamp"], "SYNTHETIC_DEMO_ONLY")
        self.assertEqual(result["session_id"], cli.SESSION)
        self.assertEqual(result["random_forest"]["confidence"], 0.55)

    def test_live_environment_refused_before_database_access(self):
        with patch.dict(os.environ, {
            "GCLOUD_PROJECT": "real-production-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                cli.validate_local_configuration()

    def test_service_account_is_never_accepted(self):
        with patch.dict(os.environ, {
            "GCLOUD_PROJECT": "demo-tasnim-security",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/should-not-be-used.json",
        }):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                cli.validate_local_configuration()

    def test_no_foreign_database_emulator_endpoint(self):
        with patch.dict(os.environ, {
            "GCLOUD_PROJECT": cli.PROJECT,
            "GOOGLE_APPLICATION_CREDENTIALS": "",
            "FIREBASE_DATABASE_EMULATOR_HOST": "example.com:19003",
        }):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                cli.validate_local_configuration()

    def test_no_foreign_branch(self):
        with patch.object(cli, "ROOT", Path("/tmp/something-else")):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                cli.validate_local_configuration()


if __name__ == "__main__":
    unittest.main()
