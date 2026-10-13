"""Offline tests for legacy N0/N1/N2 latest -> V2 history capture.

All inputs correspond to user-shared Firebase screenshots, no real Firebase
connection. The capture is Emulator-only and NEVER writes nodes/latest.
"""
import copy
import os
import unittest
from threading import RLock
from unittest.mock import patch

from iot.hardware_test_legacy_history_capture_v1 import (
    capture_latest_as_history, normalize_legacy_observation,
    require_demo_history_capture, FieldCaptureRejected,
)
from iot.hardware_test_contract_v2 import validate_measurement

NOW = 1791815000000
LATEST = {
    "N0": dict(ph=7.43, rssi=-52, sequence=2, tds=0,
               timestamp=1791811802000, turbidity=24),
    "N1": dict(ph=16.9, rssi=-53, sequence=2, tds=0,
               timestamp=1791813601000, turbidity=39.5),
    "N2": dict(ph=4.96, rssi=-53, sequence=1, tds=1890.8,
               timestamp=1791813908000, turbidity=0),
}


class MemDB:
    emulator_only = True
    emulator_project = "demo-tasnim-security"
    emulator_host = "127.0.0.1:19003"

    def __init__(self):
        self.values = {
            f"hardware_test/nodes/{n}/latest": copy.deepcopy(value)
            for n, value in LATEST.items()
        }
        self.lock = RLock()
        self.reads = 0

    def reference(self, path):
        parent = self
        class Ref:
            def get(self):
                parent.reads += 1
                return copy.deepcopy(parent.values.get(path))
            def transaction(self, fn):
                with parent.lock:
                    result = fn(copy.deepcopy(parent.values.get(path)))
                    parent.values[path] = copy.deepcopy(result)
                    return copy.deepcopy(result)
        return Ref()


class FieldLatestHistoryTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "TASNIM_FIELD_HISTORY_EMULATOR_ONLY": "YES",
            "GCLOUD_PROJECT": "demo-tasnim-security",
            "FIREBASE_DATABASE_EMULATOR_HOST": "127.0.0.1:19003",
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.db = MemDB()

    def test_screenshot_raw_records_become_valid_flagged_v2_packets(self):
        for node in ("N0", "N1", "N2"):
            record, slot = normalize_legacy_observation(LATEST[node], node, now_ms=NOW)
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["node_id"], node)
            self.assertEqual(record["sample_id"],
                             f"{node}_{LATEST[node]['timestamp']}_{LATEST[node]['sequence']}")
            self.assertEqual(validate_measurement(record), slot)
        bad, _ = normalize_legacy_observation(LATEST["N1"], "N1", now_ms=NOW)
        self.assertNotIn("ph", bad)
        self.assertIn("PH_INVALID", bad["quality_flags"])
        self.assertIn("TDS_ZERO_CHECK_CLAMP", bad["quality_flags"])
        zero, _ = normalize_legacy_observation(LATEST["N2"], "N2", now_ms=NOW)
        self.assertIn("TURB_ZERO_VERIFY", zero["quality_flags"])
        self.assertEqual(zero["tds"], 1890.8)

    def test_read_only_preview_makes_no_history(self):
        before = copy.deepcopy(self.db.values)
        result = capture_latest_as_history(self.db, dry_run=True, now_ms=NOW)
        self.assertEqual(result["nodes"], dict.fromkeys(LATEST, "READY_TO_CAPTURE"))
        self.assertEqual(self.db.values, before)

    def test_capture_once_and_retry_are_immutable_and_idempotent(self):
        originals = copy.deepcopy(self.db.values)
        first = capture_latest_as_history(self.db, dry_run=False, now_ms=NOW)
        self.assertEqual(first["nodes"], dict.fromkeys(LATEST, "CAPTURED"))
        self.assertEqual(len(self.db.values), 6)
        for node, original in LATEST.items():
            slot = original["timestamp"] // 300000 * 300000
            self.assertEqual(self.db.values[f"hardware_test/nodes/{node}/latest"],
                             originals[f"hardware_test/nodes/{node}/latest"])
            self.assertIn(f"hardware_test/history/{slot}/{node}", self.db.values)
        before = copy.deepcopy(self.db.values)
        again = capture_latest_as_history(self.db, dry_run=False, now_ms=NOW)
        self.assertEqual(again["nodes"], dict.fromkeys(LATEST, "CAPTURED"))
        self.assertEqual(self.db.values, before)

    def test_second_distinct_sample_same_slot_does_not_overwrite(self):
        capture_latest_as_history(self.db, dry_run=False, now_ms=NOW)
        slot = LATEST["N0"]["timestamp"] // 300000 * 300000
        path = f"hardware_test/history/{slot}/N0"
        original = copy.deepcopy(self.db.values[path])
        self.db.values["hardware_test/nodes/N0/latest"]["ph"] = 7.98
        result = capture_latest_as_history(self.db, dry_run=False, now_ms=NOW)
        self.assertEqual(result["nodes"]["N0"], "SLOT_CONFLICT")
        self.assertEqual(self.db.values[path], original)

    def test_future_timestamp_refused_without_history_write(self):
        self.db.values["hardware_test/nodes/N2/latest"]["timestamp"] = NOW + 120000
        result = capture_latest_as_history(self.db, dry_run=False, now_ms=NOW)
        self.assertEqual(result["nodes"]["N2"], "REVIEW_REQUIRED")
        self.assertEqual(sum(k.startswith("hardware_test/history/")
                             for k in self.db.values), 2)

    def test_invalid_or_missing_values_never_converted_to_fake_zero(self):
        invalid = {**LATEST["N1"], "ph": "16.9", "tds": None,
                   "turbidity": -2}
        packet, _ = normalize_legacy_observation(invalid, "N1", now_ms=NOW)
        for sensor in ("ph", "tds", "turbidity"):
            self.assertNotIn(sensor, packet)
        self.assertIn("TDS_INVALID", packet["quality_flags"])
        for bad in ({**LATEST["N0"], "timestamp": NOW+300000},
                    {**LATEST["N0"], "sequence": "2"}):
            with self.assertRaises(FieldCaptureRejected):
                normalize_legacy_observation(bad, "N0", now_ms=NOW)

    def test_production_identity_refused_before_any_database_read(self):
        for override in (
            {"GCLOUD_PROJECT": "real-prod-project"},
            {"FIREBASE_DATABASE_EMULATOR_HOST": "real-db.invalid"},
            {"TASNIM_FIELD_HISTORY_EMULATOR_ONLY": "NO"},
            {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/real.json"},
        ):
            with self.subTest(override=override), patch.dict(os.environ, override):
                with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                    capture_latest_as_history(self.db, now_ms=NOW, dry_run=False)
        self.assertEqual(self.db.reads, 0)
        self.assertEqual(len(self.db.values), 3)


if __name__ == "__main__":
    unittest.main()
