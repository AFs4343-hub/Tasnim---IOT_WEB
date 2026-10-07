from __future__ import annotations

import math
from typing import Any

SLOT_MS = 300_000
NODE_IDS = {"N0", "N1", "N2"}


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def canonical_slot_ms(timestamp_ms: int | float) -> int:
    if not _number(timestamp_ms):
        raise ValueError("timestamp harus angka finite")

    timestamp_ms = int(timestamp_ms)

    if timestamp_ms <= 0:
        raise ValueError("timestamp harus > 0")

    return (timestamp_ms // SLOT_MS) * SLOT_MS


def validate_node_id(node_id: str) -> bool:
    return node_id in NODE_IDS


def validate_storage_packet(packet: dict[str, Any]) -> list[str]:
    """
    Memeriksa apakah packet boleh disimpan ke FIELD.

    Turbidity / RSSI / sequence boleh tidak tersedia.
    """
    errors: list[str] = []

    for key in ("ph", "tds", "timestamp"):
        if key not in packet:
            errors.append(f"{key}:missing")

    ph = packet.get("ph")
    if ph is not None:
        if not _number(ph):
            errors.append("ph:not_numeric")
        elif not 0 <= float(ph) <= 14:
            errors.append("ph:out_of_range")

    tds = packet.get("tds")
    if tds is not None:
        if not _number(tds):
            errors.append("tds:not_numeric")
        elif float(tds) < 0:
            errors.append("tds:negative")

    timestamp = packet.get("timestamp")
    if timestamp is not None:
        if not _number(timestamp):
            errors.append("timestamp:not_numeric")
        elif float(timestamp) <= 0:
            errors.append("timestamp:invalid")

    if "turbidity" in packet:
        turbidity = packet["turbidity"]

        if turbidity is None:
            errors.append("turbidity:null_should_be_omitted")
        elif not _number(turbidity):
            errors.append("turbidity:not_numeric")
        elif float(turbidity) < 0:
            errors.append("turbidity:negative")

    if "sequence" in packet:
        sequence = packet["sequence"]

        if not _number(sequence):
            errors.append("sequence:not_numeric")
        elif float(sequence) < 0:
            errors.append("sequence:negative")

    if "rssi" in packet:
        if not _number(packet["rssi"]):
            errors.append("rssi:not_numeric")

    return errors


def is_ai_analyzable(packet: dict[str, Any]) -> bool:
    if validate_storage_packet(packet):
        return False

    turbidity = packet.get("turbidity")

    return (
        _number(turbidity)
        and float(turbidity) >= 0
    )


def validate_location(location: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    lat = location.get("latitude")
    lng = location.get("longitude")

    if not _number(lat):
        errors.append("latitude:invalid")
    elif not -90 <= float(lat) <= 90:
        errors.append("latitude:out_of_range")

    if not _number(lng):
        errors.append("longitude:invalid")
    elif not -180 <= float(lng) <= 180:
        errors.append("longitude:out_of_range")

    if "captured_timestamp" in location:
        timestamp = location["captured_timestamp"]

        if not _number(timestamp) or float(timestamp) <= 0:
            errors.append("captured_timestamp:invalid")

    return errors
