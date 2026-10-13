"""Offline tests: safe delete with trash backup, deletion list and restore."""
import unittest

from fake_rtdb import FakeRtdb
from iot.hardware_test_csv_import import build_import
from iot.hardware_test_delete import (
    DeleteError, apply_delete, is_deleted, list_batches, load_deleted_ranges,
    plan_delete, restore,
)
from iot.hardware_test_history_recorder import record_once

S = 1_791_811_800_000  # slot 12/10 21:30 WITA
NOW = S + 3_600_000


def node(n, slot, **extra):
    base = {"node_id": n, "timestamp": slot + 1000, "sequence": 1, "ph": 7.2,
            "tds": 210.0, "turbidity": 8.0, "quality_flags": ["BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED"]}
    base.update(extra)
    return base


def seeded():
    history = {}
    for k in range(4):
        slot = S + k * 300_000
        history[str(slot)] = {n: node(n, slot) for n in ("N0", "N1", "N2")}
        history[str(slot)]["analysis"] = {"status": "NORMAL", "source_timestamp_ms": slot}
    latest = history[str(S + 900_000)]["analysis"]
    return FakeRtdb({"hardware_test": {
        "history": history, "analysis": {"latest": latest},
        "nodes": {"N0": {"latest": {"timestamp": 1}}},
    }})


class DeleteTests(unittest.TestCase):
    def test_plan_is_read_only(self):
        db = seeded()
        plan = plan_delete(db, S, S + 300_000)
        self.assertEqual(plan["count"], {"slot": 2, "node": 6, "analysis": 2})
        self.assertEqual(db.writes, [])

    def test_whole_slot_delete_backs_up_first_and_repairs_latest(self):
        db = seeded()
        plan = plan_delete(db, S + 600_000, S + 900_000 + 299_999)
        result = apply_delete(db, plan, "uji coba", now_ms=NOW, batch_id="b1")
        history = db.get_path(["hardware_test", "history"])
        self.assertEqual(sorted(history), [str(S), str(S + 300_000)])
        trash = db.get_path(["tasnim_trash", "b1"])
        self.assertEqual(sorted(trash["items"]), [str(S + 600_000), str(S + 900_000)])
        self.assertEqual(db.writes[0][0], "tasnim_trash/b1")  # cadangan ditulis paling awal
        latest = db.get_path(["hardware_test", "analysis", "latest"])
        self.assertEqual(latest["source_timestamp_ms"], S + 300_000)
        self.assertIn("diganti", result["latest_analysis"])
        self.assertEqual(db.get_path(["hardware_test", "nodes"]), {"N0": {"latest": {"timestamp": 1}}})

    def test_node_only_delete_keeps_other_nodes_and_drops_slot_analysis(self):
        db = seeded()
        plan = plan_delete(db, S, S, ["N1"])
        apply_delete(db, plan, "sensor terangkat", now_ms=NOW, batch_id="b2")
        slot = db.get_path(["hardware_test", "history", str(S)])
        self.assertEqual(sorted(slot), ["N0", "N2"])

    def test_reason_required_and_bad_range_rejected(self):
        db = seeded()
        with self.assertRaises(DeleteError):
            apply_delete(db, plan_delete(db, S, S), "")
        with self.assertRaises(DeleteError):
            plan_delete(db, S + 1, S)
        with self.assertRaises(DeleteError):
            plan_delete(db, S, S, ["N9"])

    def test_deleted_range_blocks_csv_import_and_live_recorder(self):
        db = seeded()
        apply_delete(db, plan_delete(db, S, S + 300_000, ["N0"]), "uji coba",
                     now_ms=NOW, batch_id="b3")
        ranges = load_deleted_ranges(db)
        self.assertTrue(is_deleted(ranges, S + 300_000, "N0"))
        self.assertFalse(is_deleted(ranges, S + 300_000, "N1"))
        self.assertFalse(is_deleted(ranges, S + 600_000, "N0"))
        readings = [{"node": "N0", "timestamp": S + 5000, "sequence": 1, "ph": 7.1, "tds": 1, "turbidity": 1},
                    {"node": "N1", "timestamp": S + 5000, "sequence": 1, "ph": 7.1, "tds": 1, "turbidity": 1}]
        imported = build_import(readings, now_ms=NOW, deleted_ranges=ranges)
        self.assertEqual(imported["stats"]["excluded_deleted"], 1)
        self.assertEqual(list(imported["history"][str(S)]), ["N1"])
        db.set_path(["hardware_test", "nodes", "N0", "latest"],
                    {"ph": 7.1, "tds": 1, "turbidity": 1, "timestamp": S + 7000, "sequence": 9})
        out = record_once(db, now_ms=NOW, write=True, deleted_ranges=ranges)
        self.assertEqual(out["N0"][0], "DELETED_RANGE")
        self.assertNotIn("N0", db.get_path(["hardware_test", "history", str(S)]))

    def test_empty_range_is_still_listed_to_block_future_imports(self):
        db = seeded()
        far = S + 10 * 86_400_000
        apply_delete(db, plan_delete(db, far, far + 3_600_000), "jangan impor", now_ms=NOW, batch_id="b4")
        self.assertTrue(is_deleted(load_deleted_ranges(db), far + 300_000, "N2"))

    def test_restore_returns_data_without_overwriting_and_lifts_range(self):
        db = seeded()
        apply_delete(db, plan_delete(db, S, S + 300_000), "uji coba", now_ms=NOW, batch_id="b5")
        # Sementara itu slot S terisi data baru N0 (mis. dari impor lain).
        db.set_path(["hardware_test", "history", str(S), "N0"], {"timestamp": S + 2, "ph": 6.0})
        result = restore(db, "b5")
        self.assertEqual(result["skipped_existing"], 1)
        self.assertEqual(db.get_path(["hardware_test", "history", str(S), "N0", "ph"]), 6.0)
        self.assertEqual(db.get_path(["hardware_test", "history", str(S), "N1", "ph"]), 7.2)
        self.assertEqual(load_deleted_ranges(db), [])
        self.assertEqual(list_batches(db)[0]["status"], "dipulihkan")
        latest = db.get_path(["hardware_test", "analysis", "latest"])
        self.assertEqual(latest["source_timestamp_ms"], S + 900_000)
        with self.assertRaises(DeleteError):
            restore(db, "tidak-ada")


if __name__ == "__main__":
    unittest.main()
