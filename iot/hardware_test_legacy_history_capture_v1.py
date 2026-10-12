"""Migrate observed legacy ESP32 latest readings to canonical V2 history.

This bridge is PROTOTYPE EMULATOR-ONLY. No Firebase client initialization,
production URL, credential load, LIVE writes, or changes to existing latest.
Only measurements observed while a capture is running can be archived.
Historical missed observations require original microSD CSVs.
"""
from __future__ import annotations

import os
import time

from iot.hardware_test_contract_v2 import NODE_IDS, SLOT_MS, MIN_TIMESTAMP_MS
from iot.hardware_test_ingestion_core import (
    check_ingestion_packet, stored_packet_matches, HistoryConflict,
    MAX_FUTURE_MS,
)

ROOT = "hardware_test"
DEMO_PROJECT = "demo-tasnim-security"
DEMO_HOST = "127.0.0.1:19003"


class FieldCaptureRejected(ValueError):
    pass


def _measurement(raw, key, low, high, flags, *, upper_inclusive=True):
    x = raw.get(key)
    valid = (type(x) in (int, float) and x == x
             and low <= x <= high if upper_inclusive else
             type(x) in (int, float) and x == x and low <= x < high)
    if not valid:
        flags.append({
            "ph": "PH_INVALID",
            "tds": "TDS_INVALID",
            "turbidity": "TURB_INVALID_OR_MISSING",
        }[key])
        return None
    if key == "tds" and x == 0:
        flags.append("TDS_ZERO_CHECK_CLAMP")
    if key == "turbidity" and x == 0:
        flags.append("TURB_ZERO_VERIFY")
    return x


def normalize_legacy_observation(raw, node, *, now_ms):
    """Map exactly one real/latest snapshot to a canonical immutable slot.

    Never invent measurements or pretend calibration proved accuracy.
    """
    if node not in NODE_IDS or type(raw) is not dict:
        raise FieldCaptureRejected("field_history:invalid_node_or_payload")
    ts, seq = raw.get("timestamp"), raw.get("sequence")
    if (type(ts) is not int or ts < MIN_TIMESTAMP_MS
            or ts > now_ms + MAX_FUTURE_MS
            or type(seq) is not int or seq < 0
            or (raw.get("node_id") is not None and raw["node_id"] != node)):
        raise FieldCaptureRejected("field_history:invalid_timestamp_sequence_or_node")
    flags = []
    packet = {
        "schema_version": 2, "node_id": node,
        "sample_id": f"{node}_{ts}_{seq}",
        "timestamp": ts, "sequence": seq,
    }
    for key, high in (("ph", 14), ("tds", 5000), ("turbidity", 3000)):
        value = _measurement(
            raw, key, 0, high, flags,
            upper_inclusive=key != "turbidity",
        )
        if value is not None:
            packet[key] = value
    rssi = raw.get("rssi")
    if type(rssi) in (int, float) and rssi == rssi and abs(rssi) <= 200:
        packet["rssi"] = rssi
    packet["quality_flags"] = flags or ["BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED"]
    slot = check_ingestion_packet(packet, now_ms=now_ms)
    return packet, slot


def require_demo_history_capture(db):
    # Never touch database until runtime and adapter identity checked.
    if (os.getenv("TASNIM_FIELD_HISTORY_EMULATOR_ONLY") != "YES"
            or os.getenv("GCLOUD_PROJECT") != DEMO_PROJECT
            or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != DEMO_HOST
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or getattr(db, "emulator_only", None) is not True
            or getattr(db, "emulator_project", None) != DEMO_PROJECT
            or getattr(db, "emulator_host", None) != DEMO_HOST):
        raise RuntimeError("REFUSED: history capture requires localhost demo Emulator")


def capture_latest_as_history(db, *, now_ms=None, dry_run=True):
    """Capture one observed batch of N0/N1/N2 to immutable Emulator history.

    With dry_run=True, never write. In write mode, refuses to overwrite a
    different measurement from the same node in the same 5-minute slot.
    """
    require_demo_history_capture(db)
    if type(dry_run) is not bool:
        raise ValueError("field_history:invalid_dry_run")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    if type(now) is not int or now < MIN_TIMESTAMP_MS:
        raise ValueError("field_history:invalid_now")
    outcomes = {}
    for node in ("N0", "N1", "N2"):
        raw = db.reference(f"{ROOT}/nodes/{node}/latest").get()
        if raw is None:
            outcomes[node] = "NO_DATA"
            continue
        try:
            packet, slot = normalize_legacy_observation(raw, node, now_ms=now)
        except (FieldCaptureRejected, ValueError):
            outcomes[node] = "REVIEW_REQUIRED"
            continue
        if dry_run:
            outcomes[node] = "READY_TO_CAPTURE"
            continue
        ref = db.reference(f"{ROOT}/history/{slot}/{node}")
        previous = ref.transaction(lambda old: packet if old is None else old)
        if not stored_packet_matches(previous, packet):
            outcomes[node] = "SLOT_CONFLICT"
            continue
        outcomes[node] = "CAPTURED"
    return {"dry_run": dry_run, "nodes": outcomes, "source": ROOT}
