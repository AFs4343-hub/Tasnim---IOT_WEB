"""Supervisor + telemetry verification on the REAL localhost RTDB Emulator."""
import os
import unittest
from unittest.mock import patch

import firebase_admin
from firebase_admin import db

from ai.hardware_test_supervisor_v1 import (
    run_supervised_emulator_cycle, run_bounded_demo_schedule,
)
from ai.hardware_test_supervisor_status_v1 import (
    STATUS_PATH, make_supervisor_status, persist_supervisor_status,
)
from ai.hardware_test_supervisor_feed_v1 import FEED_PATH
from ai.hardware_test_supervisor_recovery_v1 import (
    inspect_demo_supervisor_reporting, repair_demo_supervisor_reporting,
    SupervisorReportingReviewRequired,
)
from ai.hardware_test_supervisor_audit_v1 import (
    AUDIT_PATH, SupervisorAuditReviewRequired,
    append_supervisor_audit, verify_supervisor_audit,
)
from ai.hardware_test_worker_lease_v2 import (
    LEASE_PATH, RELEASED, acquire_exclusive_emulator_lock,
)
from test_hardware_test_worker_lease_emulator import EmulatorAdapter, PROJECT, HOST, URL
from test_hardware_test_worker_v2 import prediction
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


class SupervisorDemoEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.getenv("GCLOUD_PROJECT") != PROJECT
                or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST):
            raise RuntimeError("REFUSED: local demo only")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-supervisor-test-only",
        )
        cls.adapter = EmulatorAdapter(cls.app)

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference("worker_state/ai_v2_supervisor", app=self.app).delete()
        db.reference(LEASE_PATH, app=self.app).delete()
        db.reference("hardware_test", app=self.app).delete()
        db.reference("hardware_test/history", app=self.app).set({
            str(SLOT0 + i*INTERVAL): slot(SLOT0 + i*INTERVAL)
            for i in range(3)
        })
        p = patch.dict(os.environ, {
            "TASNIM_AI_WORKER_EMULATOR_ONLY": "YES",
            "TASNIM_AI_COORDINATION_EMULATOR_ONLY": "YES",
        })
        p.start()
        self.addCleanup(p.stop)

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def cycle(self, **kwargs):
        fn = kwargs.pop("predict_fn", prediction)
        return run_supervised_emulator_cycle(
            self.adapter, session_id="DEMO_SUPERVISOR",
            model_version="prototype-v1", model_bundle=None,
            predict_fn=fn, now_ms=SLOT0+10*INTERVAL, **kwargs,
        )

    def test_success_then_idempotent_idle_with_monotonic_status(self):
        first = self.cycle()
        self.assertEqual(first["state"], "PROCESSED")
        self.assertEqual(first["processed_count"], 2)
        self.assertTrue(first["status_persisted"])
        self.assertTrue(first["feed_persisted"])
        self.assertTrue(first["audit_persisted"])
        self.assertEqual(self.read(STATUS_PATH), self.read(FEED_PATH))
        self.assertEqual(
            verify_supervisor_audit(self.read(AUDIT_PATH))[-1]["record"],
            self.read(STATUS_PATH),
        )
        self.assertEqual(self.read(STATUS_PATH)["state"], "PROCESSED")
        self.assertEqual(self.read(LEASE_PATH), RELEASED)
        second = self.cycle(
            predict_fn=lambda frame, bundle: self.fail("duplicated prediction"),
        )
        self.assertEqual(second["state"], "IDLE")
        self.assertFalse(second["status_persisted"])
        self.assertEqual(self.read(STATUS_PATH)["processed_count"], 2)

    def test_dry_run_does_not_write_status_lock_or_ai(self):
        first = self.cycle(
            dry_run=True,
            predict_fn=lambda frame, bundle: self.fail("prediction invoked"),
        )
        self.assertEqual(first["state"], "PREVIEW")
        self.assertEqual(first["status_persisted"], False)
        self.assertIsNone(self.read(STATUS_PATH))
        self.assertIsNone(self.read(FEED_PATH))
        self.assertIsNone(self.read(AUDIT_PATH))
        self.assertIsNone(self.read(LEASE_PATH))
        self.assertIsNone(self.read("hardware_test/analysis/latest"))

    def test_held_lock_reports_waiting_but_does_not_run_model(self):
        acquire_exclusive_emulator_lock(self.adapter)
        result = self.cycle(
            predict_fn=lambda frame, bundle: self.fail("lock ignored"),
        )
        self.assertEqual(result["state"], "WAITING_LOCK")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(self.read(STATUS_PATH)["error_code"], "LEASE_BUSY")
        self.assertEqual(self.read(FEED_PATH)["error_code"], "LEASE_BUSY")
        self.assertIsNone(self.read("hardware_test/analysis/latest"))

    def test_worker_error_is_classified_not_recorded_verbatim(self):
        result = self.cycle(
            predict_fn=lambda *_: (_ for _ in ()).throw(
                RuntimeError("SUPER-PRIVATE-PLACEHOLDER")
            ),
        )
        self.assertEqual(result["state"], "FAILED")
        stored = self.read(STATUS_PATH)
        self.assertEqual(stored["error_code"], "WORKER_ERROR")
        self.assertNotIn("SUPER-PRIVATE", str(stored))
        self.assertNotIn("SUPER-PRIVATE", str(self.read(FEED_PATH)))
        self.assertEqual(self.read(LEASE_PATH), RELEASED)

    def test_real_emulator_audit_uses_non_numeric_keys_and_rejects_corruption(self):
        from ai.hardware_test_supervisor_status_v1 import make_supervisor_status
        for i in range(3):
            event = make_supervisor_status(
                state="IDLE", timestamp_ms=SLOT0+i+1, attempts=1,
            )
            self.assertTrue(append_supervisor_audit(self.adapter, event))
        saved = self.read(AUDIT_PATH)
        self.assertEqual(sorted(saved["events"]), ["s1", "s2", "s3"])
        self.assertEqual(len(verify_supervisor_audit(saved)), 3)
        saved["events"]["s2"]["record"]["attempts"] = 2
        db.reference(AUDIT_PATH, app=self.app).set(saved)
        with self.assertRaises(SupervisorAuditReviewRequired):
            append_supervisor_audit(self.adapter, make_supervisor_status(
                state="IDLE", timestamp_ms=SLOT0+5, attempts=1,
            ))
        self.assertEqual(self.read(AUDIT_PATH), saved)

    def test_real_emulator_reconciles_partial_private_report_without_inference(self):
        # Inject a crash window: the private record was committed but the
        # public feed and private audit were not. Recovery never reads models.
        status = make_supervisor_status(
            state="PROCESSED", timestamp_ms=SLOT0 + 20*INTERVAL,
            attempts=2, result={"processed_slots": [SLOT0 + INTERVAL]},
        )
        self.assertTrue(persist_supervisor_status(self.adapter, status))
        self.assertIsNone(self.read(FEED_PATH))
        self.assertIsNone(self.read(AUDIT_PATH))
        self.assertEqual(inspect_demo_supervisor_reporting(self.adapter)["state"],
                         "RECOVERY_REQUIRED")
        self.assertEqual(repair_demo_supervisor_reporting(self.adapter)["state"],
                         "REPAIRED")
        self.assertEqual(self.read(STATUS_PATH), self.read(FEED_PATH))
        events = verify_supervisor_audit(self.read(AUDIT_PATH))
        self.assertEqual(events[-1]["record"], status)
        self.assertEqual(repair_demo_supervisor_reporting(self.adapter)["state"],
                         "CONSISTENT")
        self.assertIsNone(self.read("hardware_test/analysis/latest"))

    def test_real_emulator_recovery_does_not_overwrite_conflicting_feed(self):
        status = make_supervisor_status(
            state="IDLE", timestamp_ms=SLOT0 + 20*INTERVAL, attempts=1,
        )
        conflict = make_supervisor_status(
            state="FAILED", timestamp_ms=SLOT0 + 20*INTERVAL,
            attempts=1, error_code="WORKER_ERROR",
        )
        self.assertTrue(persist_supervisor_status(self.adapter, status))
        db.reference(FEED_PATH, app=self.app).set(conflict)
        with self.assertRaises(SupervisorReportingReviewRequired):
            repair_demo_supervisor_reporting(self.adapter)
        self.assertEqual(self.read(FEED_PATH), conflict)
        self.assertIsNone(self.read(AUDIT_PATH))

    def test_no_overwrite_newer_status_and_guard_refuses_production(self):
        old = make_supervisor_status(
            state="FAILED", timestamp_ms=SLOT0, attempts=1,
            error_code="WORKER_ERROR",
        )
        recent = make_supervisor_status(
            state="PROCESSED", timestamp_ms=SLOT0+INTERVAL, attempts=1,
        )
        self.assertTrue(persist_supervisor_status(self.adapter, recent))
        self.assertFalse(persist_supervisor_status(self.adapter, old))
        self.assertEqual(self.read(STATUS_PATH), recent)
        with patch.dict(os.environ, {"GCLOUD_PROJECT": "production"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                persist_supervisor_status(self.adapter, recent)


if __name__ == "__main__":
    unittest.main()
