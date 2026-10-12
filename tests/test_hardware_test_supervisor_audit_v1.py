"""Offline bounded supervisor audit, corruption and dedup tests."""
import copy
import os
import unittest
from unittest.mock import patch

from ai.hardware_test_supervisor_audit_v1 import (
    AUDIT_PATH, MAX_EVENTS, SupervisorAuditReviewRequired,
    append_supervisor_audit, verify_supervisor_audit,
)
from ai.hardware_test_supervisor_status_v1 import make_supervisor_status
from test_hardware_test_supervisor_v1 import SupervisorFakeDB
from test_hardware_test_worker_v2 import ENV


class AuditTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, dict(ENV, TASNIM_AI_COORDINATION_EMULATOR_ONLY="YES"),
                       clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.db = SupervisorFakeDB({})

    def status(self, t, state="IDLE"):
        return make_supervisor_status(state=state, timestamp_ms=t, attempts=1)

    def test_append_deduplicates_and_does_not_keep_sensitive_fields(self):
        event = self.status(1000)
        self.assertTrue(append_supervisor_audit(self.db, event))
        first = copy.deepcopy(self.db.values[AUDIT_PATH])
        self.assertFalse(append_supervisor_audit(self.db, event))
        self.assertFalse(append_supervisor_audit(self.db, self.status(999)))
        self.assertEqual(first, self.db.values[AUDIT_PATH])
        self.assertEqual(len(verify_supervisor_audit(first)), 1)
        self.assertNotIn("password", str(first))
        with self.assertRaises(ValueError):
            append_supervisor_audit(self.db, {**event, "token": "TOP-SECRET"})
        self.assertEqual(first, self.db.values[AUDIT_PATH])

    def test_retention_caps_twenty_and_hash_chain_survives_window(self):
        for i in range(MAX_EVENTS + 5):
            self.assertTrue(append_supervisor_audit(self.db, self.status(1000+i)))
        stored = self.db.values[AUDIT_PATH]
        items = verify_supervisor_audit(stored)
        self.assertEqual(len(items), MAX_EVENTS)
        self.assertEqual(items[0]["sequence"], 6)
        self.assertEqual(items[-1]["sequence"], MAX_EVENTS+5)
        self.assertEqual(items[-1]["sha256"], stored["tail_sha256"])
        self.assertEqual(items[-1]["record"]["timestamp_ms"], 1000+MAX_EVENTS+4)

    def test_corrupt_digest_blocks_every_future_append(self):
        append_supervisor_audit(self.db, self.status(1000))
        self.db.values[AUDIT_PATH]["events"]["s1"]["record"]["processed_count"] = 7
        before = copy.deepcopy(self.db.values[AUDIT_PATH])
        with self.assertRaises(SupervisorAuditReviewRequired):
            append_supervisor_audit(self.db, self.status(1001))
        self.assertEqual(self.db.values[AUDIT_PATH], before)

    def test_corrupt_order_or_root_blocks_append(self):
        append_supervisor_audit(self.db, self.status(1000))
        self.db.values[AUDIT_PATH]["events"]["s3"] = copy.deepcopy(
            self.db.values[AUDIT_PATH]["events"]["s1"]
        )
        with self.assertRaises(SupervisorAuditReviewRequired):
            append_supervisor_audit(self.db, self.status(1001))

    def test_refuses_non_demo_before_any_database_access(self):
        with patch.dict(os.environ, {"GCLOUD_PROJECT": "production"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                append_supervisor_audit(self.db, self.status(1000))
        self.assertEqual(self.db.reads, 0)
        self.assertEqual(self.db.values, {})


if __name__ == "__main__":
    unittest.main()
