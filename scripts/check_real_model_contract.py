#!/usr/bin/env python3
"""Offline, READ-ONLY smoke test of the locally trusted prototype RF/IF bundle.

Model loading via joblib executes Python object deserialization. Only load the
file already built by THIS research team; never accept a downloaded stranger's
bundle. No Firebase, no model training, no file writes, no field-accuracy claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "ai/models/tasnim_ai_bundle.joblib"
START_MS = 1791724500000
SLOT_MS = 300000


def guard_local_model():
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("REFUSED: run model smoke from repository root")
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                            text=True, capture_output=True, check=True).stdout.strip()
    if branch != "infra/field-data":
        raise RuntimeError("REFUSED: non-candidate branch")
    cfg = json.loads((ROOT / "tasnim.config.json").read_text())
    if cfg != {"activeDataRoot": "simulation", "mode": "SIMULATION"}:
        raise RuntimeError("REFUSED: changed website data mode")
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        raise RuntimeError("REFUSED: service-account credentials must be absent")
    if not MODEL_PATH.is_file() or MODEL_PATH.is_symlink():
        raise RuntimeError("REFUSED: local trusted model file missing or symlink")
    if MODEL_PATH.stat().st_size > 150_000_000:
        raise RuntimeError("REFUSED: unexpectedly large model file")


def synthetic_history():
    """Four static 5-min slots; no device, Firebase or external dataset."""
    history = {}
    for tick in range(4):
        slot = START_MS + tick * SLOT_MS
        packets = {}
        for i, node in enumerate(("N0", "N1", "N2")):
            packets[node] = {
                "schema_version": 2,
                "node_id": node,
                "sample_id": f"{node}_{slot+1000}_1",
                "timestamp": slot + 1000,
                "sequence": tick + 1,
                "ph": 7.1 + i * 0.12 + tick * 0.01,
                "tds": 180 + i * 20 + tick * 0.5,
                "turbidity": 9 + i * 1.1 + tick * 0.15,
            }
        history[str(slot)] = packets
    return history


def check_bundle(bundle, predict_fn):
    """Contract check without leaking inference values or writing files."""
    from ai.hardware_test_analysis_writer_v2 import prepare_analysis_record
    from ai.hardware_test_preview_v2 import preview_pending

    def once():
        return preview_pending(
            synthetic_history(), session_id="SYNTHETIC_MODEL_SMOKE_ONLY",
            model_bundle=bundle, predict_fn=predict_fn,
            expected_model_version="prototype-v1",
        )

    first = once()
    second = once()
    if first["predictions"] != second["predictions"]:
        raise ValueError("model_smoke:nondeterministic_predictions")
    if len(first["predictions"]) != 3 or len(first["plan"]["rows"]) != 4:
        raise ValueError("model_smoke:unexpected_slot_count")
    for key, item in first["predictions"].items():
        slot = int(key)
        rec = prepare_analysis_record(
            item, model_version="prototype-v1",
            inference_timestamp_ms=START_MS + 2_000_000,
        )
        if (rec["source_timestamp_ms"] != slot
                or rec["data_source"] != "HARDWARE_TEST"
                or rec["model_stage"] != "PROTOTYPE_SIMULATION"
                or rec["time_mode"] != "ACTUAL_TIMESTAMP"):
            raise ValueError("model_smoke:invalid_provenance")
    return {
        "contract": "PASS",
        "data_source": "SYNTHETIC_OFFLINE_ONLY",
        "model_stage": "PROTOTYPE_SIMULATION",
        "validated_slots": 3,
        "repeatability": "DETERMINISTIC_ON_STATIC_INPUT",
        "firebase_reads": 0,
        "firebase_writes": 0,
        "field_accuracy_tested": False,
    }


def main():
    parser = argparse.ArgumentParser(description="TASNIM trusted local model compatibility")
    parser.add_argument("--check", required=True, action="store_true",
                        help="read-only, local prototype RF/IF smoke test")
    args = parser.parse_args()
    guard_local_model()
    # Import only after all guards. joblib deserialization is trusted-local only.
    import joblib
    from ai.predict import predict_latest
    artifact_digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12]
    bundle = joblib.load(MODEL_PATH)
    result = check_bundle(bundle, predict_latest)
    result["model_file_sha256_prefix"] = artifact_digest
    print(json.dumps(result, sort_keys=True))
    print("[SAFE] No Firebase usage or file writes. No field-validity claim.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print("[STOP] Real-model smoke refused/failed:", type(exc).__name__)
        raise SystemExit(2)
