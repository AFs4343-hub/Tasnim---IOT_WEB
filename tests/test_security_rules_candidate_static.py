
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "database.hardware_test.v2.candidate.rules.json"

class CandidateSecurityRulesStaticTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(
            RULES.read_text(encoding="utf-8")
        )["rules"]

    def test_root_default_deny(self):
        self.assertIs(self.r[".read"], False)
        self.assertIs(self.r[".write"], False)

    def test_expected_roots_only(self):
        self.assertEqual(
            set(self.r),
            {
                ".read", ".write", "hardware_test",
                "simulation", "real_test", "field"
            }
        )

    def test_explicit_human_roles(self):
        for root in (
            "hardware_test", "simulation",
            "real_test", "field"
        ):
            expr = self.r[root][".read"]
            self.assertIn("auth != null", expr)

            for role in ("admin", "manager", "viewer"):
                self.assertIn(
                    "tasnim_role === '" + role + "'",
                    expr
                )

            self.assertNotEqual(expr, "auth != null")
            self.assertNotEqual(expr, True)

    def test_all_client_writes_denied(self):
        def walk(obj):
            if not isinstance(obj, dict):
                return

            if ".write" in obj:
                self.assertIs(obj[".write"], False)

            for value in obj.values():
                walk(value)

        walk(self.r)

    def test_no_subtree_permissions(self):
        for root in (
            "hardware_test", "simulation",
            "real_test", "field"
        ):
            self.assertEqual(
                set(self.r[root]),
                {".read", ".write"}
            )

    def test_simulation_unchanged(self):
        cfg = json.loads(
            (ROOT / "tasnim.config.json").read_text()
        )

        self.assertEqual(
            cfg,
            {
                "activeDataRoot": "simulation",
                "mode": "SIMULATION"
            }
        )

if __name__ == "__main__":
    unittest.main()
