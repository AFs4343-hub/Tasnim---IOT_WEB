"""The CI evidence must be scoped, redact-free and always LIVE blocked."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/generate_candidate_release_evidence.py"


class CandidateReleaseEvidenceTests(unittest.TestCase):
    def test_offline_and_emulator_reports_never_claim_live_approval(self):
        for scope in ("offline", "emulator"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as td:
                dest = Path(td) / "report.json"
                env = {**os.environ, "GITHUB_SHA": "TEST_ONLY_REVISION"}
                p = subprocess.run(
                    [sys.executable, str(TOOL), "--scope", scope,
                     "--output", str(dest)],
                    cwd=ROOT, env=env, capture_output=True, text=True,
                    timeout=10,
                )
                self.assertEqual(p.returncode, 0, p.stderr)
                evidence = json.loads(dest.read_text())
                self.assertEqual(evidence["release_decision"], "LIVE_DEPLOYMENT_BLOCKED")
                self.assertEqual(evidence["scope"], scope)
                self.assertEqual(evidence["revision"], "TEST_ONLY_REVISION")
                self.assertEqual(evidence["frozen_production_files_checked"], 4)
                self.assertFalse(evidence["real_field_accuracy_verified"])
                self.assertEqual(evidence["firmware_stage"], "LAST_STAGE_NOT_INTEGRATED")
                self.assertNotIn("password", json.dumps(evidence).lower())
                # Never overwrite existing operator reports.
                second = subprocess.run(
                    [sys.executable, str(TOOL), "--scope", scope,
                     "--output", str(dest)],
                    cwd=ROOT, env=env, capture_output=True, text=True,
                    timeout=10,
                )
                self.assertNotEqual(second.returncode, 0)

    def test_unsupported_scope_cannot_produce_an_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "bad.json"
            run = subprocess.run(
                [sys.executable, str(TOOL), "--scope", "production",
                 "--output", str(dest)],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
