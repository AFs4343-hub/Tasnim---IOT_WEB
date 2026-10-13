"""Offline V2 analysis-checkpoint provenance tests; no network/model files."""
import copy
import os
import unittest
from unittest.mock import patch

from ai.hardware_test_checkpoint_integrity_v1 import (
    CheckpointIntegrityReviewRequired,
    inspect_checkpoint_integrity, inspect_demo_checkpoints,
)
from ai.hardware_test_worker_v2 import run_emulator_cycle
from test_hardware_test_worker_v2 import (
    ENV, MODEL, FakeDB, prediction, three_slots,
)
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


class CheckpointIntegrityAuditTests(unittest.TestCase):
    def setUp(self):
        scope = patch.dict(os.environ, ENV, clear=True)
        scope.start()
        self.addCleanup(scope.stop)
        self.db = FakeDB(three_slots())
        self.kwargs = dict(session_id="OFFLINE_SESSION", model_version=MODEL)

    def inspect(self, db=None, **kwargs):
        return inspect_demo_checkpoints(
            db or self.db, **dict(self.kwargs, **kwargs),
        )

    def cycle(self, db=None, predict_fn=prediction):
        return run_emulator_cycle(
            db or self.db, session_id="OFFLINE_SESSION",
            model_version=MODEL, model_bundle=None,
            predict_fn=predict_fn, now_ms=SLOT0 + 10*INTERVAL,
        )

    def test_no_checkpoint_is_read_only_and_reports_pending(self):
        history_before = copy.deepcopy(self.db.history)
        result = self.inspect()
        self.assertEqual(result["state"], "NO_CHECKPOINTS")
        self.assertEqual(result["archived_count"], 0)
        self.assertEqual(result["pending_count"], 2)
        self.assertTrue(result["read_only"])
        self.assertEqual(self.db.history, history_before)
        self.assertEqual(self.db.values, {})

    def test_completed_worker_history_and_latest_are_aligned(self):
        self.cycle()
        before = copy.deepcopy(self.db.values)
        result = self.inspect()
        self.assertEqual(result["state"], "ALIGNED")
        self.assertEqual(result["archived_count"], 2)
        self.assertEqual(result["pending_count"], 0)
        self.assertEqual(result["highest_archived_slot"], SLOT0 + 2*INTERVAL)
        self.assertEqual(result["latest_slot"], SLOT0 + 2*INTERVAL)
        self.assertEqual(self.db.values, before)

    def test_partial_archive_write_is_repairable_not_repredicted(self):
        self.db.fail_once_path = "hardware_test/analysis/latest"
        with self.assertRaises(ConnectionError):
            self.cycle()
        before = copy.deepcopy(self.db.values)
        result = self.inspect()
        self.assertEqual(result["state"], "REPAIRABLE_LATEST")
        self.assertEqual(result["archived_count"], 1)
        self.assertIsNone(result["latest_slot"])
        self.assertEqual(self.db.values, before)
        predicted = []
        def only_new_slot(frame, bundle):
            # The recovered archived slot is not fed to the predictor again;
            # the remaining pending slot may still legitimately be inferred.
            predicted.append(int(frame.iloc[-1]["source_timestamp_ms"]))
            return prediction(frame, bundle)
        self.cycle(predict_fn=only_new_slot)
        self.assertEqual(predicted, [SLOT0 + 2*INTERVAL])
        self.assertEqual(self.inspect()["state"], "ALIGNED")

    def test_verified_older_latest_pointer_is_repairable(self):
        self.cycle()
        prior = copy.deepcopy(self.db.values[
            f"hardware_test/history/{SLOT0+INTERVAL}/analysis"
        ])
        self.db.values["hardware_test/analysis/latest"] = prior
        before = copy.deepcopy(self.db.values)
        result = self.inspect()
        self.assertEqual(result["state"], "REPAIRABLE_LATEST")
        self.assertEqual(result["latest_slot"], SLOT0 + INTERVAL)
        self.assertEqual(self.db.values, before)

    def test_late_backfill_of_earlier_valid_slot_invalidates_archived_hash(self):
        self.db.history = {
            str(SLOT0): slot(SLOT0),
            str(SLOT0 + 2*INTERVAL): slot(SLOT0 + 2*INTERVAL),
            str(SLOT0 + 3*INTERVAL): slot(SLOT0 + 3*INTERVAL),
        }
        self.cycle()
        self.assertEqual(self.inspect()["state"], "ALIGNED")
        self.db.history[str(SLOT0 + INTERVAL)] = slot(SLOT0 + INTERVAL)
        before = copy.deepcopy(self.db.values)
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect()
        self.assertEqual(self.db.values, before)

    def test_changed_sensor_sample_metadata_invalidates_archived_hash(self):
        self.cycle()
        self.db.history[str(SLOT0 + INTERVAL)]["N1"]["sample_id"] = "N1_CHANGED_1"
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect()

    def test_corrupt_analysis_record_or_unrelated_latest_is_never_accepted(self):
        self.cycle()
        key = f"hardware_test/history/{SLOT0 + INTERVAL}/analysis"
        original = copy.deepcopy(self.db.values)
        self.db.values[key] = {"status": "NORMAL"}
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect()
        self.db.values = copy.deepcopy(original)
        self.db.values["hardware_test/analysis/latest"] = {
            "source_timestamp_ms": SLOT0 + 2*INTERVAL,
            "model_stage": "FIELD_VALIDATED",
        }
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect()

    def test_missing_archive_but_orphan_latest_is_review_not_repair(self):
        self.db.values["hardware_test/analysis/latest"] = {
            "source_timestamp_ms": SLOT0 + INTERVAL,
        }
        before = copy.deepcopy(self.db.values)
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect()
        self.assertEqual(self.db.values, before)

    def test_invalid_source_row_is_counted_without_inventing_analysis(self):
        self.db.history[str(SLOT0 + INTERVAL)].pop("N2")
        report = self.inspect()
        self.assertEqual(report["state"], "NO_CHECKPOINTS")
        self.assertEqual(report["skipped_slot_count"], 1)
        self.assertEqual(report["pending_count"], 1)
        self.assertEqual(self.db.values, {})

    def test_size_limit_prevents_next_database_read_and_writes(self):
        with self.assertRaises(ValueError):
            self.inspect(max_source_slots=1)
        self.assertEqual(self.db.reads, 0)
        self.db.history = {
            str(SLOT0 + i*INTERVAL): slot(SLOT0 + i*INTERVAL)
            for i in range(4)
        }
        with self.assertRaises(CheckpointIntegrityReviewRequired):
            self.inspect(max_source_slots=3)
        self.assertEqual(self.db.reads, 1)
        self.assertEqual(self.db.values, {})

    def test_production_identity_and_bad_adapter_refused_before_reads(self):
        with patch.dict(os.environ, {"GCLOUD_PROJECT": "production-project"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                self.inspect()
        self.assertEqual(self.db.reads, 0)
        self.db.emulator_only = False
        with self.assertRaisesRegex(RuntimeError, "REFUSED"):
            self.inspect()
        self.assertEqual(self.db.reads, 0)

    def test_pure_audit_does_not_touch_raw_history_or_latest(self):
        snapshot = three_slots()
        latest = None
        before = copy.deepcopy(snapshot)
        result = inspect_checkpoint_integrity(
            snapshot, latest, **self.kwargs,
        )
        self.assertEqual(result["state"], "NO_CHECKPOINTS")
        self.assertEqual(snapshot, before)


if __name__ == "__main__":
    unittest.main()
