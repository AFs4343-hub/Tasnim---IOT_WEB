"""Candidate AI analysis persistence for TASNIM hardware_test (no Firebase init).

The caller is responsible for authenticating as trusted backend, verifying
that its source slot is still the validated three-node snapshot and supplying
a stable record across retries. This module never connects to a database by
itself, and is NOT authorized for LIVE use.
"""
import json
from iot.hardware_test_contract_v2 import SLOT_MS

ROOT = "hardware_test"
MAX_ANALYSIS_BYTES = 16_384
ALLOWED_KEYS = frozenset({
    "source_timestamp_ms", "session_id", "model_version",
    "model_stage", "data_source", "time_mode", "status",
    "location", "random_forest", "isolation_forest",
    "dominant_zscore", "model_disagreement", "interpretation",
    "timestamp", "inference_timestamp_ms",
})


class AnalysisConflict(RuntimeError):
    pass


class AnalysisLatestConflict(RuntimeError):
    pass


def _clean(value):
    """Drop RTDB-unsupported null/empty collections without altering inputs."""
    if value is None:
        return None
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("analysis:non_string_key")
            normalized = _clean(item)
            if normalized is not None and normalized != {} and normalized != []:
                result[key] = normalized
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            normalized = _clean(item)
            if normalized is not None and normalized != {} and normalized != []:
                result.append(normalized)
        return result
    if type(value) not in (str, int, float, bool):
        raise ValueError("analysis:unsupported_type")
    return value


def prepare_analysis_record(preview, *, model_version, inference_timestamp_ms):
    """Convert validated preview into a stable RTDB-compatible record.

    The exact returned record MUST be retried. Do not regenerate an inference
    timestamp or rerun a nondeterministic model when replaying a partial write.
    """
    if type(preview) is not dict:
        raise ValueError("analysis:expected_object")
    unknown = set(preview) - ALLOWED_KEYS
    if unknown:
        raise ValueError("analysis:unknown_fields:" + ",".join(sorted(unknown)))
    slot = preview.get("source_timestamp_ms")
    if type(slot) is not int or slot <= 0 or slot % SLOT_MS:
        raise ValueError("analysis:invalid_slot")
    if not isinstance(model_version, str) or not model_version.strip() or len(model_version) > 80:
        raise ValueError("analysis:invalid_model_version")
    if type(inference_timestamp_ms) is not int or inference_timestamp_ms <= 0:
        raise ValueError("analysis:invalid_inference_timestamp")

    required_str = {
        "session_id", "data_source", "model_stage",
        "time_mode", "status", "interpretation",
    }
    for key in required_str:
        if not isinstance(preview.get(key), str) or not preview[key].strip():
            raise ValueError("analysis:missing_" + key)
    if len(preview["session_id"]) > 80:
        raise ValueError("analysis:session_too_long")
    if preview["data_source"] != "HARDWARE_TEST":
        raise ValueError("analysis:wrong_source")
    if preview["model_stage"] != "PROTOTYPE_SIMULATION":
        raise ValueError("analysis:wrong_model_stage")
    if preview["time_mode"] != "ACTUAL_TIMESTAMP":
        raise ValueError("analysis:wrong_time_mode")
    if preview["status"] not in ("NORMAL", "ANOMALI"):
        raise ValueError("analysis:invalid_status")
    if type(preview.get("model_disagreement")) is not bool:
        raise ValueError("analysis:missing_disagreement")
    if not isinstance(preview.get("random_forest"), dict):
        raise ValueError("analysis:missing_rf")
    if not isinstance(preview.get("isolation_forest"), dict):
        raise ValueError("analysis:missing_if")
    if not isinstance(preview.get("dominant_zscore"), dict):
        raise ValueError("analysis:missing_zscore")

    record = {k: v for k, v in preview.items() if k in ALLOWED_KEYS}
    record["model_version"] = model_version
    record["inference_timestamp_ms"] = inference_timestamp_ms
    record = _clean(record)
    try:
        serialized = json.dumps(record, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("analysis:invalid_json_values") from exc
    if len(serialized.encode("utf-8")) > MAX_ANALYSIS_BYTES:
        raise ValueError("analysis:too_large")
    return record


def commit_verified_analysis(db, record):
    """Transactionally archive one analysis and monotonically advance latest.

    `db` supplies reference(path).transaction(callback). Transactions are
    individually atomic, but NOT a single two-path atomic transaction.
    Caller MUST verify the underlying N0/N1/N2 history and authorization.
    """
    if type(record) is not dict:
        raise ValueError("analysis:invalid_record")
    canonical_preview = {
        key: value for key, value in record.items()
        if key not in ("model_version", "inference_timestamp_ms")
    }
    canonical = prepare_analysis_record(
        canonical_preview,
        model_version=record.get("model_version"),
        inference_timestamp_ms=record.get("inference_timestamp_ms"),
    )
    if canonical != record:
        raise ValueError("analysis:record_not_canonical")
    slot = record.get("source_timestamp_ms")
    if type(slot) is not int or slot <= 0 or slot % SLOT_MS:
        raise ValueError("analysis:invalid_slot")

    history_path = f"{ROOT}/history/{slot}/analysis"
    latest_path = f"{ROOT}/analysis/latest"
    stored = db.reference(history_path).transaction(
        lambda previous: dict(record) if previous is None else previous
    )
    if stored != record:
        raise AnalysisConflict("analysis_history_conflict:" + str(slot))

    def update_latest(previous):
        if previous is None:
            return dict(record)
        if not isinstance(previous, dict) or type(previous.get("source_timestamp_ms")) is not int:
            return previous
        if previous["source_timestamp_ms"] < slot:
            return dict(record)
        return previous

    current = db.reference(latest_path).transaction(update_latest)
    if current == record:
        state = "LATEST_CONFIRMED"
    elif (
        isinstance(current, dict)
        and type(current.get("source_timestamp_ms")) is int
        and current["source_timestamp_ms"] > slot
    ):
        state = "OLDER_ANALYSIS_PRESERVED"
    else:
        raise AnalysisLatestConflict("analysis_latest_conflict:" + str(slot))
    return {"history": "CONFIRMED", "latest": state, "slot": slot}
