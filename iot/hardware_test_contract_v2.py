"""Offline V2 candidate validation. No Firebase access or firmware changes."""
import math
import re

SLOT_MS = 300_000
NODE_IDS = frozenset(("N0", "N1", "N2"))
MIN_TIMESTAMP_MS = 1_704_067_200_000  # 2024-01-01 UTC
MISSING_FLAGS = {
    "ph": {"PH_INVALID"},
    "tds": {"TDS_INVALID"},
    "turbidity": {"TURB_INVALID_OR_MISSING", "TURB_SATURATED"},
}


class ContractError(ValueError):
    pass


def is_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_measurement(packet):
    """Return 5-minute slot; invalid-sensor omissions need explicit flags."""
    if not isinstance(packet, dict):
        raise ContractError("packet:not_object")
    if type(packet.get("schema_version")) is not int or packet["schema_version"] != 2:
        raise ContractError("schema_version:expected_2")
    node = packet.get("node_id")
    if not isinstance(node, str) or node not in NODE_IDS:
        raise ContractError("node_id:invalid")
    ts = packet.get("timestamp")
    if type(ts) is not int or ts < MIN_TIMESTAMP_MS:
        raise ContractError("timestamp:invalid_ms")
    seq = packet.get("sequence")
    if type(seq) is not int or seq < 0:
        raise ContractError("sequence:invalid")
    sample_id = packet.get("sample_id")
    if (not isinstance(sample_id, str) or
            not re.fullmatch(rf"{node}_[A-Za-z0-9_-]{{1,80}}", sample_id)):
        raise ContractError("sample_id:invalid_or_wrong_node")
    flags = packet.get("quality_flags")
    if (not isinstance(flags, list) or any(
        not isinstance(f, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", f)
        for f in flags
    ) or len(set(flags)) != len(flags)):
        raise ContractError("quality_flags:invalid")
    for sensor, high in (("ph", 14), ("tds", 5000), ("turbidity", 3000)):
        if sensor not in packet:
            if not (MISSING_FLAGS[sensor] & set(flags)):
                raise ContractError(f"{sensor}:missing_without_flag")
            continue
        value = packet[sensor]
        if not is_number(value) or value < 0 or value > high or (
            sensor == "turbidity" and value == high
        ):
            raise ContractError(f"{sensor}:invalid_value_omit_and_flag")
    if "rssi" in packet and not is_number(packet["rssi"]):
        raise ContractError("rssi:invalid")
    return (ts // SLOT_MS) * SLOT_MS


def store_history_in_memory(store, packet):
    """Offline reference logic, NOT atomic Firebase implementation."""
    slot = validate_measurement(packet)
    key = f'hardware_test/history/{slot}/{packet["node_id"]}'
    if key not in store:
        store[key] = dict(packet)
        return "INSERTED"
    if store[key] == packet:
        return "DUPLICATE_NOOP"
    return "CONFLICT_NO_OVERWRITE"


def advance_latest_in_memory(store, packet):
    """Offline reference logic, NOT atomic Firebase implementation."""
    validate_measurement(packet)
    key = f'hardware_test/nodes/{packet["node_id"]}/latest'
    old = store.get(key)
    if old is None:
        store[key] = dict(packet)
        return "UPDATED"
    old_ts = old.get("timestamp")
    if type(old_ts) is not int:
        return "CONFLICT_BAD_EXISTING"
    if packet["timestamp"] < old_ts:
        return "OLDER_NOOP"
    if packet["timestamp"] == old_ts:
        return "DUPLICATE_NOOP" if old == packet else "CONFLICT_NO_OVERWRITE"
    store[key] = dict(packet)
    return "UPDATED"
