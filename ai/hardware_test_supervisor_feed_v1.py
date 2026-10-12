"""Read-only browser feed of *sanitized* AI supervisor status in the DEMO RTDB.

The private worker_state status remains authoritative. A small, bounded
mirror is published under hardware_test so already-authorized research users
can READ it with candidate RTDB Rules. It contains no secrets or measurements.
NO new browser write permissions are introduced, and LIVE is refused.
"""
from __future__ import annotations

from ai.hardware_test_worker_lease_v2 import _require_exclusive_demo
from ai.hardware_test_supervisor_status_v1 import make_supervisor_status

FEED_PATH = "hardware_test/operations/supervisor/latest"


def publish_demo_supervisor_feed(db, record):
    _require_exclusive_demo(db)
    if type(record) is not dict:
        raise ValueError("supervisor_feed:invalid")
    # Strictly reconstruct to prevent accidentally exposing a token,
    # arbitrary exception text, inference, or sensor measurement.
    counters = (
        ("processed_count", "processed_slots"),
        ("recovered_count", "recovered_slots"),
        ("deferred_count", "deferred_slots"),
        ("would_process_count", "would_process_slots"),
    )
    data = {}
    for key, target in counters:
        count = record.get(key)
        if type(count) is not int or not 0 <= count <= 5000:
            raise ValueError("supervisor_feed:invalid_counter")
        data[target] = [0] * count
    normalized = make_supervisor_status(
        state=record.get("state"), timestamp_ms=record.get("timestamp_ms"),
        attempts=record.get("attempts"), error_code=record.get("error_code"),
        result=data,
    )
    if normalized != record:
        raise ValueError("supervisor_feed:noncanonical")

    def choose(previous):
        if previous is None:
            return dict(normalized)
        if type(previous) is not dict or type(previous.get("timestamp_ms")) is not int:
            return previous   # Corruption requires manual review.
        if previous["timestamp_ms"] < normalized["timestamp_ms"]:
            return dict(normalized)
        return previous

    final = db.reference(FEED_PATH).transaction(choose)
    return final == normalized
