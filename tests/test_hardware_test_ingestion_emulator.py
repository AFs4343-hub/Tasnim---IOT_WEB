"""Integration tests for the real TASNIM ingestion core on RTDB Emulator ONLY.

Run with firebase emulators:exec --project demo-tasnim-security.
No service account credentials and no Firebase production access.
This suite uses the SAME ingest_verified_packet function as the offline tests.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor

import firebase_admin
from firebase_admin import db

from iot.hardware_test_contract_v2 import ContractError
from iot.hardware_test_ingestion_core import (
    HistoryConflict,
    LatestConflict,
    ingest_verified_packet,
)

EMULATOR_HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
NAMESPACE = "demo-tasnim-security-default-rtdb"
EMULATOR_URL = f"http://{EMULATOR_HOST}/?ns={NAMESPACE}"

TS = 1_791_724_501_000
DAY_MS = 86_400_000
NOW_MS = TS + 40 * DAY_MS
SLOT = str((TS // 300_000) * 300_000)


def expected_in_rtdb(packet):
    """RTDB does not preserve an empty array-valued property."""
    result = dict(packet)
    if result.get("quality_flags") == []:
        result.pop("quality_flags")
    return result


def sample(node="N0", ts=TS, seq=3, **overrides):
    result = {
        "schema_version": 2,
        "node_id": node,
        "sample_id": f"{node}_{ts}_{seq}",
        "timestamp": ts,
        "sequence": seq,
        "ph": 7.2,
        "tds": 240.0,
        "turbidity": 16.0,
        "rssi": -49,
        "quality_flags": [],
    }
    result.update(overrides)
    return result


class FailLatestOnce:
    """Fail between the two real RTDB transactions (fault injection)."""

    def __init__(self, real_database):
        self.database = real_database
        self.failed = False

    def reference(self, path):
        original = self.database.reference(path)
        if path != "hardware_test/nodes/N0/latest" or self.failed:
            return original

        parent = self

        class FaultReference:
            def transaction(self, callback):
                parent.failed = True
                raise ConnectionError("injected failure before latest transaction")

        return FaultReference()


class IngestionOnRealEmulatorTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if os.environ.get("FIREBASE_DATABASE_EMULATOR_HOST") != EMULATOR_HOST:
            raise RuntimeError(
                "REFUSED: FIREBASE_DATABASE_EMULATOR_HOST must be "
                + EMULATOR_HOST
            )
        if os.environ.get("GCLOUD_PROJECT") != PROJECT:
            raise RuntimeError("REFUSED: GCLOUD_PROJECT must be " + PROJECT)

        # Explicit HTTP localhost URL + demo namespace. No production fallback.
        cls.app = firebase_admin.initialize_app(
            options={
                "projectId": PROJECT,
                "databaseURL": EMULATOR_URL,
                "httpTimeout": 15,
            },
            name="tasnim-ingestion-emulator-tests",
        )
        print("\n[SAFE] Python Admin SDK: localhost demo namespace only")

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        # Only the synthetic demo database is cleaned between test cases.
        db.reference("hardware_test", app=self.app).delete()

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def ingest(self, packet, adapter=None):
        if adapter is None:
            adapter = _AppDatabase(self.app)
        return ingest_verified_packet(adapter, packet, now_ms=NOW_MS)

    def test_01_initial_history_and_latest(self):
        packet = sample()
        result = self.ingest(packet)
        self.assertEqual(result["history"], "CONFIRMED")
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(packet))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(packet))

    def test_02_identical_retry_is_idempotent(self):
        packet = sample()
        self.ingest(packet)
        self.ingest(dict(packet))
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(packet))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(packet))

    def test_03_old_replay_preserves_newer_latest(self):
        newer = sample(ts=TS + 300_000, seq=5)
        older = sample()
        self.ingest(newer)
        result = self.ingest(older)
        self.assertEqual(result["latest"], "OLDER_REPLAY_PRESERVED")
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(older))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(newer))

    def test_04_conflict_same_slot_does_not_overwrite(self):
        first = sample()
        competing = sample(ts=TS + 1_000, seq=8)
        self.ingest(first)
        with self.assertRaises(HistoryConflict):
            self.ingest(competing)
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(first))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(first))

    def test_05_conflict_same_timestamp_different_value(self):
        first = sample()
        self.ingest(first)
        with self.assertRaises(HistoryConflict):
            self.ingest(sample(ph=8.8))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(first))

    def test_06_partial_failure_recovers_on_retry(self):
        packet = sample()
        faulty = FailLatestOnce(_AppDatabase(self.app))
        with self.assertRaises(ConnectionError):
            self.ingest(packet, adapter=faulty)
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(packet))
        self.assertIsNone(self.read("hardware_test/nodes/N0/latest"))
        self.ingest(packet)
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), expected_in_rtdb(packet))

    def test_07_concurrent_collision_has_single_winner(self):
        first = sample()
        competing = sample(ts=TS + 1_000, seq=8)

        def write(packet):
            try:
                self.ingest(packet)
                return "SAVED"
            except HistoryConflict:
                return "CONFLICT"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, (first, competing)))
        self.assertCountEqual(results, ["SAVED", "CONFLICT"])
        stored = self.read(f"hardware_test/history/{SLOT}/N0")
        self.assertIn(stored, (expected_in_rtdb(first), expected_in_rtdb(competing)))
        self.assertEqual(self.read("hardware_test/nodes/N0/latest"), stored)

    def test_08_three_nodes_same_slot(self):
        for node in ("N0", "N1", "N2"):
            self.ingest(sample(node=node))
        history = self.read(f"hardware_test/history/{SLOT}")
        self.assertEqual(set(history), {"N0", "N1", "N2"})

    def test_09_invalid_ph_diagnostic_preserved(self):
        packet = sample(node="N2", quality_flags=["PH_INVALID"])
        del packet["ph"]
        self.ingest(packet)
        stored = self.read(f"hardware_test/history/{SLOT}/N2")
        self.assertNotIn("ph", stored)
        self.assertEqual(stored["quality_flags"], ["PH_INVALID"])

    def test_10_invalid_future_timestamp_rejected(self):
        with self.assertRaises(ContractError):
            self.ingest(sample(ts=NOW_MS + 120_000))
        self.assertIsNone(self.read("hardware_test"))

    def test_11_unknown_field_rejected(self):
        with self.assertRaises(ContractError):
            self.ingest(sample(secret_field="not_permitted"))
        self.assertIsNone(self.read("hardware_test"))

    def test_12_bad_existing_latest_preserved(self):
        path = "hardware_test/nodes/N0/latest"
        db.reference(path, app=self.app).set({"timestamp": "corrupt"})
        with self.assertRaises(LatestConflict):
            self.ingest(sample())
        self.assertEqual(self.read(path), {"timestamp": "corrupt"})

    def test_14_newer_corrupt_latest_is_not_trusted_during_backfill(self):
        path = "hardware_test/nodes/N0/latest"
        for mutation in (
            {"node_id": "N2"},
            {"ph": -42},
            {"schema_version": 99},
            {"unexpected_meta": "bogus"},
            {"timestamp": NOW_MS + 120_000},
        ):
            with self.subTest(mutation=mutation):
                corrupt = sample(ts=TS + 300_000, seq=4)
                corrupt.update(mutation)
                db.reference(path, app=self.app).set(corrupt)
                with self.assertRaises(LatestConflict):
                    self.ingest(sample())
                self.assertEqual(self.read(path), expected_in_rtdb(corrupt))

    def test_13_old_backfill_after_40_days(self):
        packet = sample()
        result = self.ingest(packet)
        self.assertEqual(result["history"], "CONFIRMED")
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), expected_in_rtdb(packet))


class _AppDatabase:
    """Adapter matching ingestion_core's reference(path) contract."""

    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


if __name__ == "__main__":
    unittest.main()
