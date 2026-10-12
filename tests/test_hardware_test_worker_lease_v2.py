"""Single-flight gate unit tests; entirely in memory, no Firebase LIVE."""
import copy
import os
import unittest
from unittest.mock import patch

from ai.hardware_test_worker_lease_v2 import (
    LEASE_PATH, WorkerLeaseBusy, WorkerLeaseOwnershipLost,
    acquire_exclusive_emulator_lock, release_exclusive_emulator_lock,
    run_exclusive_emulator_cycle,
)
from test_hardware_test_worker_v2 import ENV, MODEL, FakeDB, prediction, three_slots
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


class LeaseFakeDB(FakeDB):
    def reference(self, path):
        if path != LEASE_PATH:
            return super().reference(path)
        parent = self

        class Ref:
            def get(self):
                with parent.lock:
                    parent.reads += 1
                    return copy.deepcopy(parent.values.get(path))

            def transaction(self, update):
                with parent.lock:
                    old = copy.deepcopy(parent.values.get(path))
                    new = update(old)
                    if new is None:
                        parent.values.pop(path, None)
                    else:
                        parent.values[path] = copy.deepcopy(new)
                    return copy.deepcopy(new)

        return Ref()


class WorkerLeaseTests(unittest.TestCase):
    def setUp(self):
        env = dict(ENV, TASNIM_AI_COORDINATION_EMULATOR_ONLY="YES")
        p = patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.db = LeaseFakeDB(three_slots())

    def cycle(self, **extra):
        predictor = extra.pop("predict_fn", prediction)
        return run_exclusive_emulator_cycle(
            self.db, session_id="OFFLINE_SESSION", model_version=MODEL,
            model_bundle=None, predict_fn=predictor,
            now_ms=SLOT0 + 10 * INTERVAL, **extra,
        )

    def test_missing_flag_and_wrong_adapter_fail_before_firebase_access(self):
        with patch.dict(os.environ, {"TASNIM_AI_COORDINATION_EMULATOR_ONLY": "NO"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                self.cycle()
        self.assertEqual(self.db.reads, 0)
        self.assertEqual(self.db.values, {})
        self.db.emulator_only = False
        with self.assertRaisesRegex(RuntimeError, "REFUSED"):
            self.cycle()
        self.assertEqual(self.db.values, {})

    def test_lock_blocks_another_owner_and_does_not_steal(self):
        first = acquire_exclusive_emulator_lock(self.db)
        saved = copy.deepcopy(self.db.values[LEASE_PATH])
        with self.assertRaises(WorkerLeaseBusy):
            acquire_exclusive_emulator_lock(self.db)
        self.assertEqual(self.db.values[LEASE_PATH], saved)
        with self.assertRaises(WorkerLeaseOwnershipLost):
            release_exclusive_emulator_lock(self.db, owner_id="f" * 32)
        self.assertEqual(self.db.values[LEASE_PATH], saved)
        release_exclusive_emulator_lock(self.db, owner_id=first)
        self.assertNotIn(LEASE_PATH, self.db.values)
        with self.assertRaises(WorkerLeaseOwnershipLost):
            release_exclusive_emulator_lock(self.db, owner_id=first)
        other = acquire_exclusive_emulator_lock(self.db)
        self.assertNotEqual(other, first)
        release_exclusive_emulator_lock(self.db, owner_id=other)

    def test_reentrant_cycle_refused_during_prediction(self):
        nested = []

        def predictor(frame, bundle):
            try:
                self.cycle()
            except WorkerLeaseBusy:
                nested.append("blocked")
            return prediction(frame, bundle)

        report = self.cycle(predict_fn=predictor)
        self.assertEqual(nested, ["blocked", "blocked"])
        self.assertEqual(report["processed_slots"], [
            SLOT0 + INTERVAL, SLOT0 + 2 * INTERVAL,
        ])
        self.assertEqual(report["coordination"], "DEMO_EXCLUSIVE_SINGLE_FLIGHT")
        self.assertNotIn(LEASE_PATH, self.db.values)

    def test_failure_releases_lock_and_checkpoint_recovers(self):
        self.db.fail_once_path = "hardware_test/analysis/latest"
        with self.assertRaises(ConnectionError):
            self.cycle()
        self.assertNotIn(LEASE_PATH, self.db.values)
        report = self.cycle()
        self.assertEqual(report["recovered_slots"], [SLOT0 + INTERVAL])
        self.assertEqual(report["processed_slots"], [SLOT0 + 2 * INTERVAL])
        self.assertNotIn(LEASE_PATH, self.db.values)

    def test_dry_run_makes_no_lock_or_history_writes(self):
        report = self.cycle(
            dry_run=True, predict_fn=lambda frame, bundle: self.fail("predicted")
        )
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["would_process_slots"], [
            SLOT0 + INTERVAL, SLOT0 + 2 * INTERVAL,
        ])
        self.assertEqual(self.db.values, {})

    def test_stale_lock_is_not_automatically_stolen(self):
        self.db.values[LEASE_PATH] = {"owner_id": "orphan", "acquired_at_ms": 1}
        for _ in range(2):
            with self.assertRaises(WorkerLeaseBusy):
                self.cycle()
        self.assertEqual(self.db.values[LEASE_PATH]["owner_id"], "orphan")
        self.assertEqual(set(self.db.values), {LEASE_PATH})

    def test_deny_lost_owner_release_and_invalid_owner(self):
        owner = acquire_exclusive_emulator_lock(self.db)
        with self.assertRaises(ValueError):
            release_exclusive_emulator_lock(self.db, owner_id="")
        self.assertEqual(self.db.values[LEASE_PATH]["owner_id"], owner)
        release_exclusive_emulator_lock(self.db, owner_id=owner)


if __name__ == "__main__":
    unittest.main()
