"""In-memory tests. No live Firebase connection."""

import copy
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
import unittest

from iot.hardware_test_contract_v2 import ContractError
from iot.hardware_test_ingestion_core import (
    HistoryConflict,
    LatestConflict,
    ingest_verified_packet,
)

TS = 1_791_724_501_000
NOW = TS + 3_600_000


def sample(node="N0", ts=TS, seq=3, **extra):
    packet = dict(
        schema_version=2,
        node_id=node,
        sample_id=f"{node}_{ts}_{seq}",
        timestamp=ts,
        sequence=seq,
        ph=7.2,
        tds=240.0,
        turbidity=16.0,
        quality_flags=[],
        rssi=-49,
    )

    packet.update(extra)
    return packet


class FakeDB:
    def __init__(self):
        self.values = {}
        self.lock = RLock()
        self.fail_once_path = None

    def reference(self, path):
        database = self

        class Ref:
            def transaction(self, callback):
                with database.lock:
                    if database.fail_once_path == path:
                        database.fail_once_path = None
                        raise ConnectionError(
                            "simulated connection drop"
                        )

                    old = copy.deepcopy(
                        database.values.get(path)
                    )

                    new = callback(old)
                    database.values[path] = copy.deepcopy(new)
                    return copy.deepcopy(new)

        return Ref()


class IngestionCoreTests(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB()

    def ingest(self, packet):
        return ingest_verified_packet(
            self.db,
            packet,
            now_ms=NOW,
        )

    def test_first_packet_writes_both_paths(self):
        result = self.ingest(sample())
        self.assertEqual(
            result["history"], "CONFIRMED"
        )
        self.assertEqual(
            result["latest"], "LATEST_CONFIRMED"
        )
        self.assertEqual(len(self.db.values), 2)

    def test_same_sample_replay_idempotent(self):
        p = sample()
        self.ingest(p)
        self.ingest(dict(p))
        self.assertEqual(len(self.db.values), 2)

    def test_out_of_order_backfill_preserves_latest(self):
        newer = sample(
            ts=TS + 300_000,
            seq=7,
        )

        self.ingest(newer)
        result = self.ingest(sample())

        self.assertEqual(
            result["latest"],
            "OLDER_REPLAY_PRESERVED"
        )

        self.assertEqual(len(self.db.values), 3)
        self.assertEqual(
            self.db.values[
                "hardware_test/nodes/N0/latest"
            ],
            newer,
        )

    def test_conflict_same_slot_never_overwrites(self):
        first = sample()
        self.ingest(first)

        second = sample(
            ts=TS + 3000,
            seq=4,
        )

        with self.assertRaises(HistoryConflict):
            self.ingest(second)

        self.assertEqual(
            self.db.values[
                "hardware_test/nodes/N0/latest"
            ],
            first,
        )

    def test_conflict_same_timestamp_different_value(self):
        self.ingest(sample())

        with self.assertRaises(HistoryConflict):
            self.ingest(sample(ph=8.4))

    def test_invalid_sensor_diagnostic_is_stored(self):
        p = sample(
            node="N2",
            quality_flags=["PH_INVALID"],
        )

        del p["ph"]
        self.ingest(p)

        self.assertNotIn(
            "ph",
            self.db.values[
                "hardware_test/nodes/N2/latest"
            ],
        )

    def test_unknown_fields_not_written(self):
        with self.assertRaises(ContractError):
            self.ingest(
                sample(analysis={"status": "NORMAL"})
            )

        self.assertEqual(self.db.values, {})

    def test_future_timestamp_rejected(self):
        with self.assertRaises(ContractError):
            self.ingest(
                sample(ts=NOW + 120_000)
            )

        self.assertEqual(self.db.values, {})

    def test_bad_node_rejected(self):
        with self.assertRaises(ContractError):
            self.ingest(sample(node="N9"))

        self.assertEqual(self.db.values, {})

    def test_thirty_day_old_backfill_is_accepted(self):
        result = ingest_verified_packet(
            self.db,
            sample(),
            now_ms=NOW + 30 * 86_400_000,
        )

        self.assertEqual(
            result["history"], "CONFIRMED"
        )

    def test_partial_failure_retry_recovers_latest(self):
        p = sample()

        self.db.fail_once_path = (
            "hardware_test/nodes/N0/latest"
        )

        with self.assertRaises(ConnectionError):
            self.ingest(p)

        self.assertEqual(len(self.db.values), 1)

        self.ingest(p)
        self.assertEqual(len(self.db.values), 2)

    def test_bad_preexisting_latest_not_overwritten(self):
        path = "hardware_test/nodes/N0/latest"

        self.db.values[path] = {
            "timestamp": "bad"
        }

        with self.assertRaises(LatestConflict):
            self.ingest(sample())

        self.assertEqual(
            self.db.values[path],
            {"timestamp": "bad"},
        )

    def test_same_slot_concurrent_conflict(self):
        first = sample()

        second = sample(
            ts=TS + 1000,
            seq=8,
        )

        def writer(packet):
            try:
                return self.ingest(packet)
            except HistoryConflict:
                return "CONFLICT"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(
                    writer,
                    (first, second),
                )
            )

        self.assertEqual(
            sum(
                item == "CONFLICT"
                for item in outcomes
            ),
            1,
        )

        self.assertEqual(len(self.db.values), 2)


if __name__ == "__main__":
    unittest.main()
