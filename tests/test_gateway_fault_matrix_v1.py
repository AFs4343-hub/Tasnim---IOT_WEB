"""Synthetic signed-gateway crash/retry/concurrency matrix (no Firebase)."""
import copy
from concurrent.futures import ThreadPoolExecutor
import unittest

from iot.hardware_test_gateway_auth_v1 import (
    NonceConflict, accept_signed_measurement,
)
from iot.hardware_test_ingestion_core import HistoryConflict, LatestConflict
from test_hardware_test_gateway_auth_v1 import KEYS, NOW, signed
from test_hardware_test_ingestion_core import FakeDB, TS, sample


class GatewayFaultMatrixTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.body, self.headers = signed(
            sample(), nonce="faultmatrixnonce000001",
        )

    def submit(self, body=None, headers=None):
        return accept_signed_measurement(
            self.db, body if body is not None else self.body,
            headers if headers is not None else self.headers,
            KEYS, now_ms=NOW,
        )

    def test_failure_at_nonce_history_or_latest_is_recoverable_same_request(self):
        nonce = "gateway_state/nonces/N0/faultmatrixnonce000001"
        history = f"hardware_test/history/{(TS // 300_000)*300_000}/N0"
        latest = "hardware_test/nodes/N0/latest"
        for fault, expected_saved in (
            (nonce, set()), (history, {nonce}),
            (latest, {nonce, history}),
        ):
            with self.subTest(fault=fault):
                self.db = FakeDB()
                self.db.fail_once_path = fault
                with self.assertRaises(ConnectionError):
                    self.submit()
                self.assertEqual(set(self.db.values), expected_saved)
                self.assertEqual(self.submit()["latest"], "LATEST_CONFIRMED")
                self.assertEqual(set(self.db.values), {nonce, history, latest})
                self.assertEqual(self.submit()["latest"], "LATEST_CONFIRMED")

    def test_competing_signed_payload_with_same_nonce_never_replaces_history(self):
        self.db.fail_once_path = "hardware_test/nodes/N0/latest"
        with self.assertRaises(ConnectionError):
            self.submit()
        altered, altered_headers = signed(
            sample(ph=8.2), nonce="faultmatrixnonce000001",
        )
        before = copy.deepcopy(self.db.values)
        with self.assertRaises(NonceConflict):
            self.submit(altered, altered_headers)
        self.assertEqual(self.db.values, before)
        self.assertEqual(self.submit()["latest"], "LATEST_CONFIRMED")

    def test_concurrent_identical_replay_does_not_duplicate_nonce_or_slot(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: self.submit(), range(8)))
        self.assertTrue(all(item["latest"] == "LATEST_CONFIRMED"
                            for item in outcomes))
        self.assertEqual(len(self.db.values), 3)

    def test_concurrent_distinct_slot_collision_has_one_winner(self):
        body1, head1 = signed(sample(), nonce="faultmatrixnonce000002")
        body2, head2 = signed(sample(
            ts=TS + 1000, seq=9, ph=8.3,
        ), nonce="faultmatrixnonce000003")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.submit, body1, head1),
                pool.submit(self.submit, body2, head2),
            ]
            outcomes = []
            for f in futures:
                try:
                    outcomes.append(f.result()["history"])
                except HistoryConflict:
                    outcomes.append("CONFLICT")
        self.assertCountEqual(outcomes, ["CONFIRMED", "CONFLICT"])
        self.assertEqual(len([
            key for key in self.db.values
            if key.startswith("hardware_test/history/")
        ]), 1)

    def test_delayed_backfill_preserves_newer_latest_without_discarding_history(self):
        recent, headers = signed(
            sample(ts=TS + 300_000, seq=4),
            nonce="faultmatrixnonce000004",
        )
        self.submit(recent, headers)
        result = self.submit()
        self.assertEqual(result["latest"], "OLDER_REPLAY_PRESERVED")
        self.assertEqual(self.db.values["hardware_test/nodes/N0/latest"]["sequence"], 4)

    def test_corrupt_latest_fails_closed_even_when_history_transaction_succeeds(self):
        latest = "hardware_test/nodes/N0/latest"
        bad = sample(ts=TS + 300_000, seq=4)
        bad["node_id"] = "N2"
        self.db.values[latest] = copy.deepcopy(bad)
        with self.assertRaises(LatestConflict):
            self.submit()
        self.assertEqual(self.db.values[latest], bad)
        self.assertEqual(len(self.db.values), 3)
        # Existing corrupt latest requires review, not automatic overwrite.
        with self.assertRaises(LatestConflict):
            self.submit()


if __name__ == "__main__":
    unittest.main()
