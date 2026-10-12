"""Guarded, bounded operational status for the localhost TASNIM AI demo.

Only one small `latest` status is persisted; there is no infinite event log,
LIVE endpoint, browser write route, or model/sensor/credential serialization.
"""
from __future__ import annotations

from ai.hardware_test_worker_lease_v2 import _require_exclusive_demo

STATUS_PATH = "worker_state/ai_v2_supervisor/latest"
STATES = frozenset({
    "PROCESSED", "IDLE", "PREVIEW", "WAITING_LOCK",
    "REVIEW_REQUIRED", "RETRY_EXHAUSTED", "FAILED",
})
ERROR_CODES = frozenset({
    "NONE", "LEASE_BUSY", "REVIEW_REQUIRED",
    "SOURCE_CHANGED", "TRANSIENT_ERROR", "WORKER_ERROR",
})


def make_supervisor_status(*, state, timestamp_ms, attempts,
                           result=None, error_code="NONE"):
    """Produce a strict, bounded summary with no exception messages."""
    if state not in STATES or error_code not in ERROR_CODES:
        raise ValueError("supervisor_status:unknown_state_or_error")
    if type(timestamp_ms) is not int or timestamp_ms <= 0:
        raise ValueError("supervisor_status:invalid_timestamp")
    if type(attempts) is not int or not 0 <= attempts <= 3:
        raise ValueError("supervisor_status:invalid_attempts")

    result = result or {}
    if type(result) is not dict:
        raise ValueError("supervisor_status:invalid_result")
    counters = {}
    for key, field in (
        ("processed_count", "processed_slots"),
        ("recovered_count", "recovered_slots"),
        ("deferred_count", "deferred_slots"),
        ("would_process_count", "would_process_slots"),
    ):
        value = result.get(field, [])
        if type(value) is not list or len(value) > 5000:
            raise ValueError("supervisor_status:invalid_counter")
        counters[key] = len(value)

    return {
        "schema_version": 1,
        "state": state,
        "error_code": error_code,
        "timestamp_ms": timestamp_ms,
        "attempts": attempts,
        **counters,
        "source_root": "hardware_test",
        "model_stage": "PROTOTYPE_SIMULATION",
    }


def persist_supervisor_status(db, record):
    """Monotonically update one demo-only RTDB status via Admin transaction.

    Older completed cycles cannot replace newer ones. If the record has the
    same timestamp, a competing cycle cannot overwrite it with other content.
    """
    _require_exclusive_demo(db)
    if type(record) is not dict or set(record) != {
        "schema_version", "state", "error_code", "timestamp_ms", "attempts",
        "processed_count", "recovered_count", "deferred_count",
        "would_process_count", "source_root", "model_stage",
    }:
        raise ValueError("supervisor_status:unexpected_keys")
    canonical = make_supervisor_status(
        state=record["state"], timestamp_ms=record["timestamp_ms"],
        attempts=record["attempts"], error_code=record["error_code"],
        result={
            "processed_slots": [0] * record["processed_count"],
            "recovered_slots": [0] * record["recovered_count"],
            "deferred_slots": [0] * record["deferred_count"],
            "would_process_slots": [0] * record["would_process_count"],
        },
    )
    if canonical != record:
        raise ValueError("supervisor_status:not_canonical")

    def choose(previous):
        if previous is None:
            return dict(record)
        if (type(previous) is not dict
                or type(previous.get("timestamp_ms")) is not int):
            # Never overwrite corrupt status silently.
            return previous
        if previous["timestamp_ms"] < record["timestamp_ms"]:
            return dict(record)
        return previous

    stored = db.reference(STATUS_PATH).transaction(choose)
    return stored == record
