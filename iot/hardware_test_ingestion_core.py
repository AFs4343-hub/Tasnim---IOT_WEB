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

    slot = check_ingestion_packet(
        packet,
        now_ms=now_ms,
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

    if history != packet:
        raise HistoryConflict(
            f"history_conflict:{node}:{slot}"
        )

    def latest_update(old):
        if old is None:
            return dict(packet)

        if (
            not isinstance(old, dict)
            or type(old.get("timestamp")) is not int
        ):
            return old

        if packet["timestamp"] > old["timestamp"]:
            return dict(packet)

        return old

    latest = db.reference(latest_path).transaction(
        latest_update
    )

    if latest == packet:
        state = "LATEST_CONFIRMED"

    elif (
        isinstance(latest, dict)
        and type(latest.get("timestamp")) is int
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
