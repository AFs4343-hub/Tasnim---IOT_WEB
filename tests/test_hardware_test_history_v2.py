"""Offline, no model or database dependency for V2 history planning."""
import copy
import unittest
from test_hardware_test_analysis_writer_v2 import record as analysis_record
from ai.hardware_test_history_v2 import prepare_backlog, model_frame_for_slot

SLOT0 = 1_791_724_500_000
INTERVAL = 300_000


def packet(node, slot, flags=True):
    row = {
        "schema_version": 2, "node_id": node,
        "sample_id": f"{node}_{slot+1000}_1",
        "timestamp": slot + 1000, "sequence": 1,
        "ph": 7.1, "tds": 212, "turbidity": 10.2,
        "rssi": -58,
    }
    if flags:
        row["quality_flags"] = []
    return row


def slot(slot_ms, *, omit_empty_flags=False):
    return {node: packet(node, slot_ms, not omit_empty_flags)
            for node in ("N0", "N1", "N2")}


class HardwareTestHistoryPlannerTests(unittest.TestCase):
    def plan(self, history, session_id="OFFLINE_TEST_SESSION"):
        return prepare_backlog(history, session_id=session_id)

    def test_complete_history_sorted_and_pending(self):
        h = {str(SLOT0 + 2*INTERVAL): slot(SLOT0 + 2*INTERVAL),
             str(SLOT0): slot(SLOT0),
             str(SLOT0 + INTERVAL): slot(SLOT0 + INTERVAL)}
        p = self.plan(h)
        self.assertEqual([r["source_timestamp_ms"] for r in p["rows"]],
                         [SLOT0, SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertEqual(p["pending_timestamps"], [SLOT0+INTERVAL, SLOT0+2*INTERVAL])
        self.assertEqual(p["warmup_slots"], [SLOT0])

    def test_empty_flags_missing_as_rtdb_form(self):
        p = self.plan({str(SLOT0): slot(SLOT0, omit_empty_flags=True)})
        self.assertEqual(len(p["rows"]), 1)
        self.assertFalse(p["skipped"])

    def test_no_mutation_of_input_when_normalizing(self):
        history = {str(SLOT0): slot(SLOT0, omit_empty_flags=True)}
        before = copy.deepcopy(history)
        self.plan(history)
        self.assertEqual(history, before)

    def test_incomplete_node_is_skipped(self):
        h = slot(SLOT0)
        del h["N2"]
        p = self.plan({str(SLOT0): h})
        self.assertEqual(p["rows"], [])
        self.assertTrue(any("N2:MISSING" == x for x in p["skipped"][str(SLOT0)]))

    def test_invalid_ph_flagged_is_not_ai_ready(self):
        h = slot(SLOT0)
        del h["N2"]["ph"]
        h["N2"]["quality_flags"] = ["PH_INVALID"]
        p = self.plan({str(SLOT0): h})
        self.assertEqual(p["rows"], [])
        self.assertIn(str(SLOT0), p["skipped"])

    def test_wrong_v2_node_id_rejected(self):
        h = slot(SLOT0)
        h["N1"]["node_id"] = "N0"
        p = self.plan({str(SLOT0): h})
        self.assertTrue(any("V2_CONTRACT" in s for s in p["skipped"][str(SLOT0)]))

    def test_sensor_above_contract_range_rejected(self):
        h = slot(SLOT0)
        h["N0"]["tds"] = 9999
        p = self.plan({str(SLOT0): h})
        self.assertTrue(any("V2_CONTRACT" in s for s in p["skipped"][str(SLOT0)]))

    def test_bad_slot_name_rejected(self):
        p = self.plan({"not-a-slot": slot(SLOT0), str(SLOT0+1): slot(SLOT0)})
        self.assertEqual(len(p["skipped"]), 2)

    def test_processed_analysis_is_not_pending(self):
        h = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        h[str(SLOT0+INTERVAL)]["analysis"] = {"status": "NORMAL"}
        p = self.plan(h)
        self.assertEqual(p["pending_timestamps"], [])
        self.assertEqual(len(p["rows"]), 2)

    def test_versioned_checkpoint_matching_record_is_complete(self):
        h = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        marker = analysis_record(SLOT0+INTERVAL)
        marker["session_id"] = "OFFLINE_TEST_SESSION"
        h[str(SLOT0+INTERVAL)]["analysis"] = marker
        plan = prepare_backlog(
            h, session_id="OFFLINE_TEST_SESSION",
            expected_model_version="prototype-v1",
        )
        self.assertEqual(plan["pending_timestamps"], [])
        self.assertEqual(plan["blocked_analyses"], {})

    def test_wrong_model_version_blocks_review_not_recompute(self):
        h = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        h[str(SLOT0+INTERVAL)]["analysis"] = analysis_record(SLOT0+INTERVAL)
        plan = prepare_backlog(
            h, session_id="OFFLINE_SESSION",
            expected_model_version="prototype-v2",
        )
        self.assertEqual(plan["pending_timestamps"], [])
        self.assertIn(str(SLOT0+INTERVAL), plan["blocked_analyses"])

    def test_incomplete_or_nonobject_checkpoint_blocks_review(self):
        for marker in ({"status": "NORMAL"}, "corrupt", {}):
            with self.subTest(marker=marker):
                h = {str(SLOT0): slot(SLOT0),
                     str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
                h[str(SLOT0+INTERVAL)]["analysis"] = marker
                plan = prepare_backlog(
                    h, session_id="OFFLINE_TEST_SESSION",
                    expected_model_version="prototype-v1",
                )
                self.assertEqual(plan["pending_timestamps"], [])
                self.assertIn(str(SLOT0+INTERVAL), plan["blocked_analyses"])

    def test_versioned_new_slot_remains_pending(self):
        h = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        plan = prepare_backlog(
            h, session_id="OFFLINE_TEST_SESSION",
            expected_model_version="prototype-v1",
        )
        self.assertEqual(plan["pending_timestamps"], [SLOT0+INTERVAL])
        self.assertEqual(plan["blocked_analyses"], {})

    def test_invalid_expected_model_version_rejected(self):
        with self.assertRaises(ValueError):
            prepare_backlog({}, session_id="OFFLINE_TEST_SESSION",
                            expected_model_version=" ")

    def test_only_one_slot_is_warmup(self):
        p = self.plan({str(SLOT0): slot(SLOT0)})
        self.assertEqual(p["pending_timestamps"], [])
        self.assertEqual(p["warmup_slots"], [SLOT0])

    def test_model_frame_uses_actual_time_and_history(self):
        h = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        p = self.plan(h)
        frame = model_frame_for_slot(p, SLOT0+INTERVAL)
        self.assertEqual(len(frame), 2)
        self.assertEqual(
            (frame.iloc[1]["timestamp"] - frame.iloc[0]["timestamp"]).total_seconds(), 300
        )
        self.assertIn("ph_N2", frame)
        self.assertIn("session_id", frame)
        self.assertEqual(p["time_mode"], "ACTUAL_TIMESTAMP")

    def test_model_frame_requires_context(self):
        p = self.plan({str(SLOT0): slot(SLOT0)})
        with self.assertRaises(ValueError):
            model_frame_for_slot(p, SLOT0)

    def test_requires_explicit_session(self):
        with self.assertRaises(ValueError):
            self.plan({str(SLOT0): slot(SLOT0)}, session_id=" ")

    def test_blank_history_is_valid_empty(self):
        p = self.plan({})
        self.assertEqual(p["rows"], [])
        self.assertEqual(p["skipped"], {})

    def test_disagreement_quality_flag_rejected(self):
        h = slot(SLOT0)
        h["N0"]["quality_flags"] = ["UNREVIEWED"]
        p = self.plan({str(SLOT0): h})
        self.assertTrue(p["skipped"][str(SLOT0)])


if __name__ == "__main__":
    unittest.main()
