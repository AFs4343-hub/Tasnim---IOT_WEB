"""TASNIM candidate ingestion core.

No Firebase initialization and no network operations here.
Caller must authenticate and authorize the node first.
"""

import json
import time

from iot.hardware_test_contract_v2 import (
    ContractError,
    validate_measurement,
)

ROOT = "hardware_test"

ALLOWED_FIELDS = frozenset({
    "schema_version",
    "node_id",
    "sample_id",
    "timestamp",
    "sequence",
    "ph",
    "tds",
    "turbidity",
    "rssi",
    "quality_flags",
})

MAX_PAYLOAD_BYTES = 2048
MAX_FUTURE_MS = 60_000


class HistoryConflict(RuntimeError):
    pass


class LatestConflict(RuntimeError):
    pass


def stored_packet_matches(stored, packet):
    """Compare a stored RTDB measurement with a validated V2 packet.

    Realtime Database omits an empty array property. Consequently, a
    persisted valid packet with quality_flags=[] has no quality_flags key.
    Only this one documented representation is treated as equivalent.
    A nonempty flag list must remain present and match exactly.
    """
    if not isinstance(stored, dict):
        return False
    if stored == packet:
        return True
    if (
        packet.get("quality_flags") == []
        and "quality_flags" not in stored
    ):
        normalized = dict(stored)
        normalized["quality_flags"] = []
        return normalized == packet
    return False


def valid_stored_latest(stored, *, node, now_ms=None):
    """Stored pointer must pass the full V2 schema before trusting its clock.

    RTDB may omit only an empty quality_flags array. Structural validation
    does NOT prove the pointer equals archived history; that needs a separate
    provenance check. Never overwrite malformed latest data automatically.
    """
    if type(stored) is not dict or stored.get("node_id") != node:
        return False
    if set(stored) - ALLOWED_FIELDS:
        return False
    timestamp = stored.get("timestamp")
    if type(timestamp) is not int:
        return False
    if now_ms is not None and timestamp > now_ms + MAX_FUTURE_MS:
        return False
    restored = dict(stored)
    restored.setdefault("quality_flags", [])
    try:
        # Check the packet's structure and size; do not reject a historically
        # legitimate stored pointer because its acquisition clock is old.
        check_ingestion_packet(restored, now_ms=timestamp)
    except (ContractError, ValueError, OverflowError):
        return False
    return True


def check_ingestion_packet(packet, *, now_ms=None):
    """Validate canonical measurement before persistence."""

    if type(packet) is not dict:
        raise ContractError("packet:not_object")

    unknown = set(packet) - ALLOWED_FIELDS

    if unknown:
        raise ContractError(
            "packet:unknown_fields:" +
            ",".join(sorted(unknown))
        )

    flags = packet.get("quality_flags")

    if isinstance(flags, list) and len(flags) > 12:
        raise ContractError("quality_flags:too_many")

    try:
        encoded = json.dumps(
            packet,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContractError(
            "packet:non_json_value"
        ) from exc

    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ContractError("packet:too_large")

    slot = validate_measurement(packet)

    now = (
        int(time.time() * 1000)
        if now_ms is None
        else now_ms
    )

    if type(now) is not int or now < 0:
        raise ValueError("now_ms:invalid")

    if packet["timestamp"] > now + MAX_FUTURE_MS:
        raise ContractError(
            "timestamp:too_far_in_future"
        )

    return slot


def ingest_verified_packet(db, packet, *, now_ms=None):
    """Store history first, then update latest.

    db must expose reference(path).transaction(callback).

    Transactions are independent, not one atomic batch.
    Caller must verify device identity before calling.
    """

    reference_now = int(time.time() * 1000) if now_ms is None else now_ms
    slot = check_ingestion_packet(
        packet,
        now_ms=reference_now,
    )

    node = packet["node_id"]

    history_path = (
        f"{ROOT}/history/{slot}/{node}"
    )

    latest_path = (
        f"{ROOT}/nodes/{node}/latest"
    )

    # History is immutable once occupied.
    # Returning old preserves collisions without overwrite.
    history = db.reference(history_path).transaction(
        lambda old: dict(packet)
        if old is None
        else old
    )

    if not stored_packet_matches(history, packet):
        raise HistoryConflict(
            f"history_conflict:{node}:{slot}"
        )

    def latest_update(old):
        if old is None:
            return dict(packet)

        if not valid_stored_latest(old, node=node, now_ms=reference_now):
            return old

        if packet["timestamp"] > old["timestamp"]:
            return dict(packet)

        return old

    latest = db.reference(latest_path).transaction(
        latest_update
    )

    if stored_packet_matches(latest, packet):
        state = "LATEST_CONFIRMED"

    elif (
        valid_stored_latest(latest, node=node, now_ms=reference_now)
        and latest["timestamp"] > packet["timestamp"]
    ):
        state = "OLDER_REPLAY_PRESERVED"

    else:
        raise LatestConflict(
            f"latest_conflict:{node}"
        )

    return {
        "history": "CONFIRMED",
        "latest": state,
        "slot": slot,
        "node_id": node,
    }
