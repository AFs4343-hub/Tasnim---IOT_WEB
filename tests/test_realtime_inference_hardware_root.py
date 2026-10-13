"""Offline tests: AI reads hardware_test slot history (stub model, no Firebase)."""
import unittest
from unittest.mock import patch

from ai.check_ai_readiness import audit_slot
from ai.realtime_inference import build_analysis_result, history_to_frame

SLOT = 1_791_811_800_000
FLAGS_OK = ["BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED"]


def packet(node, slot, **extra):
    base = {"schema_version": 2, "node_id": node, "sequence": 1,
            "sample_id": f"{node}_{slot + 1000}_1", "timestamp": slot + 1000,
            "ph": 7.2, "tds": 210.0, "turbidity": 8.0, "quality_flags": FLAGS_OK}
    base.update(extra)
    return base


def history(slots):
    return {str(s): {n: packet(n, s) for n in ("N0", "N1", "N2")} for s in slots}


class HardwareRootFrameTests(unittest.TestCase):
    def test_slots_become_rows_with_gap_sessions(self):
        slots = [SLOT, SLOT + 300_000, SLOT + 600_000, SLOT + 86_400_000, SLOT + 86_700_000]
        df, pending, mode = history_to_frame(history(slots), "hardware_test", verbose=False)
        self.assertEqual(list(df["source_timestamp_ms"]), slots)
        self.assertEqual(pending, slots)
        self.assertEqual(mode, "ACTUAL_TIMESTAMP")
        self.assertEqual(df["session_id"].nunique(), 2)
        self.assertEqual(df["session_id"].iloc[0], f"HW_{SLOT}")
        self.assertEqual(df["session_id"].iloc[3], f"HW_{SLOT + 86_400_000}")

    def test_invalid_or_incomplete_slots_skipped_but_zero_warnings_allowed(self):
        data = history([SLOT, SLOT + 300_000, SLOT + 600_000, SLOT + 900_000])
        data[str(SLOT + 300_000)]["N1"] = packet(
            "N1", SLOT + 300_000, quality_flags=["PH_INVALID"])
        del data[str(SLOT + 300_000)]["N1"]["ph"]
        del data[str(SLOT + 600_000)]["N2"]
        data[str(SLOT + 900_000)]["N0"] = packet(
            "N0", SLOT + 900_000, tds=0, quality_flags=["TDS_ZERO_CHECK_CLAMP"])
        df, pending, _ = history_to_frame(data, "hardware_test", verbose=False)
        self.assertEqual(pending, [SLOT, SLOT + 900_000])
        # real_test tetap ketat seperti sebelumnya
        self.assertTrue(audit_slot(str(SLOT + 900_000), data[str(SLOT + 900_000)]))

    def test_already_analyzed_slot_not_pending_and_too_little_history(self):
        data = history([SLOT, SLOT + 300_000])
        data[str(SLOT)]["analysis"] = {"status": "NORMAL"}
        _, pending, _ = history_to_frame(data, "hardware_test", verbose=False)
        self.assertEqual(pending, [SLOT + 300_000])
        self.assertEqual(history_to_frame(history([SLOT]), "hardware_test"), (None, None, None))
        self.assertEqual(history_to_frame(None, "hardware_test"), (None, None, None))

    def test_result_labels_hardware_source_and_prototype_stage(self):
        df, _, mode = history_to_frame(history([SLOT, SLOT + 300_000]), "hardware_test",
                                       verbose=False)
        with patch("ai.realtime_inference.predict_latest",
                   return_value={"status": "NORMAL", "location": None}) as stub:
            result = build_analysis_result(df, SLOT + 300_000, mode, object(),
                                           "hardware_test", inference_timestamp_ms=5)
        self.assertEqual(len(stub.call_args.args[0]), 2)
        self.assertEqual(result["data_source"], "HARDWARE_TEST")
        self.assertEqual(result["model_stage"], "PROTOTYPE_SIMULATION")
        self.assertEqual(result["source_timestamp_ms"], SLOT + 300_000)
        self.assertEqual(result["location"], "-")


if __name__ == "__main__":
    unittest.main()
