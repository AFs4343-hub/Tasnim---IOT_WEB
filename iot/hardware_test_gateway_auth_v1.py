"""TASNIM candidate signed-device request verifier (no HTTP server).

HMAC authenticates each node's EXACT request body to a trusted gateway.
Request time is current even for historical microSD samples.
Not deployable without HTTPS, secret management, rate limits, and nonce GC.
"""
import hashlib
import hmac
import json
import re
import time

from iot.hardware_test_ingestion_core import (
    MAX_PAYLOAD_BYTES, check_ingestion_packet, ingest_verified_packet,
)
from iot.hardware_test_contract_v2 import NODE_IDS

MAX_CLOCK_SKEW_MS = 300_000
NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,80}\Z")
HEX_SIGNATURE = re.compile(r"[0-9a-f]{64}\Z")


class DeviceAuthError(ValueError):
    pass


class NonceConflict(RuntimeError):
    pass


def signature_message(node, request_ts, nonce, body):
    """Canonical HMAC domain separator. Must match future ESP32 firmware."""
    if not isinstance(body, bytes):
        raise TypeError("body:expected_bytes")
    return f"TASNIM-DEVICE-V1\n{node}\n{request_ts}\n{nonce}\n".encode("ascii") + body


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DeviceAuthError("body:duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite(token):
    raise DeviceAuthError("body:nonfinite_json")


def verify_device_request(body, headers, secrets_by_node, *, now_ms=None):
    """Verify HMAC, exact node ownership, clock, JSON and V2 packet.

    Headers: X-Tasnim-Node, X-Tasnim-Time, X-Tasnim-Nonce,
    X-Tasnim-Signature, Content-Type: application/json.

    Secrets are injected as per-node bytes and never embedded in GitHub.
    """
    if type(body) is not bytes or not 0 < len(body) <= MAX_PAYLOAD_BYTES:
        raise DeviceAuthError("body:invalid_length")
    if not isinstance(headers, dict):
        raise DeviceAuthError("headers:expected_dict")
    lowered = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise DeviceAuthError("headers:invalid_type")
        name = key.lower()
        if name in lowered:
            raise DeviceAuthError("headers:duplicate_case")
        lowered[name] = value

    if lowered.get("content-type") != "application/json":
        raise DeviceAuthError("headers:content_type")
    node = lowered.get("x-tasnim-node")
    stamp = lowered.get("x-tasnim-time")
    nonce = lowered.get("x-tasnim-nonce")
    signature = lowered.get("x-tasnim-signature")
    if node not in NODE_IDS:
        raise DeviceAuthError("auth:node_unknown")
    if not isinstance(stamp, str) or not re.fullmatch(r"[1-9][0-9]{12}", stamp):
        raise DeviceAuthError("auth:timestamp_format")
    if not isinstance(nonce, str) or not NONCE_PATTERN.fullmatch(nonce):
        raise DeviceAuthError("auth:nonce_format")
    if not isinstance(signature, str) or not HEX_SIGNATURE.fullmatch(signature):
        raise DeviceAuthError("auth:signature_format")

    current = int(time.time() * 1000) if now_ms is None else now_ms
    if type(current) is not int or current < 0:
        raise ValueError("now_ms:invalid")
    if abs(int(stamp) - current) > MAX_CLOCK_SKEW_MS:
        raise DeviceAuthError("auth:expired_request")

    secret = secrets_by_node.get(node)
    if type(secret) is not bytes or len(secret) < 32:
        raise DeviceAuthError("auth:credentials_unavailable")
    signed = signature_message(node, stamp, nonce, body)
    expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise DeviceAuthError("auth:bad_signature")

    try:
        packet = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeviceAuthError("body:invalid_json") from exc

    if type(packet) is not dict:
        raise DeviceAuthError("body:not_object")
    if packet.get("node_id") != node:
        raise DeviceAuthError("auth:node_mismatch")

    check_ingestion_packet(packet, now_ms=current)
    return {"packet": packet, "node": node, "nonce": nonce,
            "request_ts": int(stamp),
            "fingerprint": hashlib.sha256(signed).hexdigest()}


def accept_signed_measurement(db, body, headers, secrets_by_node, *, now_ms=None):
    """Verify, register nonce transactionally and ingest history then latest.

    Identical retry reuses its nonce and fingerprint and remains idempotent.
    A nonce reused for different signed content is rejected. Nonce registry
    is backend-only /gateway_state/nonces (not readable by dashboard Rules).
    These operations are NOT one atomic transaction.
    """
    envelope = verify_device_request(
        body, headers, secrets_by_node, now_ms=now_ms
    )
    path = f"gateway_state/nonces/{envelope['node']}/{envelope['nonce']}"
    expected = {
        "fingerprint": envelope["fingerprint"],
        "request_ts_ms": envelope["request_ts"],
    }
    stored = db.reference(path).transaction(
        lambda old: expected if old is None else old
    )
    if stored != expected:
        raise NonceConflict("gateway:nonce_reused_with_changed_request")
    return ingest_verified_packet(db, envelope["packet"], now_ms=now_ms)
