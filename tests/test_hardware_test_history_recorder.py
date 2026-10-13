"""Offline tests: latest -> immutable 5-minute history (no Firebase)."""
import unittest

from fake_rtdb import FakeRtdb
from iot.hardware_test_history_recorder import (
    packet_from_observation, record_once, store_packet,
)
from iot.hardware_test_legacy_history_capture_v1 import FieldCaptureRejected

# Bentuk persis dari screenshot Firebase alat (tanpa metadata V2).
LATEST = {
    "N0": {"ph": 7.43, "rssi": -52, "sequence": 2, "tds": 0,
           "timestamp": 1791811802000, "turbidity": 24},
    "N1": {"ph": 16.9, "rssi": -53, "sequence": 2, "tds": 0,
           "timestamp": 1791813601000, "turbidity": 39.5},
    "N2": {"ph": 4.96, "rssi": -53, "sequence": 1, "tds": 1890.8,
           "timestamp": 1791813908000, "turbidity": 0},
}
NOW = 1791814000000


def nodes_tree(latest):
    return {"hardware_test": {"nodes": {n: {"latest": v} for n, v in latest.items()}}}


class RecorderTests(unittest.TestCase):
    def test_dry_run_never_writes(self):
        db = FakeRtdb(nodes_tree(LATEST))
        out = record_once(db, now_ms=NOW, write=False)
        self.assertEqual({k: v[0] for k, v in out.items()}, dict.fromkeys(LATEST, "WOULD_CAPTURE"))
        self.assertEqual(db.writes, [])

    def test_write_archives_each_node_in_its_slot_and_keeps_latest(self):
        db = FakeRtdb(nodes_tree(LATEST))
        before = db.get_path(["hardware_test", "nodes"])
        out = record_once(db, now_ms=NOW, write=True)
        self.assertEqual({k: v[0] for k, v in out.items()}, dict.fromkeys(LATEST, "CAPTURED"))
        self.assertEqual(db.get_path(["hardware_test", "nodes"]), before)
        for node, raw in LATEST.items():
            slot = raw["timestamp"] // 300000 * 300000
            stored = db.get_path(["hardware_test", "history", str(slot), node])
            self.assertEqual(stored["timestamp"], raw["timestamp"])
            self.assertEqual(stored["node_id"], node)
        n1 = db.get_path(["hardware_test", "history",
                          str(LATEST["N1"]["timestamp"] // 300000 * 300000), "N1"])
        self.assertNotIn("ph", n1)  # pH 16.9 tidak dijadikan angka palsu
        self.assertIn("PH_INVALID", n1["quality_flags"])

    def test_repeat_poll_is_noop_and_new_sample_in_same_slot_does_not_overwrite(self):
        db = FakeRtdb(nodes_tree(LATEST))
        seen = {}
        record_once(db, now_ms=NOW, write=True, seen=seen)
        writes = len(db.writes)
        again = record_once(db, now_ms=NOW, write=True, seen=seen)
        self.assertEqual({v[0] for v in again.values()}, {"UNCHANGED"})
        self.assertEqual(len(db.writes), writes)
        # Firmware mengirim lagi 5 detik kemudian di slot yang sama.
        newer = dict(LATEST["N0"], timestamp=LATEST["N0"]["timestamp"] + 5000, sequence=3, ph=7.5)
        db.set_path(["hardware_test", "nodes", "N0", "latest"], newer)
        out = record_once(db, now_ms=NOW, write=True, seen=seen)
        self.assertEqual(out["N0"][0], "SLOT_TAKEN")
        slot = LATEST["N0"]["timestamp"] // 300000 * 300000
        self.assertEqual(db.get_path(["hardware_test", "history", str(slot), "N0", "ph"]), 7.43)

    def test_identical_retry_is_duplicate(self):
        db = FakeRtdb()
        packet, slot = packet_from_observation(LATEST["N2"], "N2", now_ms=NOW)
        self.assertEqual(store_packet(db, slot, "N2", packet), "CAPTURED")
        self.assertEqual(store_packet(db, slot, "N2", packet), "DUPLICATE")

    def test_bad_clock_or_node_rejected(self):
        with self.assertRaises(FieldCaptureRejected):
            packet_from_observation(dict(LATEST["N0"], timestamp=NOW + 3_600_000), "N0", now_ms=NOW)
        with self.assertRaises(FieldCaptureRejected):
            packet_from_observation(dict(LATEST["N0"], node_id="N1"), "N0", now_ms=NOW)
        db = FakeRtdb(nodes_tree({"N0": dict(LATEST["N0"], timestamp=123)}))
        out = record_once(db, now_ms=NOW, write=True)
        self.assertEqual(out["N0"][0], "REVIEW_REQUIRED")
        self.assertEqual(out["N1"][0], "NO_DATA")
        self.assertEqual(db.writes, [])

    def test_float_epoch_and_missing_sequence_for_csv(self):
        raw = {"timestamp": float(LATEST["N0"]["timestamp"]), "ph": 7.1, "tds": 100.0,
               "turbidity": 5.0}
        with self.assertRaises(FieldCaptureRejected):
            packet_from_observation(raw, "N0", now_ms=NOW)
        packet, _ = packet_from_observation(raw, "N0", now_ms=NOW, allow_missing_sequence=True)
        self.assertEqual(packet["timestamp"], LATEST["N0"]["timestamp"])
        self.assertEqual(packet["sequence"], 0)


if __name__ == "__main__":
    unittest.main()
