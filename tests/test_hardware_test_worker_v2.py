"""Offline candidate worker tests: in-memory DB, no Firebase or network."""
import copy
import os
import unittest
from threading import RLock
from unittest.mock import patch

from ai.hardware_test_worker_v2 import (
    WorkerReviewRequired, WorkerSourceChanged, context_digests,
    run_emulator_cycle,
)
from ai.hardware_test_history_v2 import prepare_backlog
from test_hardware_test_history_v2 import INTERVAL, SLOT0, slot

MODEL = "prototype-v1"
ENV = {
    "TASNIM_AI_WORKER_EMULATOR_ONLY": "YES",
    "FIREBASE_DATABASE_EMULATOR_HOST": "127.0.0.1:19003",
    "GCLOUD_PROJECT": "demo-tasnim-security",
}


def prediction(frame, bundle):
    return {
        "session_id": str(frame.iloc[-1]["session_id"]),
        "status": "NORMAL",
        "timestamp": "2026-10-11T12:00:00",
        "location": None,
        "random_forest": {"prediction": "NORMAL", "confidence": 0.55},
        "isolation_forest": {"is_anomaly": False, "decision_score": 0.1},
        "dominant_zscore": {"node": "N0", "parameter": "tds", "zscore": 0.2},
    }


class FakeDB:
    emulator_only = True
    emulator_project = "demo-tasnim-security"
    emulator_host = "127.0.0.1:19003"

    def __init__(self, history):
        self.history = copy.deepcopy(history)
        self.values = {}
        self.lock = RLock()
        self.fail_once_path = None
        self.reads = 0

    def reference(self, path):
        parent = self

        class Ref:
            def get(self):
                if path != "hardware_test/history":
                    raise AssertionError("unexpected database read")
                with parent.lock:
                    parent.reads += 1
                    current = copy.deepcopy(parent.history)
                    for key, record in parent.values.items():
                        if key.startswith("hardware_test/history/") and key.endswith("/analysis"):
                            slot_id = key.split("/")[2]
                            current[slot_id]["analysis"] = copy.deepcopy(record)
                    return current

            def transaction(self, update):
                with parent.lock:
                    if path == parent.fail_once_path:
                        parent.fail_once_path = None
                        raise ConnectionError("injected partial failure")
                    old = copy.deepcopy(parent.values.get(path))
                    new = update(old)
                    parent.values[path] = copy.deepcopy(new)
                    return copy.deepcopy(new)

        return Ref()


def three_slots():
    return {str(SLOT0 + i*INTERVAL): slot(SLOT0+i*INTERVAL) for i in range(3)}


class WorkerCandidateTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, ENV, clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.db = FakeDB(three_slots())

    def cycle(self, predict=prediction):
        return run_emulator_cycle(
            self.db, session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=predict, now_ms=SLOT0+10*INTERVAL,
        )

    def test_guard_rejects_missing_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                self.cycle()
        self.assertEqual(self.db.reads, 0)

    def test_guard_rejects_production_adapter(self):
        self.db.emulator_only = False
        with self.assertRaises(RuntimeError):
            self.cycle()
        self.assertEqual(self.db.reads, 0)

    def test_first_pass_and_restart_reuses_identical_checkpoint(self):
        first = self.cycle()
        self.assertEqual(first["processed_slots"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertEqual(len(self.db.values), 3)
        marker = self.db.values[f"hardware_test/history/{SLOT0+INTERVAL}/analysis"]
        self.assertEqual(len(marker["source_digest_sha256"]), 64)
        self.assertEqual(self.db.values["hardware_test/analysis/latest"]["source_timestamp_ms"],
                         SLOT0+2*INTERVAL)

        def forbidden(frame, bundle):
            raise AssertionError("must not run model for stored analysis")

        second = self.cycle(forbidden)
        self.assertEqual(second["processed_slots"], [])
        self.assertEqual(second["recovered_slots"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertEqual(len(self.db.values), 3)

    def test_partial_latest_failure_retry_does_not_repredict_old_slot(self):
        self.db.fail_once_path = "hardware_test/analysis/latest"
        with self.assertRaises(ConnectionError):
            self.cycle()
        target = f"hardware_test/history/{SLOT0+INTERVAL}/analysis"
        stored = copy.deepcopy(self.db.values[target])
        self.assertNotIn("hardware_test/analysis/latest", self.db.values)
        result = self.cycle()
        self.assertEqual(result["recovered_slots"], [SLOT0+INTERVAL])
        self.assertEqual(result["processed_slots"], [SLOT0+2*INTERVAL])
        self.assertEqual(self.db.values[target], stored)

    def test_late_valid_slot_blocks_preexisting_analyses(self):
        self.db.history.pop(str(SLOT0+INTERVAL))
        self.db.history[str(SLOT0+3*INTERVAL)] = slot(SLOT0+3*INTERVAL)
        self.cycle()
        self.db.history[str(SLOT0+INTERVAL)] = slot(SLOT0+INTERVAL)
        before = copy.deepcopy(self.db.values)
        with self.assertRaises(WorkerReviewRequired):
            self.cycle()
        self.assertEqual(self.db.values, before)

    def test_source_changed_during_predict_never_writes(self):
        self.db.history.pop(str(SLOT0+INTERVAL))
        self.db.history[str(SLOT0+3*INTERVAL)] = slot(SLOT0+3*INTERVAL)

        def mutation(frame, bundle):
            self.db.history[str(SLOT0+INTERVAL)] = slot(SLOT0+INTERVAL)
            return prediction(frame, bundle)

        with self.assertRaises(WorkerSourceChanged):
            self.cycle(mutation)
        self.assertEqual(self.db.values, {})

    def test_corrupt_checkpoint_is_never_overwritten(self):
        self.db.history[str(SLOT0+INTERVAL)]["analysis"] = {"status": "NORMAL"}
        with self.assertRaises(WorkerReviewRequired):
            self.cycle()
        self.assertEqual(self.db.values, {})

    def test_invalid_analyzed_source_is_not_ignored(self):
        self.db.history[str(SLOT0+INTERVAL)]["analysis"] = {"status": "NORMAL"}
        self.db.history[str(SLOT0+INTERVAL)].pop("N2")
        with self.assertRaises(WorkerReviewRequired):
            self.cycle()
        self.assertEqual(self.db.values, {})

    def test_hash_stable_for_missing_empty_flags_and_field_order(self):
        a = three_slots()
        b = copy.deepcopy(a)
        for item in b.values():
            for node in ("N0", "N1", "N2"):
                packet = item[node]
                packet.pop("quality_flags")
                item[node] = dict(reversed(list(packet.items())))
        left = context_digests(a, prepare_backlog(a, session_id="OFFLINE_SESSION"))
        right = context_digests(b, prepare_backlog(b, session_id="OFFLINE_SESSION"))
        self.assertEqual(left, right)

    def test_empty_history_and_one_warmup_slot_no_writes(self):
        self.db.history = {}
        self.assertEqual(self.cycle()["processed_slots"], [])
        self.db.history = {str(SLOT0): slot(SLOT0)}
        self.assertEqual(self.cycle()["processed_slots"], [])
        self.assertEqual(self.db.values, {})


if __name__ == "__main__":
    unittest.main()
