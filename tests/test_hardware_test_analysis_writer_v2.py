"""Offline tests: analysis persistence candidate, no Firebase initialization."""
import copy
import unittest
from threading import RLock

from ai.hardware_test_analysis_writer_v2 import (
    AnalysisConflict, AnalysisLatestConflict,
    prepare_analysis_record, commit_verified_analysis,
)

S0 = 1_791_724_500_000
STEP = 300_000


def preview(slot=S0):
    return {
        "source_timestamp_ms": slot,
        "session_id": "OFFLINE_SESSION",
        "data_source": "HARDWARE_TEST",
        "model_stage": "PROTOTYPE_SIMULATION",
        "time_mode": "ACTUAL_TIMESTAMP",
        "timestamp": "2026-10-11T12:00:00",
        "status": "NORMAL",
        "location": None,
        "random_forest": {"prediction": "NORMAL", "confidence": 0.53,
                          "probabilities": {"NORMAL": 0.53, "ANOMALI_N0": 0.47}},
        "isolation_forest": {"is_anomaly": True, "decision_score": -0.03},
        "dominant_zscore": {"parameter": "tds", "node": "N0",
                            "zscore": -7.15},
        "model_disagreement": True,
        "interpretation": "MODEL_REVIEW_REQUIRED",
    }


def record(slot=S0):
    return prepare_analysis_record(preview(slot), model_version="prototype-v1",
                                   inference_timestamp_ms=S0 + 100_000)


class FakeDB:
    def __init__(self):
        self.values = {}
        self.lock = RLock()
        self.fail_once_path = None

    def reference(self, path):
        parent = self

        class Ref:
            def transaction(self, updater):
                with parent.lock:
                    if path == parent.fail_once_path:
                        parent.fail_once_path = None
                        raise ConnectionError("simulated latest write failure")
                    old = copy.deepcopy(parent.values.get(path))
                    new = updater(old)
                    parent.values[path] = copy.deepcopy(new)
                    return copy.deepcopy(new)

        return Ref()


class CandidateAnalysisWriterTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()

    def test_first_analysis_archived_and_latest(self):
        r = record()
        result = commit_verified_analysis(self.db, r)
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")
        self.assertEqual(self.db.values[f"hardware_test/history/{S0}/analysis"], r)
        self.assertEqual(self.db.values["hardware_test/analysis/latest"], r)

    def test_identical_retry_no_conflict(self):
        r = record()
        commit_verified_analysis(self.db, r)
        commit_verified_analysis(self.db, copy.deepcopy(r))
        self.assertEqual(len(self.db.values), 2)

    def test_older_backfill_never_rewinds_latest(self):
        newer = record(S0 + STEP)
        older = record(S0)
        commit_verified_analysis(self.db, newer)
        result = commit_verified_analysis(self.db, older)
        self.assertEqual(result["latest"], "OLDER_ANALYSIS_PRESERVED")
        self.assertEqual(self.db.values["hardware_test/analysis/latest"], newer)

    def test_different_record_same_slot_conflicts(self):
        first = record()
        commit_verified_analysis(self.db, first)
        second = copy.deepcopy(first)
        second["random_forest"]["confidence"] = 0.51
        with self.assertRaises(AnalysisConflict):
            commit_verified_analysis(self.db, second)
        self.assertEqual(self.db.values[f"hardware_test/history/{S0}/analysis"], first)

    def test_partial_failure_retry_recovers_latest(self):
        r = record()
        self.db.fail_once_path = "hardware_test/analysis/latest"
        with self.assertRaises(ConnectionError):
            commit_verified_analysis(self.db, r)
        self.assertEqual(len(self.db.values), 1)
        commit_verified_analysis(self.db, r)
        self.assertEqual(len(self.db.values), 2)

    def test_conflicting_latest_same_slot_not_overwritten(self):
        r = record()
        self.db.values["hardware_test/analysis/latest"] = {**r, "status": "ANOMALI"}
        with self.assertRaises(AnalysisLatestConflict):
            commit_verified_analysis(self.db, r)
        self.assertEqual(self.db.values["hardware_test/analysis/latest"]["status"], "ANOMALI")

    def test_corrupt_existing_latest_not_overwritten(self):
        self.db.values["hardware_test/analysis/latest"] = {"bad": "metadata"}
        with self.assertRaises(AnalysisLatestConflict):
            commit_verified_analysis(self.db, record())
        self.assertEqual(self.db.values["hardware_test/analysis/latest"], {"bad": "metadata"})

    def test_model_stage_enforced(self):
        bad = preview()
        bad["model_stage"] = "VALIDATED_FIELD"
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_canonicalization_removes_null_location(self):
        source = preview()
        before = copy.deepcopy(source)
        prepared = prepare_analysis_record(source, model_version="v1",
                                           inference_timestamp_ms=S0 + 1)
        self.assertNotIn("location", prepared)
        self.assertEqual(source, before)

    def test_bad_nan_rejected(self):
        bad = preview()
        bad["random_forest"]["confidence"] = float("nan")
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_direct_noncanonical_write_is_rejected(self):
        altered = record()
        altered["location"] = None
        with self.assertRaises(ValueError):
            commit_verified_analysis(self.db, altered)
        self.assertEqual(self.db.values, {})

    def test_rf_status_mismatch_rejected(self):
        bad = preview()
        bad["status"] = "ANOMALI"
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_disagreement_mismatch_rejected(self):
        bad = preview()
        bad["model_disagreement"] = False
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_wrong_source_rejected(self):
        bad = preview()
        bad["data_source"] = "simulation"
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_invalid_source_digest_format_refused(self):
        bad = preview()
        bad["source_digest_sha256"] = "not-64-hex"
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)

    def test_invalid_slot_rejected(self):
        bad = preview(S0 + 1)
        with self.assertRaises(ValueError):
            prepare_analysis_record(bad, model_version="v1",
                                    inference_timestamp_ms=S0 + 1)


if __name__ == "__main__":
    unittest.main()
