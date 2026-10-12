"""Read-only, offline planner for TASNIM /hardware_test/history V2.

No credentials, network, Firebase writes, model loading or production changes.
The returned plan is a candidate for prototype inference, not scientific proof.
"""

from ai.check_ai_readiness import audit_slot
from iot.hardware_test_contract_v2 import (
    ContractError, SLOT_MS, validate_measurement,
)

NODE_ORDER = ("N0", "N1", "N2")
SENSORS = ("ph", "tds", "turbidity")


def _normalized_for_validation(stored_packet):
    """RTDB omits empty quality_flags arrays; normalize a COPY only."""
    if not isinstance(stored_packet, dict):
        raise ContractError("packet:not_object")
    result = dict(stored_packet)
    if "quality_flags" not in result:
        result["quality_flags"] = []
    return result


def prepare_backlog(history, *, session_id):
    """Return valid model rows, pending slots, warmup and skip reasons.

    Only records with 3 V2 nodes in the correct 5-minute slot are eligible.
    The earliest eligible row is retained as temporal context, not predicted.
    `analysis` is considered complete only when it's a dict; this is a
    provisional marker contract that still requires backend versioning.
    """
    if not isinstance(history, dict):
        raise ValueError("history:expected_object")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id:required_by_caller")
    if len(session_id) > 80:
        raise ValueError("session_id:too_long")

    rows = []
    skipped = {}
    for raw_key, slot_record in history.items():
        key = str(raw_key)
        try:
            slot = int(key)
            if key != str(slot) or slot <= 0 or slot % SLOT_MS != 0:
                raise ValueError
        except (TypeError, ValueError):
            skipped[key] = ["INVALID_SLOT_KEY"]
            continue

        reasons = audit_slot(key, slot_record)
        if reasons:
            skipped[key] = reasons
            continue

        feature_values = {}
        for node in NODE_ORDER:
            packet = _normalized_for_validation(slot_record[node])
            try:
                packet_slot = validate_measurement(packet)
            except ContractError as exc:
                reasons.append(f"{node}:V2_CONTRACT:{exc}")
                continue
            if packet_slot != slot:
                reasons.append(f"{node}:V2_SLOT_MISMATCH")
                continue
            for sensor in SENSORS:
                feature_values[f"{sensor}_{node}"] = float(packet[sensor])

        if reasons:
            skipped[key] = reasons
            continue

        row = {
            "source_timestamp_ms": slot,
            "session_id": session_id,
            "has_analysis": isinstance(slot_record.get("analysis"), dict),
            **feature_values,
        }
        rows.append(row)

    rows.sort(key=lambda r: r["source_timestamp_ms"])
    warmup_slots = ([rows[0]["source_timestamp_ms"]] if rows else [])
    pending_timestamps = [
        row["source_timestamp_ms"]
        for row in rows[1:]
        if not row["has_analysis"]
    ]
    return {
        "rows": rows,
        "pending_timestamps": pending_timestamps,
        "warmup_slots": warmup_slots,
        "skipped": skipped,
        "time_mode": "ACTUAL_TIMESTAMP",
        "data_root": "hardware_test",
    }


def model_frame_for_slot(plan, target_timestamp):
    """Provide the legacy AI feature interface with preceding valid context.

    Does not invoke AI or touch Firebase. Raises when no prior valid slot.
    """
    if type(target_timestamp) is not int:
        raise ValueError("target_timestamp:invalid")
    records = [
        dict(row) for row in plan["rows"]
        if row["source_timestamp_ms"] <= target_timestamp
    ]
    if len(records) < 2 or records[-1]["source_timestamp_ms"] != target_timestamp:
        raise ValueError("target_requires_two_valid_context_slots")
    import pandas as pd
    frame = pd.DataFrame.from_records(records)
    frame["timestamp"] = pd.to_datetime(frame["source_timestamp_ms"], unit="ms")
    return frame
