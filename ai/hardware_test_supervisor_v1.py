"""Manually-invoked, bounded AI Supervisor V1 for demo Firebase Emulator ONLY.

Two features: guarded paced cycles/retry classification and compact operational
status. NO daemon, cron, Firebase client initialization or unattended launch.
The predictor and model are always injected by the caller.
"""
from __future__ import annotations

import time

from ai.hardware_test_worker_lease_v2 import (
    WorkerLeaseBusy, WorkerLeaseOwnershipLost, _require_exclusive_demo,
    run_exclusive_emulator_cycle,
)
from ai.hardware_test_worker_v2 import WorkerReviewRequired, WorkerSourceChanged
from ai.hardware_test_supervisor_status_v1 import (
    make_supervisor_status, persist_supervisor_status,
)
from ai.hardware_test_supervisor_feed_v1 import publish_demo_supervisor_feed
from ai.hardware_test_supervisor_audit_v1 import append_supervisor_audit
from ai.hardware_test_supervisor_recovery_v1 import (
    inspect_demo_supervisor_reporting, SupervisorReportingReviewRequired,
)

_RETRYABLE = (ConnectionError, TimeoutError, WorkerSourceChanged)


def run_supervised_emulator_cycle(
    db, *, session_id, model_version, model_bundle, predict_fn,
    now_ms=None, max_attempts=2, dry_run=False, record_status=True,
    max_actions_per_cycle=3, max_source_slots=500,
):
    """Try at most two bounded cooperative cycles; return sanitized report.

    A transient partial-commit error is retried by reading canonical history
    again, never by reusing a stale predicted output. Lease collisions and
    review-required sources are NOT retried or reset automatically.

    In dry_run there are NO transaction writes (not even status).
    """
    _require_exclusive_demo(db)  # Before any DB read/write.
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("supervisor:max_attempts_range_1_to_3")
    if type(dry_run) is not bool or type(record_status) is not bool:
        raise ValueError("supervisor:invalid_boolean")
    if type(max_actions_per_cycle) is not int or not 1 <= max_actions_per_cycle <= 50:
        raise ValueError("supervisor:max_actions_range_1_to_50")
    if type(max_source_slots) is not int or not 2 <= max_source_slots <= 5000:
        raise ValueError("supervisor:max_sources_range_2_to_5000")
    timestamp = int(time.time() * 1000) if now_ms is None else now_ms
    if type(timestamp) is not int or timestamp <= 0:
        raise ValueError("supervisor:invalid_timestamp")

    if record_status and not dry_run:
        reporting = inspect_demo_supervisor_reporting(db)
        if reporting["state"] == "RECOVERY_REQUIRED":
            # A prior cycle reached private status but not every mirror.
            # Prevent a subsequent IDLE/PROCESSED cycle from hiding it.
            raise SupervisorReportingReviewRequired(
                "supervisor_reporting:repair_required_before_new_cycle"
            )

    state, error, output = "FAILED", "WORKER_ERROR", None
    used_attempts = 0
    for attempt in range(1, max_attempts + 1):
        used_attempts = attempt
        try:
            output = run_exclusive_emulator_cycle(
                db, session_id=session_id, model_version=model_version,
                model_bundle=model_bundle, predict_fn=predict_fn,
                now_ms=timestamp, dry_run=dry_run,
                max_actions_per_cycle=max_actions_per_cycle,
                max_source_slots=max_source_slots,
            )
            state, error = (
                "PREVIEW" if dry_run else
                "PROCESSED" if output["processed_slots"] or output["recovered_slots"]
                else "IDLE"
            ), "NONE"
            break
        except WorkerLeaseBusy:
            state, error = "WAITING_LOCK", "LEASE_BUSY"
            break
        except (WorkerReviewRequired, WorkerLeaseOwnershipLost):
            state, error = "REVIEW_REQUIRED", "REVIEW_REQUIRED"
            break
        except _RETRYABLE as exc:
            state = "RETRY_EXHAUSTED"
            error = ("SOURCE_CHANGED" if isinstance(exc, WorkerSourceChanged)
                     else "TRANSIENT_ERROR")
            if attempt < max_attempts:
                continue
            break
        except Exception:
            # No raw exception text, trace, token or model features recorded.
            state, error = "FAILED", "WORKER_ERROR"
            break

    status = make_supervisor_status(
        state=state, timestamp_ms=timestamp, attempts=used_attempts,
        result=output, error_code=error,
    )
    # A failure to record status is NOT silently swallowed. The caller
    # receives a persistence error and must investigate the local demo.
    private_written = False
    public_written = False
    audit_written = False
    if record_status and not dry_run:
        private_written = persist_supervisor_status(db, status)
        if private_written:
            # All three paths use individual Emulator transactions, NOT an
            # atomic multi-path commit. A failure propagates to the caller.
            public_written = publish_demo_supervisor_feed(db, status)
            if public_written:
                audit_written = append_supervisor_audit(db, status)
    return {
        **status,
        "status_persisted": private_written,
        "feed_persisted": public_written,
        "audit_persisted": audit_written,
    }


def run_bounded_demo_schedule(
    db, *, cycles=1, interval_seconds=300, sleep_fn=time.sleep, **kwargs
):
    """Run 1–3 explicitly requested cycles, then EXIT. Not a daemon.

    Interval is applied between cycles, never before the first. For safety
    stop the bounded schedule on ANY non-success outcome. Callers must opt
    into the localhost demo guard before sleep or database access.
    """
    _require_exclusive_demo(db)
    if type(cycles) is not int or not 1 <= cycles <= 3:
        raise ValueError("supervisor:cycles_range_1_to_3")
    if type(interval_seconds) is not int or not 1 <= interval_seconds <= 3600:
        raise ValueError("supervisor:interval_seconds_range_1_to_3600")
    if not callable(sleep_fn):
        raise ValueError("supervisor:sleep_fn_required")
    if "now_ms" in kwargs and cycles > 1:
        raise ValueError("supervisor:fixed_clock_for_multiple_cycles")

    results = []
    for index in range(cycles):
        if index:
            sleep_fn(interval_seconds)
        status = run_supervised_emulator_cycle(db, **kwargs)
        results.append(status)
        if status["state"] not in ("PROCESSED", "IDLE", "PREVIEW"):
            break
    return results
