"""Pure offline checks for real-model smoke runner (bundle not present in CI)."""
import os
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_real_model_contract as smoke
from test_hardware_test_worker_v2 import prediction


class ModelSmokeContractTests(unittest.TestCase):
    def test_mock_prediction_validates_four_synthetic_slots_without_writes(self):
        result = smoke.check_bundle(None, prediction)
        self.assertEqual(result["contract"], "PASS")
        self.assertEqual(result["validated_slots"], 3)
        self.assertEqual(result["firebase_reads"], 0)
        self.assertEqual(result["firebase_writes"], 0)
        self.assertIs(result["field_accuracy_tested"], False)

    def test_python_script_import_succeeds_without_pythonpath(self):
        # -I ignores PYTHONPATH and cwd imports. This reproduces the
        # Codespaces ModuleNotFoundError without loading any model artifact.
        source = (
            "import importlib.util, sys; "
            f"path={str(ROOT / 'scripts/check_real_model_contract.py')!r}; "
            "spec=importlib.util.spec_from_file_location('model_smoke_script',path); "
            "module=importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(module); "
            "assert callable(module.load_local_predictor())"
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-I", "-c", source],
            cwd=ROOT, env=env, capture_output=True, text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_nondeterministic_predictor_fails_instead_of_claiming_validation(self):
        calls = [0]
        def unstable(frame, bundle):
            calls[0] += 1
            value = prediction(frame, bundle)
            value["random_forest"]["confidence"] = 0.5 if calls[0] < 4 else 0.9
            return value
        with self.assertRaisesRegex(ValueError, "nondeterministic"):
            smoke.check_bundle(None, unstable)

    def test_invalid_predictor_contract_fails(self):
        def broken(frame, bundle):
            return {"status": "NORMAL", "random_forest": {}, "isolation_forest": {}}
        with self.assertRaises(ValueError):
            smoke.check_bundle(None, broken)

    def test_untrusted_model_path_and_credentials_refused_before_deserialize(self):
        with patch.object(smoke, "MODEL_PATH", ROOT / "missing-model.joblib"):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                smoke.guard_local_model()
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/private"}):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                smoke.guard_local_model()

    def test_branch_and_data_configuration_guard(self):
        with patch.object(smoke, "ROOT", Path("/tmp/not-the-repository")):
            with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                smoke.guard_local_model()


if __name__ == "__main__":
    unittest.main()
