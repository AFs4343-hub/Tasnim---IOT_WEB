"""Smoke-test REAL bundled model with synthetic hardware V2 histories.

This is a local inference compatibility check, NOT scientific validation and
NOT a Firebase write. Requires the existing trained prototype bundle.
"""
import unittest

from ai.predict import predict_latest
from ai.realtime_inference import load_model
from ai.hardware_test_preview_v2 import preview_pending
from ai.hardware_test_analysis_writer_v2 import prepare_analysis_record

S0 = 1_791_724_500_000
STEP = 300_000


def synthetic_history():
    data = {}
    for tick in range(4):
        slot = S0 + STEP * tick
        data[str(slot)] = {}
        for i, node in enumerate(("N0", "N1", "N2")):
            data[str(slot)][node] = {
                "schema_version": 2,
                "node_id": node,
                "sample_id": f"{node}_{slot+1000}_1",
                "timestamp": slot+1000,
                "sequence": tick+1,
                "ph": 7.1+i*0.12 + tick*0.01,
                "tds": 180+i*20+tick*0.5,
                "turbidity": 9+i*1.1+tick*0.15,
            }
    return data


class RealModelV2PreviewSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_model()

    def test_real_model_predicts_v2_history_without_network(self):
        history = synthetic_history()
        preview = preview_pending(
            history, session_id="SYNTHETIC_SMOKE_ONLY",
            model_bundle=self.bundle,
            predict_fn=predict_latest,
        )
        self.assertEqual(len(preview["plan"]["rows"]), 4)
        self.assertEqual(len(preview["predictions"]), 3)
        last = preview["predictions"][str(S0+3*STEP)]
        self.assertEqual(last["data_source"], "HARDWARE_TEST")
        self.assertEqual(last["model_stage"], "PROTOTYPE_SIMULATION")
        self.assertEqual(last["time_mode"], "ACTUAL_TIMESTAMP")
        self.assertIn("random_forest", last)
        self.assertIn("isolation_forest", last)
        self.assertIn("dominant_zscore", last)
        self.assertIs(type(last["model_disagreement"]), bool)
        self.assertEqual(last["session_id"], "SYNTHETIC_SMOKE_ONLY")
        self.assertNotIn("analysis", history[str(S0+3*STEP)])

    def test_real_model_preview_can_form_canonical_record(self):
        preview = preview_pending(
            synthetic_history(), session_id="SYNTHETIC_SMOKE_ONLY",
            model_bundle=self.bundle, predict_fn=predict_latest,
        )
        slot = S0+STEP
        record = prepare_analysis_record(
            preview["predictions"][str(slot)],
            model_version="prototype-v1",
            inference_timestamp_ms=S0+600_000,
        )
        self.assertEqual(record["source_timestamp_ms"], slot)
        self.assertEqual(record["model_version"], "prototype-v1")
        self.assertNotIn("location", record) if preview["predictions"][str(slot)].get("location") is None else self.assertIn("location", record)


if __name__ == "__main__":
    unittest.main()
