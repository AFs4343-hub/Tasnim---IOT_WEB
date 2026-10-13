"""Offline tests: microSD CSV -> hardware_test history / website JSON."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fake_rtdb import FakeRtdb
from iot.hardware_test_csv_import import build_import, export_json, write_history
from iot.sd_csv import CsvFormatError, parse_sd_csv, parse_timestamp

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sd_csv"
NOW = 1_791_900_000_000


def load_fixture_readings():
    readings = []
    for name in ("tasnim_N0.csv", "tasnim_N1.csv", "tasnim_N2.csv"):
        rows, skipped = parse_sd_csv((FIXTURES / name).read_text(), file_name=name)
        readings.extend(rows)
    return readings


class CsvParseTests(unittest.TestCase):
    def test_firmware_header_and_na_turbidity(self):
        rows, skipped = parse_sd_csv(
            "timestamp,node,sequence,ph,tds,turbidity,rssi\n"
            "1791811802000,N0,1,7.43,0.0,NA,-52\n"
            "timestamp,node,sequence,ph,tds,turbidity,rssi\n"
            "bad,N0,2,7.4,1,1,-50\n", file_name="tasnim_N0.csv")
        self.assertEqual(len(rows), 1)
        self.assertNotIn("turbidity", rows[0])  # NA tetap hilang, bukan 0
        self.assertEqual(rows[0]["tds"], 0.0)
        self.assertEqual(skipped, [{"line": 4, "reason": "TIMESTAMP_INVALID"}])

    def test_excel_semicolon_decimal_comma_and_node_from_filename(self):
        rows, _ = parse_sd_csv("waktu;pH;TDS (ppm);Turbidity\n"
                               "2026-10-12 08:30:00;7,10;1.890,8;12,5\n",
                               file_name="log_n2.csv")
        self.assertEqual(rows[0]["node"], "N2")
        self.assertEqual(rows[0]["ph"], 7.10)
        self.assertEqual(rows[0]["tds"], 1890.8)
        # tanpa zona waktu = WITA (UTC+8)
        self.assertEqual(rows[0]["timestamp"], parse_timestamp("2026-10-12T00:30:00Z"))

    def test_epoch_seconds_accepted_and_missing_columns_rejected(self):
        self.assertEqual(parse_timestamp("1791811802"), 1791811802000)
        self.assertIsNone(parse_timestamp("80"))
        with self.assertRaises(CsvFormatError):
            parse_sd_csv("ph,tds\n7,1\n")
        rows, skipped = parse_sd_csv("timestamp,ph\n1791811802000,7.1\n", file_name="x.csv")
        self.assertEqual(rows, [])
        self.assertEqual(skipped[0]["reason"], "NODE_UNKNOWN")


class CsvImportTests(unittest.TestCase):
    def test_first_sample_per_slot_and_complete_slots(self):
        imported = build_import(load_fixture_readings(), now_ms=NOW)
        stats = imported["stats"]
        self.assertEqual(stats["valid_rows"], 19)
        self.assertEqual(stats["slots"], 6)
        self.assertEqual(stats["extra_in_slot"], 1)
        first_slot = min(imported["history"], key=int)
        self.assertEqual(imported["history"][first_slot]["N0"]["sequence"], 1)
        self.assertEqual(stats["complete_slots"], 6)
        n1_missing = [rec["N1"] for rec in imported["history"].values()
                      if "turbidity" not in rec["N1"]]
        self.assertEqual(len(n1_missing), 1)
        self.assertIn("TURB_INVALID_OR_MISSING", n1_missing[0]["quality_flags"])

    def test_export_json_opens_in_website_shape(self):
        imported = build_import(load_fixture_readings(), now_ms=NOW)
        payload = export_json(imported)
        hw = payload["hardware_test"]
        self.assertEqual(sorted(hw["nodes"]), ["N0", "N1", "N2"])
        self.assertEqual(hw["nodes"]["N0"]["latest"]["sequence"], 7)
        self.assertEqual(list(hw["history"]), sorted(hw["history"], key=int))
        json.dumps(payload, allow_nan=False)

    def test_write_only_fills_empty_paths_and_never_touches_latest(self):
        imported = build_import(load_fixture_readings(), now_ms=NOW)
        slots = sorted(imported["history"], key=int)
        existing = {"N0": {"timestamp": int(slots[0]) + 1, "sequence": 99, "ph": 1.0}}
        db = FakeRtdb({"hardware_test": {
            "nodes": {"N0": {"latest": {"timestamp": 1}}},
            "history": {slots[0]: existing},
        }})
        outcome = write_history(db, imported["history"], now_ms=NOW, progress=lambda _m: None)
        self.assertEqual(outcome["already_present"], 1)
        self.assertEqual(outcome["captured"], 6 * 3 - 1)
        self.assertEqual(db.get_path(["hardware_test", "history", slots[0], "N0"]), existing["N0"])
        self.assertEqual(db.get_path(["hardware_test", "nodes"]), {"N0": {"latest": {"timestamp": 1}}})
        self.assertTrue(all(path.startswith("hardware_test/history") for path, _ in db.writes))
        again = write_history(db, imported["history"], now_ms=NOW, progress=lambda _m: None)
        self.assertEqual(again["already_present"], 18)

    def test_recent_slots_use_first_wins_transaction(self):
        imported = build_import(load_fixture_readings(), now_ms=NOW)
        last = max(imported["history"], key=int)
        db = FakeRtdb()
        with patch("iot.hardware_test_csv_import.store_packet", return_value="CAPTURED") as tx:
            write_history(db, {last: imported["history"][last]},
                          now_ms=int(last) + 60_000, progress=lambda _m: None)
        self.assertEqual(tx.call_count, 3)


if __name__ == "__main__":
    unittest.main()
