"""Static release-gate checks, independent of Firebase or models."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CandidateReleaseGateStaticTests(unittest.TestCase):
    def text(self, name):
        return (ROOT / name).read_text()

    def test_emulator_full_stack_runs_after_mutating_isolated_worker_suites(self):
        shell = self.text("scripts/test_hardware_auth_emulator.sh")
        worker = shell.index("test_hardware_test_supervisor_emulator.py")
        backup = shell.index("test_candidate_backup_restore_emulator.py")
        e2e = shell.index("test_full_stack_candidate_emulator.py")
        browser = shell.index("test_full_stack_browser_emulator.mjs")
        self.assertLess(worker, backup)
        self.assertLess(backup, e2e)
        self.assertLess(e2e, browser)
        self.assertIn('TASNIM_AUTH_TEST_EMULATOR_ONLY', shell)
        self.assertIn('127.0.0.1:19003', shell)
        self.assertNotIn("firebase deploy", shell)
        self.assertNotIn("git clean", shell)

    def test_ci_runs_offline_faults_and_uploads_scoped_evidence(self):
        offline = self.text(".github/workflows/tasnim-candidate-offline.yml")
        emulator = self.text(".github/workflows/tasnim-auth-emulator-candidate.yml")
        for token in ("test_gateway_fault_matrix_v1.py",
                      "test_candidate_operations_rehearsal.py",
                      "test_candidate_release_evidence.py",
                      "generate_candidate_release_evidence.py"):
            self.assertIn(token, offline)
        self.assertIn("--scope offline", offline)
        self.assertIn("--scope emulator", emulator)
        for ci in (offline, emulator):
            self.assertIn("check_production_baseline_guard.py", ci)
            self.assertIn("actions/upload-artifact@v4", ci)
            self.assertNotIn("firebase deploy", ci)

    def test_readme_and_release_notes_explicitly_block_live(self):
        for name in ("README.md",
                     "docs/GITHUB_CANDIDATE_RELEASE_GATE_20261012.md",
                     "docs/CANDIDATE_SECURITY_OPERATIONS_RUNBOOK_20261012.md"):
            text = self.text(name)
            self.assertIn("LIVE", text.upper())
            self.assertIn("firmware", text.lower())
        self.assertIn("NOT", self.text("README.md"))

    def test_local_gateway_throttle_is_not_misrepresented_as_public_security(self):
        gateway = self.text("iot/hardware_test_gateway_http_v1.py")
        policy = self.text("iot/gateway_demo_rate_limit_v1.py")
        design = self.text("docs/GATEWAY_PRODUCTION_ARCHITECTURE_DECISION_DRAFT.md")
        self.assertIn('HOST = "127.0.0.1"', gateway)
        self.assertIn("DemoSlidingWindowLimiter()", gateway)
        self.assertIn("DEMO_RATE_LIMITED", gateway)
        self.assertIn("Lock()", policy)
        self.assertIn("target design, not a running service", design)
        self.assertIn("LIVE_DEPLOYMENT_BLOCKED", design)
        self.assertIn("multi-worker protection", design)



if __name__ == "__main__":
    unittest.main()
