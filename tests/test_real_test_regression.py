"""TASNIM offline regression tests.

Synthetic fixtures only. No Firebase initialization or writes.
"""

import unittest
from copy import deepcopy
from unittest.mock import patch

from ai.check_ai_readiness import audit_slot
from iot.real_test_bridge_v2 import normalize
import ai.realtime_inference as ai


BASE = 1791637200000
NODES = ("N0", "N1", "N2")


def make_history(count=12):
    history = {}

    for i in range(count):
        ts = BASE + i * 300000
        record = {
            "meta": {"session_id": "OFFLINE_TEST_ONLY"}
        }

        for n, node in enumerate(NODES):
            record[node] = {
                "timestamp": ts + 5000,
                "ph": round(7 + n * 0.12 + i * 0.01, 3),
                "tds": float(150 + n * 20 + i),
                "turbidity": float(8 + n * 2 + i * 0.2),
                "quality_flags": [],
                "sequence": i + 1,
                "rssi": -60,
            }

        history[str(ts)] = record

    return history


class FakeReference:
    def __init__(self, path, history):
        self.path = path
        self.history = history

    def order_by_key(self):
        return self

    def limit_to_last(self, limit):
        return self

    def get(self):
        assert self.path == "real_test/history"
        return self.history

    def set(self, value):
        raise AssertionError(
            f"DRY-RUN ATTEMPTED FIREBASE WRITE: {self.path}"
        )


class TestTasnimRegression(unittest.TestCase):

    def test_01_complete_slot_is_candidate(self):
        history = make_history(1)
        key, record = next(iter(history.items()))

        self.assertEqual(audit_slot(key, record), [])

    def test_02_invalid_ph_is_rejected(self):
        history = make_history(1)
        key, record = next(iter(history.items()))

        record = deepcopy(record)
        record["N2"]["ph"] = None
        record["N2"]["quality_flags"] = ["PH_INVALID"]

        reasons = audit_slot(key, record)

        self.assertTrue(reasons)
        self.assertTrue(
            any("N2:" in reason for reason in reasons)
        )

    def test_03_bridge_rejects_stale_data(self):
        now = BASE + 300000

        raw = {
            "timestamp": BASE,
            "ph": 7.0,
            "tds": 150,
            "turbidity": 10,
        }

        packet, status = normalize(raw, "N0", now)

        self.assertIsNone(packet)
        self.assertTrue(status.startswith("STALE_"))

    def test_04_bridge_flags_missing_ph(self):
        now = BASE + 10000

        raw = {
            "timestamp": BASE + 5000,
            "ph": None,
            "tds": 107.8,
            "turbidity": 12.8,
        }

        packet, status = normalize(raw, "N2", now)

        self.assertEqual(status, "OK")
        self.assertIn(
            "PH_INVALID",
            packet["quality_flags"]
        )
        self.assertNotIn("ph", packet)

    def test_05_ai_dry_run_blocks_database_write(self):
        history = make_history(12)

        for key, record in history.items():
            self.assertEqual(audit_slot(key, record), [])

        model = ai.load_model()

        def fake_reference(path):
            return FakeReference(path, history)

        with patch.object(
            ai.db,
            "reference",
            side_effect=fake_reference
        ), patch.object(
            ai, "DATA_ROOT", "real_test"
        ), patch.object(
            ai, "DRY_RUN", True
        ):
            frame, pending, time_mode = (
                ai.load_recent_history(limit=12)
            )

            self.assertIsNotNone(frame)
            self.assertEqual(len(frame), 12)
            self.assertTrue(pending)

            target = int(
                frame["source_timestamp_ms"].max()
            )

            result = ai.process_pending_record(
                input_df=frame,
                target_timestamp=target,
                time_mode=time_mode,
                model_bundle=model,
                write_latest=True,
            )

            self.assertIsInstance(
                result["random_forest"], dict
            )
            self.assertIsInstance(
                result["isolation_forest"], dict
            )
            self.assertEqual(
                result["data_source"], "REAL_TEST"
            )
            self.assertEqual(
                result["model_stage"],
                "PROTOTYPE_SIMULATION"
            )


if __name__ == "__main__":
    unittest.main()
