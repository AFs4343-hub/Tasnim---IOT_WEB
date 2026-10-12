"""Bounded, private, sanitized audit trail for TASNIM demo Supervisor.

This is a developer audit trail, NOT an immutable production ledger. A trusted
Admin can modify Emulator data. The SHA-256 chain detects accidental edits,
not malicious alteration. No raw exception, token, model output or sensor value.
"""
from __future__ import annotations

import hashlib
import json

from ai.hardware_test_supervisor_status_v1 import make_supervisor_status
from ai.hardware_test_worker_lease_v2 import _require_exclusive_demo

AUDIT_PATH = "worker_state/ai_v2_supervisor/audit_v1"
MAX_EVENTS = 20
ZERO_HASH = "0" * 64
FIELDS = frozenset({
    "schema_version", "state", "error_code", "timestamp_ms", "attempts",
    "processed_count", "recovered_count", "deferred_count",
    "would_process_count", "source_root", "model_stage",
})


class SupervisorAuditReviewRequired(RuntimeError):
    """Stored demo audit cannot be trusted; do not overwrite it."""


def _canonical_status(record):
    if type(record) is not dict or set(record) != FIELDS:
        raise ValueError("audit:unexpected_status_fields")
    counters = {}
    for count_key, slots_key in (
        ("processed_count", "processed_slots"),
        ("recovered_count", "recovered_slots"),
        ("deferred_count", "deferred_slots"),
        ("would_process_count", "would_process_slots"),
    ):
        count = record[count_key]
        if type(count) is not int or not 0 <= count <= 5000:
            raise ValueError("audit:invalid_count")
        counters[slots_key] = [0] * count
    canonical = make_supervisor_status(
        state=record["state"], timestamp_ms=record["timestamp_ms"],
        attempts=record["attempts"], error_code=record["error_code"],
        result=counters,
    )
    if canonical != record:
        raise ValueError("audit:noncanonical_status")
    return canonical


def _digest(seq, event, prev):
    payload = {
        "sequence": seq,
        "record": event,
        "previous_sha256": prev,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(b"TASNIM-SUPERVISOR-AUDIT-V1\x00" + encoded).hexdigest()


def verify_supervisor_audit(stored):
    """Return valid ordered events, or refuse corruption (read-only)."""
    if stored is None:
        return []
    if type(stored) is not dict or set(stored) != {
        "schema_version", "events", "last_sequence", "tail_sha256",
    } or stored["schema_version"] != 1:
        raise SupervisorAuditReviewRequired("audit:invalid_root")
    events = stored["events"]
    if type(events) is not dict or not 1 <= len(events) <= MAX_EVENTS:
        raise SupervisorAuditReviewRequired("audit:invalid_event_count")
    # Prefix with a letter: RTDB otherwise serializes numeric keys as arrays.
    seqs = sorted(
        int(k[1:]) for k in events
        if type(k) is str and k.startswith("s")
        and k[1:].isdigit() and str(int(k[1:])) == k[1:]
    )
    if len(seqs) != len(events) or seqs != list(range(seqs[0], seqs[-1] + 1)):
        raise SupervisorAuditReviewRequired("audit:sequence_gap")
    if type(stored["last_sequence"]) is not int or stored["last_sequence"] != seqs[-1]:
        raise SupervisorAuditReviewRequired("audit:wrong_last_sequence")
    predecessor = None
    verified = []
    for seq in seqs:
        entry = events[f"s{seq}"]
        if type(entry) is not dict or set(entry) != {
            "sequence", "record", "previous_sha256", "sha256",
        } or entry["sequence"] != seq:
            raise SupervisorAuditReviewRequired("audit:invalid_entry")
        try:
            _canonical_status(entry["record"])
        except (ValueError, KeyError, TypeError) as exc:
            raise SupervisorAuditReviewRequired("audit:invalid_record") from exc
        parent = entry["previous_sha256"]
        if type(parent) is not str or len(parent) != 64 or any(
            c not in "0123456789abcdef" for c in parent
        ):
            raise SupervisorAuditReviewRequired("audit:invalid_parent")
        if predecessor is not None and parent != predecessor:
            raise SupervisorAuditReviewRequired("audit:broken_chain")
        if seq == 1 and parent != ZERO_HASH:
            raise SupervisorAuditReviewRequired("audit:invalid_genesis")
        computed = _digest(seq, entry["record"], parent)
        if entry["sha256"] != computed:
            raise SupervisorAuditReviewRequired("audit:bad_digest")
        if verified and entry["record"]["timestamp_ms"] <= verified[-1]["record"]["timestamp_ms"]:
            raise SupervisorAuditReviewRequired("audit:nonmonotonic_clock")
        predecessor = computed
        verified.append(entry)
    if stored["tail_sha256"] != predecessor:
        raise SupervisorAuditReviewRequired("audit:wrong_tail")
    return verified


def append_supervisor_audit(db, status):
    """Atomically append one bounded sanitized event in LOCAL demo Emulator.

    Returns True if newly appended; False for exact replay or stale event.
    Never overwrites malformed history. All retries validate the chain.
    """
    _require_exclusive_demo(db)
    canonical = _canonical_status(status)
    appended = False

    def update(previous):
        nonlocal appended
        current = verify_supervisor_audit(previous)
        if current:
            newest = current[-1]["record"]
            if canonical["timestamp_ms"] <= newest["timestamp_ms"]:
                appended = False
                return previous
            seq = current[-1]["sequence"] + 1
            parent = current[-1]["sha256"]
            kept = current[-(MAX_EVENTS - 1):]
        else:
            seq, parent, kept = 1, ZERO_HASH, []
        entry = {
            "sequence": seq,
            "record": dict(canonical),
            "previous_sha256": parent,
            "sha256": _digest(seq, canonical, parent),
        }
        records = kept + [entry]
        appended = True
        return {
            "schema_version": 1,
            "events": {f"s{e['sequence']}": e for e in records},
            "last_sequence": seq,
            "tail_sha256": entry["sha256"],
        }

    final = db.reference(AUDIT_PATH).transaction(update)
    verify_supervisor_audit(final)
    # Return True only if this record became the committed tail.
    return bool(appended and final["events"][f"s{final['last_sequence']}"]["record"] == canonical)
