"""Fail-closed backend latest-pointer regression; synthetic in-memory only.

Backfill does not authorize accepting a corrupt, wrong-owner or wrongly
labelled latest pointer merely because it has a newer timestamp.
Neither writer deletes nor silently replaces suspicious RTDB state.
"""
import copy
import unittest

from iot.hardware_test_ingestion_core import (
    LatestConflict, ingest_verified_packet, valid_stored_latest,
)
from ai.hardware_test_analysis_writer_v2 import (
    AnalysisLatestConflict, commit_verified_analysis,
    valid_stored_latest_analysis,
)
from test_hardware_test_ingestion_core import FakeDB as IngestionDB, sample, TS, NOW
from test_hardware_test_analysis_writer_v2 import FakeDB as AnalysisDB, record, S0, STEP


class IngestionLatestIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = IngestionDB()
        self.old = sample()
        self.new = sample(ts=TS + 300_000, seq=4)

    def run_backfill(self):
        return ingest_verified_packet(self.db, self.old, now_ms=NOW)

    def test_verified_newer_pointer_survives_backfill(self):
        self.db.values["hardware_test/nodes/N0/latest"] = copy.deepcopy(self.new)
        result = self.run_backfill()
        self.assertEqual(result["latest"], "OLDER_REPLAY_PRESERVED")
        self.assertEqual(self.db.values["hardware_test/nodes/N0/latest"], self.new)

    def test_stored_empty_flags_omitted_remains_canonical(self):
        persisted = copy.deepcopy(self.new)
        persisted.pop("quality_flags")
        self.assertTrue(valid_stored_latest(persisted, node="N0"))
        self.db.values["hardware_test/nodes/N0/latest"] = persisted
        self.assertEqual(self.run_backfill()["latest"], "OLDER_REPLAY_PRESERVED")

    def test_corrupt_newer_pointer_is_not_mistaken_for_valid(self):
        for mutation in (
            {"node_id": "N2"},
            {"schema_version": 99},
            {"ph": -70},
            {"sample_id": "N2_forged"},
            {"quality_flags": ["badlowercase"]},
            {"arbitrary_extra": "wrong"},
            {"timestamp": str(TS + 300_000)},
        ):
            with self.subTest(mutation=mutation):
                corrupted = {**self.new, **mutation}
                self.db = IngestionDB()
                path = "hardware_test/nodes/N0/latest"
                self.db.values[path] = copy.deepcopy(corrupted)
                before = copy.deepcopy(corrupted)
                self.assertFalse(valid_stored_latest(corrupted, node="N0"))
                with self.assertRaises(LatestConflict):
                    self.run_backfill()
                self.assertEqual(self.db.values[path], before)
                # History-first transaction may commit before the conflict.
                self.assertEqual(len(self.db.values), 2)

    def test_future_latest_pointer_is_rejected_against_ingestion_clock(self):
        corrupted = {**self.new, "timestamp": NOW + 10_000_000}
        path = "hardware_test/nodes/N0/latest"
        self.db.values[path] = copy.deepcopy(corrupted)
        # The caller supplies the same trusted UTC clock used to validate
        # the incoming measurement, even for delayed microSD uploads.
        self.assertFalse(valid_stored_latest(corrupted, node="N0", now_ms=NOW))
        with self.assertRaises(LatestConflict):
            self.run_backfill()
        self.assertEqual(self.db.values[path], corrupted)


class AnalysisLatestIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = AnalysisDB()
        self.old = record(S0)
        self.new = record(S0 + STEP)

    def run_backfill(self):
        return commit_verified_analysis(self.db, self.old)

    def test_older_replay_preserves_verified_newer_analysis(self):
        self.db.values["hardware_test/analysis/latest"] = copy.deepcopy(self.new)
        self.assertTrue(valid_stored_latest_analysis(self.new))
        self.assertEqual(self.run_backfill()["latest"], "OLDER_ANALYSIS_PRESERVED")
        self.assertEqual(self.db.values["hardware_test/analysis/latest"], self.new)

    def test_corrupt_newer_analysis_does_not_hide_conflict(self):
        for mutation in (
            {"model_stage": "FIELD_VALIDATED"},
            {"data_source": "SIMULATION"},
            {"source_timestamp_ms": S0 + STEP + 1},
            {"model_version": ""},
            {"session_id": None},
            {"model_disagreement": "false"},
            {"source_digest_sha256": "not-a-sha256"},
            {"unexpected_secret": "wrong"},
        ):
            with self.subTest(mutation=mutation):
                self.db = AnalysisDB()
                corrupted = {**self.new, **mutation}
                path = "hardware_test/analysis/latest"
                self.db.values[path] = copy.deepcopy(corrupted)
                before = copy.deepcopy(corrupted)
                self.assertFalse(valid_stored_latest_analysis(corrupted))
                with self.assertRaises(AnalysisLatestConflict):
                    self.run_backfill()
                self.assertEqual(self.db.values[path], before)
                self.assertIn(f"hardware_test/history/{S0}/analysis", self.db.values)

    def test_equal_timestamp_conflicting_analysis_is_not_overwritten(self):
        other = {**self.old, "model_version": "prototype-v2"}
        self.assertTrue(valid_stored_latest_analysis(other))
        self.db.values["hardware_test/analysis/latest"] = copy.deepcopy(other)
        with self.assertRaises(AnalysisLatestConflict):
            self.run_backfill()
        self.assertEqual(self.db.values["hardware_test/analysis/latest"], other)


if __name__ == "__main__":
    unittest.main()
