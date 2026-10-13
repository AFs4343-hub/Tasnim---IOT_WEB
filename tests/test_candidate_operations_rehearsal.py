"""Offline operational rehearsal; NO Firebase connection, secret values or deletion."""
import copy
import unittest

from iot.hardware_test_nonce_audit_v1 import (
    audit_nonce_registry, NonceAuditReviewRequired,
)
from iot.hardware_test_backup_rehearsal_v1 import (
    prepare_synthetic_backup, rehearse_synthetic_restore,
    DemoRestoreReviewRequired,
)
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


NOW = SLOT0 + 5 * INTERVAL


class CandidateOperationsRehearsalTests(unittest.TestCase):
    def test_nonce_audit_is_read_only_and_reports_age_without_cleanup(self):
        registry = {
            "N0": {
                "nonceA00000000000001": {
                    "fingerprint": "a"*64, "request_ts_ms": NOW - 1000,
                },
                "nonceB00000000000001": {
                    "fingerprint": "b"*64,
                    "request_ts_ms": NOW - 3*86_400_000,
                },
            },
            "N1": {},
        }
        before = copy.deepcopy(registry)
        result = audit_nonce_registry(registry, now_ms=NOW)
        self.assertEqual(result["state"], "AUDITED_NO_DELETION")
        self.assertEqual(result["entry_count"], 2)
        self.assertEqual(result["per_node"]["N0"]["past_review_horizon"], 1)
        self.assertFalse(result["cleanup_performed"])
        self.assertEqual(registry, before)

    def test_invalid_nonce_or_future_timestamp_requires_review_not_delete(self):
        record = {"fingerprint": "a"*64, "request_ts_ms": NOW+3600_000}
        registry = {"N2": {"short": record}}
        before = copy.deepcopy(registry)
        result = audit_nonce_registry(registry, now_ms=NOW)
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertEqual(result["per_node"]["N2"]["invalid"], 1)
        self.assertEqual(registry, before)

    def test_nonce_registry_hard_limit_fails_closed(self):
        registry = {"N0": {
            f"noncetest000000000{i:03}": {
                "fingerprint": "c"*64, "request_ts_ms": NOW,
            } for i in range(3)
        }}
        with self.assertRaises(NonceAuditReviewRequired):
            audit_nonce_registry(registry, now_ms=NOW, max_entries=2)

    def test_backup_restore_copy_matches_valid_synthetic_sensor_history(self):
        fixture = {
            "history": {
                str(SLOT0+i*INTERVAL): slot(SLOT0+i*INTERVAL)
                for i in range(3)
            },
            "nodes": {"N0": {"latest": slot(SLOT0)["N0"]}},
        }
        original = copy.deepcopy(fixture)
        backup = prepare_synthetic_backup(fixture)
        restored = rehearse_synthetic_restore(backup)
        self.assertEqual(restored, original)
        restored["history"].clear()
        self.assertEqual(fixture, original)
        self.assertEqual(backup["hardware_test"], original)

    def test_corrupt_backup_digest_and_private_roots_refused(self):
        fixture = {"history": {str(SLOT0): slot(SLOT0)}}
        backup = prepare_synthetic_backup(fixture)
        tampered = copy.deepcopy(backup)
        tampered["hardware_test"]["history"].clear()
        with self.assertRaises(DemoRestoreReviewRequired):
            rehearse_synthetic_restore(tampered)
        with self.assertRaises(DemoRestoreReviewRequired):
            prepare_synthetic_backup({"gateway_state": {"nonces": {}}})
        with self.assertRaises(DemoRestoreReviewRequired):
            prepare_synthetic_backup({"worker_state": {"secret": "X"}})
        with self.assertRaises(DemoRestoreReviewRequired):
            rehearse_synthetic_restore({**backup, "extra": True})

    def test_backup_rejects_nonfinite_value_and_oversized_snapshot(self):
        with self.assertRaises(DemoRestoreReviewRequired):
            prepare_synthetic_backup({"history": {"bad": float("nan")}})
        with self.assertRaises(DemoRestoreReviewRequired):
            prepare_synthetic_backup({"history": {"huge": "x" * 2_000_001}})


if __name__ == "__main__":
    unittest.main()
