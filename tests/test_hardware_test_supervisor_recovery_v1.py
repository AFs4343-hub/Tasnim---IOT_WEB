"""Offline crash-window reporting recovery tests; synthetic FakeDB only.

Never initializes Firebase, loads a model, or invokes a real backend.
"""
import copy
import os
import unittest
from unittest.mock import patch

from ai.hardware_test_supervisor_recovery_v1 import (
    inspect_demo_supervisor_reporting, repair_demo_supervisor_reporting,
    SupervisorReportingReviewRequired,
)
from ai.hardware_test_supervisor_v1 import run_supervised_emulator_cycle
from ai.hardware_test_supervisor_status_v1 import (
    STATUS_PATH, make_supervisor_status, persist_supervisor_status,
)
from ai.hardware_test_supervisor_feed_v1 import FEED_PATH, publish_demo_supervisor_feed
from ai.hardware_test_supervisor_audit_v1 import (
    AUDIT_PATH, append_supervisor_audit, verify_supervisor_audit,
    SupervisorAuditReviewRequired,
)
from test_hardware_test_supervisor_v1 import SupervisorFakeDB
from test_hardware_test_worker_v2 import ENV, MODEL, prediction, three_slots
from test_hardware_test_history_v2 import SLOT0, INTERVAL


class SupervisorReportingRecoveryTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, dict(
            ENV, TASNIM_AI_COORDINATION_EMULATOR_ONLY="YES"
        ), clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.db = SupervisorFakeDB(three_slots())
        self.stamp = SLOT0 + 10 * INTERVAL

    def report(self, stamp=None, state="PROCESSED"):
        return make_supervisor_status(
            state=state, timestamp_ms=self.stamp if stamp is None else stamp,
            attempts=1, result={"processed_slots": [SLOT0 + INTERVAL]},
        )

    def cycle(self, *, stamp=None, predict_fn=prediction):
        return run_supervised_emulator_cycle(
            self.db, session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=predict_fn,
            now_ms=self.stamp if stamp is None else stamp,
        )

    def test_clean_uninitialized_status_has_no_side_effect(self):
        self.assertEqual(inspect_demo_supervisor_reporting(self.db)["state"], "NO_REPORT")
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "NO_REPORT")
        self.assertEqual(self.db.values, {})

    def test_crash_after_private_status_blocks_new_cycle_then_repairs(self):
        record = self.report()
        persist_supervisor_status(self.db, record)
        original = copy.deepcopy(self.db.values)
        with self.assertRaisesRegex(
            SupervisorReportingReviewRequired, "repair_required"
        ):
            self.cycle(predict_fn=lambda *_: self.fail("worker should not start"))
        self.assertEqual(self.db.values, original)
        self.assertEqual(inspect_demo_supervisor_reporting(self.db)["state"],
                         "RECOVERY_REQUIRED")
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "REPAIRED")
        self.assertEqual(self.db.values[FEED_PATH], record)
        self.assertEqual(
            verify_supervisor_audit(self.db.values[AUDIT_PATH])[-1]["record"], record
        )
        before = copy.deepcopy(self.db.values)
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "CONSISTENT")
        self.assertEqual(self.db.values, before)

    def test_crash_after_feed_rebuilds_audit_without_replacing_private(self):
        record = self.report()
        persist_supervisor_status(self.db, record)
        publish_demo_supervisor_feed(self.db, record)
        self.assertEqual(inspect_demo_supervisor_reporting(self.db)["state"],
                         "RECOVERY_REQUIRED")
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "REPAIRED")
        self.assertEqual(self.db.values[STATUS_PATH], record)
        self.assertEqual(self.db.values[FEED_PATH], record)
        self.assertEqual(len(verify_supervisor_audit(self.db.values[AUDIT_PATH])), 1)

    def test_retry_after_fault_during_audit_transaction_is_idempotent(self):
        record = self.report()
        persist_supervisor_status(self.db, record)
        self.db.fail_once_path = AUDIT_PATH
        with self.assertRaises(ConnectionError):
            repair_demo_supervisor_reporting(self.db)
        self.assertEqual(self.db.values[FEED_PATH], record)
        self.assertNotIn(AUDIT_PATH, self.db.values)
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "REPAIRED")
        self.assertEqual(len(verify_supervisor_audit(self.db.values[AUDIT_PATH])), 1)

    def test_recovery_refuses_corrupt_feed_or_audit_without_overwrite(self):
        record = self.report()
        persist_supervisor_status(self.db, record)
        for path, value in (
            (FEED_PATH, {"state": "BROKEN", "password": "sensitive"}),
            (AUDIT_PATH, {"schema_version": 1, "tail_sha256": "wrong"}),
        ):
            with self.subTest(path=path):
                self.db.values[path] = copy.deepcopy(value)
                saved = copy.deepcopy(self.db.values)
                with self.assertRaises((SupervisorReportingReviewRequired,
                                        SupervisorAuditReviewRequired)):
                    repair_demo_supervisor_reporting(self.db)
                self.assertEqual(self.db.values, saved)
                self.db.values.pop(path)

    def test_recovery_refuses_future_or_conflicting_same_time_feed(self):
        private = self.report()
        persist_supervisor_status(self.db, private)
        for other in (
            self.report(self.stamp + 1),
            self.report(self.stamp, state="IDLE"),
        ):
            self.db.values[FEED_PATH] = other
            before = copy.deepcopy(self.db.values)
            with self.assertRaises(SupervisorReportingReviewRequired):
                repair_demo_supervisor_reporting(self.db)
            self.assertEqual(self.db.values, before)

    def test_missing_private_with_existing_feed_fails_closed(self):
        self.db.values[FEED_PATH] = self.report()
        before = copy.deepcopy(self.db.values)
        with self.assertRaises(SupervisorReportingReviewRequired):
            repair_demo_supervisor_reporting(self.db)
        self.assertEqual(self.db.values, before)

    def test_real_partial_cycle_failure_and_manual_repair_before_idle(self):
        self.db.fail_once_path = FEED_PATH
        with self.assertRaises(ConnectionError):
            self.cycle()
        self.assertEqual(self.db.values[STATUS_PATH]["state"], "PROCESSED")
        self.assertNotIn(FEED_PATH, self.db.values)
        self.assertNotIn(AUDIT_PATH, self.db.values)
        # The worker has already archived predictions before the reporting
        # failure; a repeated run must not generate an unrelated status.
        with self.assertRaises(SupervisorReportingReviewRequired):
            self.cycle(stamp=self.stamp + 1, predict_fn=lambda *_: self.fail(
                "unexpected inference after partial commit"
            ))
        self.assertEqual(repair_demo_supervisor_reporting(self.db)["state"], "REPAIRED")
        result = self.cycle(
            stamp=self.stamp + 1, predict_fn=lambda *_: self.fail(
                "already processed slots must not be re-predicted"
            ),
        )
        self.assertEqual(result["state"], "IDLE")
        events = verify_supervisor_audit(self.db.values[AUDIT_PATH])
        self.assertEqual([e["record"]["state"] for e in events],
                         ["PROCESSED", "IDLE"])

    def test_emulator_guard_blocks_before_any_database_read(self):
        with patch.dict(os.environ, {"GCLOUD_PROJECT": "live-project"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                repair_demo_supervisor_reporting(self.db)
        self.assertEqual(self.db.values, {})
        self.assertEqual(self.db.reads, 0)


if __name__ == "__main__":
    unittest.main()
