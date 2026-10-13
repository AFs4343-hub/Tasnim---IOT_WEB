"""Offline tests for scripts/firebase_project_setup.py pure helpers."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from firebase_project_setup import NEW_WRITE, merge_env_file, tighten_rules  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class SetupHelperTests(unittest.TestCase):
    def test_env_merge_fills_only_missing_and_keeps_other_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env.local"
            env.write_text("# keep\nVITE_FIREBASE_API_KEY=mine\nVITE_FIREBASE_DATABASE_URL=\nOTHER=1\n")
            filled = merge_env_file(env, {"apiKey": "theirs", "databaseURL": "https://db",
                                          "projectId": "p", "appId": ""})
            text = env.read_text()
        self.assertEqual(filled, ["VITE_FIREBASE_DATABASE_URL", "VITE_FIREBASE_PROJECT_ID"])
        self.assertIn("VITE_FIREBASE_API_KEY=mine", text)
        self.assertIn("VITE_FIREBASE_DATABASE_URL=https://db", text)
        self.assertIn("# keep", text)
        self.assertIn("OTHER=1", text)
        self.assertNotIn("VITE_FIREBASE_APP_ID", text)

    def test_rules_tightening_matches_candidate_and_is_idempotent(self):
        live = (ROOT / "database.rules.json").read_text()
        status, new = tighten_rules(live)
        self.assertEqual(status, "CHANGED")
        candidate = json.loads((ROOT / "database.rules.web-anonymous-read.candidate.json").read_text())
        self.assertEqual(json.loads(new), candidate)
        self.assertEqual(tighten_rules(new)[0], "ALREADY")

    def test_unexpected_live_rules_are_never_rewritten(self):
        for text in ('{"rules": {"hardware_test": {".read": true, ".write": "auth != null"}}}',
                     '{"rules": {}}', '// comment\n{"rules": {}}', '[]'):
            status, new = tighten_rules(text)
            self.assertEqual(status, "UNEXPECTED")
            self.assertEqual(new, text)
        self.assertIn("anonymous", NEW_WRITE)


if __name__ == "__main__":
    unittest.main()
