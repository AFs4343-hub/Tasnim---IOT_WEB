"""Static check: the web-anonymous-read Rules candidate differs from the
production Rules by exactly one line (anonymous sessions may read but not
write hardware_test). Not deployed by any script or workflow."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebAnonymousRulesCandidateTests(unittest.TestCase):
    def test_only_hardware_test_write_is_tightened(self):
        production = json.loads((ROOT / "database.rules.json").read_text())
        candidate = json.loads(
            (ROOT / "database.rules.web-anonymous-read.candidate.json").read_text())
        self.assertEqual(candidate["rules"]["hardware_test"], {
            ".read": "auth != null",
            ".write": "auth != null && auth.provider != 'anonymous'",
        })
        candidate["rules"]["hardware_test"][".write"] = "auth != null"
        self.assertEqual(candidate, production)

    def test_candidate_is_not_wired_for_deploy(self):
        firebase = json.loads((ROOT / "firebase.json").read_text())
        self.assertEqual(firebase["database"]["rules"], "database.rules.json")


if __name__ == "__main__":
    unittest.main()
