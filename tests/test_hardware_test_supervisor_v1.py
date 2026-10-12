"""Offline supervisor/status tests. No network, Firebase or model artifacts."""
import copy
import os
import unittest
from unittest.mock import patch

from ai.hardware_test_supervisor_v1 import (
    run_bounded_demo_schedule, run_supervised_emulator_cycle,
)
from ai.hardware_test_supervisor_status_v1 import (
    STATUS_PATH, make_supervisor_status, persist_supervisor_status,
)
from ai.hardware_test_supervisor_feed_v1 import (
    FEED_PATH, publish_demo_supervisor_feed,
)
from ai.hardware_test_supervisor_audit_v1 import (
    AUDIT_PATH, verify_supervisor_audit,
)
from ai.hardware_test_worker_lease_v2 import LEASE_PATH, RELEASED, acquire_exclusive_emulator_lock
from test_hardware_test_worker_lease_v2 import LeaseFakeDB
from test_hardware_test_worker_v2 import ENV, MODEL, prediction, three_slots
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


class SupervisorFakeDB(LeaseFakeDB):
    def reference(self, path):
        if path != STATUS_PATH:
            return super().reference(path)
        parent = self

        class StatusRef:
            def get(self):
                with parent.lock:
                    parent.reads += 1
                    return copy.deepcopy(parent.values.get(path))

            def transaction(self, update):
                with parent.lock:
                    old = copy.deepcopy(parent.values.get(path))
                    new = update(old)
                    parent.values[path] = copy.deepcopy(new)
                    return copy.deepcopy(new)

        return StatusRef()


class SupervisorCandidateTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, dict(
            ENV, TASNIM_AI_COORDINATION_EMULATOR_ONLY="YES",
        ), clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.db = SupervisorFakeDB(three_slots())

    def cycle(self, **extra):
        fn = extra.pop("predict_fn", prediction)
        return run_supervised_emulator_cycle(
            self.db, session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=fn, now_ms=SLOT0+10*INTERVAL,
            **extra,
        )

    def test_success_and_idle_status_no_raw_model_data(self):
        first = self.cycle()
        self.assertEqual(first["state"], "PROCESSED")
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(first["processed_count"], 2)
        self.assertTrue(first["status_persisted"])
        self.assertTrue(first["feed_persisted"])
        self.assertTrue(first["audit_persisted"])
        self.assertEqual(
            verify_supervisor_audit(self.db.values[AUDIT_PATH])[-1]["record"],
            self.db.values[STATUS_PATH],
        )
        self.assertEqual(self.db.values[STATUS_PATH], self.db.values[FEED_PATH])
        self.assertEqual(self.db.values[LEASE_PATH], RELEASED)
        stored = self.db.values[STATUS_PATH]
        self.assertEqual(stored["state"], "PROCESSED")
        self.assertNotIn("token", str(stored))
        self.assertNotIn("OFFLINE_SESSION", str(stored))

        second = self.cycle(predict_fn=lambda *_: self.fail("must not infer"))
        self.assertEqual(second["state"], "IDLE")
        self.assertFalse(second["status_persisted"])  # Same timestamp: no overwrite.
        self.assertFalse(second["feed_persisted"])
        self.assertFalse(second["audit_persisted"])
        self.assertEqual(len(verify_supervisor_audit(self.db.values[AUDIT_PATH])), 1)
        self.assertEqual(self.db.values[STATUS_PATH], stored)

    def test_transient_partial_latest_failure_recovers_on_bounded_retry(self):
        self.db.fail_once_path = "hardware_test/analysis/latest"
        report = self.cycle()
        self.assertEqual(report["state"], "PROCESSED")
        self.assertEqual(report["attempts"], 2)
        self.assertEqual(report["processed_count"], 1)
        self.assertEqual(report["recovered_count"], 1)
        self.assertEqual(self.db.values[LEASE_PATH], RELEASED)

    def test_retry_exhaustion_is_bounded_and_sanitized(self):
        self.db.history = {
            str(SLOT0+i*INTERVAL): slot(SLOT0+i*INTERVAL)
            for i in range(3)
        }

        def bad(*_):
            raise TimeoutError("secret=never-log-this")

        report = self.cycle(predict_fn=bad, max_attempts=2)
        self.assertEqual(report["state"], "RETRY_EXHAUSTED")
        self.assertEqual(report["error_code"], "TRANSIENT_ERROR")
        self.assertEqual(report["attempts"], 2)
        self.assertNotIn("never-log-this", str(report))
        self.assertNotIn("never-log-this", str(self.db.values[STATUS_PATH]))
        self.assertNotIn("never-log-this", str(self.db.values[FEED_PATH]))

    def test_held_lock_is_reported_without_writing_ai(self):
        acquire_exclusive_emulator_lock(self.db)
        report = self.cycle()
        self.assertEqual(report["state"], "WAITING_LOCK")
        self.assertEqual(report["error_code"], "LEASE_BUSY")
        self.assertEqual(report["attempts"], 1)
        self.assertNotIn("hardware_test/analysis/latest", self.db.values)

    def test_review_required_is_not_retried(self):
        self.db.history[str(SLOT0+INTERVAL)]["analysis"] = {"status": "NORMAL"}
        report = self.cycle(max_attempts=3)
        self.assertEqual(report["state"], "REVIEW_REQUIRED")
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["error_code"], "REVIEW_REQUIRED")

    def test_unexpected_error_reports_failure_no_exception_details(self):
        report = self.cycle(
            predict_fn=lambda *_: (_ for _ in ()).throw(ValueError("PASSWORD=xyz")),
        )
        self.assertEqual(report["state"], "FAILED")
        self.assertEqual(report["error_code"], "WORKER_ERROR")
        self.assertEqual(report["attempts"], 1)
        self.assertNotIn("xyz", str(self.db.values[STATUS_PATH]))

    def test_dry_run_does_not_write_lock_status_or_analysis(self):
        report = self.cycle(
            dry_run=True, predict_fn=lambda *_: self.fail("predicted"),
        )
        self.assertEqual(report["state"], "PREVIEW")
        self.assertEqual(report["would_process_count"], 2)
        self.assertEqual(report["status_persisted"], False)
        self.assertEqual(self.db.values, {})

    def test_feed_rejects_extra_keys_and_preserves_newer_status(self):
        first = make_supervisor_status(state="IDLE", timestamp_ms=1234, attempts=1)
        newer = make_supervisor_status(state="FAILED", timestamp_ms=1235,
                                      attempts=1, error_code="WORKER_ERROR")
        self.assertTrue(publish_demo_supervisor_feed(self.db, first))
        self.assertTrue(publish_demo_supervisor_feed(self.db, newer))
        self.assertFalse(publish_demo_supervisor_feed(self.db, first))
        self.assertEqual(self.db.values[FEED_PATH], newer)
        with self.assertRaises(ValueError):
            publish_demo_supervisor_feed(self.db, {**newer, "password":"wrong"})
        with self.assertRaises(ValueError):
            publish_demo_supervisor_feed(
                self.db, {**newer, "processed_count": True}
            )
        self.assertEqual(self.db.values[FEED_PATH], newer)

    def test_operational_status_timestamp_is_monotonic_and_bounded(self):
        old = make_supervisor_status(state="IDLE", timestamp_ms=1000, attempts=1)
        newer = make_supervisor_status(state="PROCESSED", timestamp_ms=2000, attempts=2)
        self.assertTrue(persist_supervisor_status(self.db, old))
        self.assertTrue(persist_supervisor_status(self.db, newer))
        self.assertFalse(persist_supervisor_status(self.db, old))
        self.assertFalse(persist_supervisor_status(
            self.db, make_supervisor_status(
                state="FAILED", timestamp_ms=2000, attempts=1,
                error_code="WORKER_ERROR",
            ),
        ))
        self.assertEqual(self.db.values[STATUS_PATH], newer)
        with self.assertRaises(ValueError):
            make_supervisor_status(state="SUCCESS", timestamp_ms=100, attempts=1)
        with self.assertRaises(ValueError):
            persist_supervisor_status(self.db, {**newer, "secret": "X"})

    def test_schedule_has_bounded_three_cycles_no_daemon(self):
        self.db.history = three_slots()
        delays = []
        reports = run_bounded_demo_schedule(
            self.db, cycles=3, interval_seconds=5, sleep_fn=delays.append,
            session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=prediction,
            record_status=False,
        )
        self.assertEqual(len(reports), 3)
        self.assertEqual(delays, [5, 5])
        self.assertEqual([x["state"] for x in reports], [
            "PROCESSED", "IDLE", "IDLE",
        ])

    def test_schedule_stops_on_lock_collision_without_sleep(self):
        acquire_exclusive_emulator_lock(self.db)
        delays = []
        reports = run_bounded_demo_schedule(
            self.db, cycles=3, interval_seconds=5, sleep_fn=delays.append,
            session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=prediction,
        )
        self.assertEqual([x["state"] for x in reports], ["WAITING_LOCK"])
        self.assertEqual(delays, [])

    def test_invalid_parameters_and_emulator_guard_fail_before_access(self):
        for opts in (
            {"max_attempts": 0},
            {"max_attempts": True},
            {"max_actions_per_cycle": 0},
            {"max_source_slots": 1},
            {"dry_run": "yes"},
            {"record_status": "yes"},
        ):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                self.cycle(**opts)
        for opts in (
            {"cycles": 0}, {"cycles": 4},
            {"interval_seconds": 0}, {"interval_seconds": 3601},
            {"cycles": 2, "now_ms": SLOT0},
        ):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                run_bounded_demo_schedule(
                    self.db, session_id="OFFLINE_SESSION", model_version=MODEL,
                    model_bundle=None, predict_fn=prediction, **opts,
                )
        self.assertEqual(self.db.reads, 0)
        self.assertEqual(self.db.values, {})
        with patch.dict(os.environ, {"GCLOUD_PROJECT": "live-project"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                self.cycle()
        self.assertEqual(self.db.values, {})


if __name__ == "__main__":
    unittest.main()
