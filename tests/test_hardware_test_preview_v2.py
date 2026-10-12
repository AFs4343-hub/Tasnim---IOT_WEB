"""Offline tests for V2 AI dry-run; injected fake model, zero Firebase writes."""
import unittest
from ai.hardware_test_preview_v2 import annotate_preview, preview_pending
from test_hardware_test_history_v2 import SLOT0, INTERVAL, slot


def fake_prediction(frame, bundle):
    return {
        "status": "NORMAL",
        "random_forest": {"prediction": bundle["rf"], "confidence": .53},
        "isolation_forest": {"is_anomaly": bundle["if"]},
        "sample_context_rows": len(frame),
        "session_id": str(frame.iloc[-1]["session_id"]),
    }


class AIHardwarePreviewTests(unittest.TestCase):
    def test_returns_pending_predictions_without_writing(self):
        history = {str(SLOT0 + INTERVAL): slot(SLOT0 + INTERVAL),
                   str(SLOT0): slot(SLOT0),
                   str(SLOT0 + 2*INTERVAL): slot(SLOT0 + 2*INTERVAL)}
        result = preview_pending(history, session_id="OFFLINE_SESSION",
                                 model_bundle={"rf": "NORMAL", "if": False},
                                 predict_fn=fake_prediction)
        self.assertEqual(len(result["predictions"]), 2)
        self.assertEqual([result["predictions"][str(t)]["sample_context_rows"]
                          for t in (SLOT0+INTERVAL, SLOT0+2*INTERVAL)], [2, 3])
        self.assertEqual(result["plan"]["warmup_slots"], [SLOT0])
        self.assertNotIn("analysis", history[str(SLOT0+INTERVAL)])

    def test_model_disagreement_flagged_without_relabeling(self):
        result = annotate_preview({
            "status": "NORMAL", "random_forest": {"prediction": "NORMAL", "confidence": 0.535},
            "isolation_forest": {"is_anomaly": True},
        }, slot=SLOT0, time_mode="ACTUAL_TIMESTAMP")
        self.assertTrue(result["model_disagreement"])
        self.assertEqual(result["interpretation"], "MODEL_REVIEW_REQUIRED")
        self.assertEqual(result["status"], "NORMAL")

    def test_invalid_sensor_excluded(self):
        history = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        del history[str(SLOT0+INTERVAL)]["N0"]["ph"]
        history[str(SLOT0+INTERVAL)]["N0"]["quality_flags"] = ["PH_INVALID"]
        result = preview_pending(history, session_id="OFFLINE_SESSION",
                                 model_bundle={"rf": "NORMAL", "if": False},
                                 predict_fn=fake_prediction)
        self.assertEqual(result["predictions"], {})
        self.assertIn(str(SLOT0+INTERVAL), result["plan"]["skipped"])

    def test_processed_analysis_not_predicted(self):
        history = {str(SLOT0): slot(SLOT0), str(SLOT0+INTERVAL): slot(SLOT0+INTERVAL)}
        history[str(SLOT0+INTERVAL)]["analysis"] = {"status": "NORMAL"}
        result = preview_pending(history, session_id="OFFLINE_SESSION",
                                 model_bundle={}, predict_fn=fake_prediction)
        self.assertEqual(result["predictions"], {})

    def test_reject_incomplete_model_output(self):
        with self.assertRaises(ValueError):
            annotate_preview({"status": "NORMAL"}, slot=SLOT0, time_mode="ACTUAL_TIMESTAMP")


if __name__ == "__main__":
    unittest.main()
