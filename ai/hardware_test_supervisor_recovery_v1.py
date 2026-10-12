"""Explicit, bounded repair of a partially published demo Supervisor report.

The private status, browser feed and hash-chain audit use separate RTDB
transactions. After a crash between them, do NOT silently run a new cycle:
the already-committed, canonical private status must be reconciled first.
This module never runs inference or writes measurement/history paths.
All operations require the existing localhost demo Emulator guard.
"""
from __future__ import annotations

from ai.hardware_test_worker_lease_v2 import _require_exclusive_demo
from ai.hardware_test_supervisor_status_v1 import STATUS_PATH
from ai.hardware_test_supervisor_feed_v1 import (
    FEED_PATH, publish_demo_supervisor_feed,
)
from ai.hardware_test_supervisor_audit_v1 import (
    AUDIT_PATH, _canonical_status, verify_supervisor_audit,
    append_supervisor_audit,
)


class SupervisorReportingReviewRequired(RuntimeError):
    """One or more reporting paths conflict or cannot be trusted."""


def inspect_demo_supervisor_reporting(db):
    """Inspect three reporting paths without changing any database record."""
    _require_exclusive_demo(db)
    private = db.reference(STATUS_PATH).get()
    feed = db.reference(FEED_PATH).get()
    audit = db.reference(AUDIT_PATH).get()

    # Check audit even when status is absent: a malformed audit must not
    # disappear as a harmless "uninitialized" system.
    events = verify_supervisor_audit(audit)
    if private is None:
        if feed is not None or events:
            raise SupervisorReportingReviewRequired(
                "supervisor_reporting:missing_private_status"
            )
        return {"state": "NO_REPORT", "feed_matches": False,
                "audit_matches": False, "status": None}

    try:
        canonical = _canonical_status(private)
        if feed is not None:
            canonical_feed = _canonical_status(feed)
            if (canonical_feed["timestamp_ms"] > canonical["timestamp_ms"]
                    or (canonical_feed["timestamp_ms"] == canonical["timestamp_ms"]
                        and canonical_feed != canonical)):
                raise SupervisorReportingReviewRequired(
                    "supervisor_reporting:feed_conflict"
                )
    except (ValueError, TypeError, KeyError) as exc:
        raise SupervisorReportingReviewRequired(
            "supervisor_reporting:invalid_private_or_feed"
        ) from exc

    last = events[-1]["record"] if events else None
    if last is not None and (
        last["timestamp_ms"] > canonical["timestamp_ms"]
        or (last["timestamp_ms"] == canonical["timestamp_ms"]
            and last != canonical)
    ):
        raise SupervisorReportingReviewRequired(
            "supervisor_reporting:audit_conflict"
        )
    feed_matches = feed == canonical
    audit_matches = last == canonical
    return {
        "state": "CONSISTENT" if feed_matches and audit_matches
                 else "RECOVERY_REQUIRED",
        "feed_matches": feed_matches,
        "audit_matches": audit_matches,
        "status": canonical,
    }


def repair_demo_supervisor_reporting(db):
    """Explicitly finish *only* missing/older feed and private audit records.

    A corrupted or newer feed/audit is never overwritten. Re-running this
    function is idempotent. Partial write failures propagate; call again
    manually after investigating, without rerunning model inference.
    """
    before = inspect_demo_supervisor_reporting(db)
    if before["state"] != "RECOVERY_REQUIRED":
        return {"state": before["state"],
                "feed_matches": before["feed_matches"],
                "audit_matches": before["audit_matches"]}

    record = before["status"]
    if not before["feed_matches"]:
        if not publish_demo_supervisor_feed(db, record):
            raise SupervisorReportingReviewRequired(
                "supervisor_reporting:feed_commit_rejected"
            )
    if not before["audit_matches"]:
        append_supervisor_audit(db, record)

    after = inspect_demo_supervisor_reporting(db)
    if after["state"] != "CONSISTENT" or after["status"] != record:
        raise SupervisorReportingReviewRequired(
            "supervisor_reporting:changed_during_repair"
        )
    return {"state": "REPAIRED", "feed_matches": True,
            "audit_matches": True}
