"""Offline checks for frozen production files; no production connection."""
import tempfile
from pathlib import Path
import unittest

from scripts.check_production_baseline_guard import (
    FROZEN_GIT_BLOBS, ProductionBaselineChanged, ROOT,
    git_blob_hash, verify_production_baseline,
)


class FrozenBaselineGuardTests(unittest.TestCase):
    def test_candidate_branch_preserves_all_reviewed_baseline_files(self):
        self.assertEqual(set(verify_production_baseline(ROOT)), set(FROZEN_GIT_BLOBS))

    def test_plain_git_blob_encoding_has_expected_reference(self):
        # "test content" is a public Git hash test vector, not a secret.
        self.assertEqual(git_blob_hash(b"test content\n"),
                         "d670460b4b4aece5915caf5c68d12f560a9fe3e4")

    def test_one_byte_change_to_production_rules_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in FROZEN_GIT_BLOBS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            self.assertEqual(set(verify_production_baseline(root)),
                             set(FROZEN_GIT_BLOBS))
            rules = root / "database.rules.json"
            rules.write_bytes(rules.read_bytes() + b" ")
            with self.assertRaisesRegex(
                ProductionBaselineChanged, "database.rules.json"
            ):
                verify_production_baseline(root)

    def test_missing_or_symlinked_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in FROZEN_GIT_BLOBS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            config = root / "tasnim.config.json"
            config.unlink()
            with self.assertRaisesRegex(
                ProductionBaselineChanged, "tasnim.config.json"
            ):
                verify_production_baseline(root)
            config.symlink_to(ROOT / "tasnim.config.json")
            with self.assertRaisesRegex(
                ProductionBaselineChanged, "tasnim.config.json"
            ):
                verify_production_baseline(root)


if __name__ == "__main__":
    unittest.main()
