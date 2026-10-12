"""Read-only provenance audit of V2 AI checkpoints in synthetic demo data.

Uses the SAME canonical history and context-digest checks as the worker;
never infers, commits, repairs, deletes, or loads model artifacts. This is
software integrity only, NOT proof of field sensor accuracy or trusted ML.
"""
from __future__ import annotations

from ai.hardware_test_history_v2 import prepare_backlog
from ai.hardware_test_worker_v2 import (
    HISTORY_PATH, WorkerReviewRequired, _check_markers, _snapshot,
    context_digests, require_worker_emulator,
)

LATEST_PATH = "hardware_test/analysis/latest"


class CheckpointIntegrityReviewRequired(RuntimeError):
    """Checkpoint/source conflict. No automatic overwrite or re-prediction."""


def inspect_checkpoint_integrity(
    history, latest, *, session_id, model_version, max_source_slots=500,
):
    """Inspect already-read data without ever mutating inputs.

    States:
      NO_CHECKPOINTS: no archived record and no latest pointer
      ALIGNED: latest equals highest verified archived checkpoint
      REPAIRABLE_LATEST: latest absent or points to a verified older archive

    Malformed source, mismatched fingerprint, unrecognized latest, or
    incompatible archived markers fail closed with an opaque error type.
    Use the guarded worker's existing recovery path only after manual review.
    """
    if type(max_source_slots) is not int or not 2 <= max_source_slots <= 5000:
        raise ValueError("checkpoint_audit:invalid_source_limit")
    if type(history) is not dict or len(history) > max_source_slots:
        raise CheckpointIntegrityReviewRequired("checkpoint_audit:source_invalid")

    try:
        plan = prepare_backlog(
            history, session_id=session_id,
            expected_model_version=model_version,
        )
        digests = context_digests(history, plan)
        _check_markers(history, plan, digests)
    except (ValueError, TypeError, KeyError, OverflowError,
            WorkerReviewRequired) as exc:
        raise CheckpointIntegrityReviewRequired(
            "checkpoint_audit:source_or_archive_review"
        ) from exc

    archived = [
        (row["source_timestamp_ms"],
         history[str(row["source_timestamp_ms"])]["analysis"])
        for row in plan["rows"]
        if type(history[str(row["source_timestamp_ms"])].get("analysis")) is dict
    ]
    if latest is not None and (
        type(latest) is not dict
        or not any(marker == latest for _, marker in archived)
    ):
        raise CheckpointIntegrityReviewRequired(
            "checkpoint_audit:latest_not_verified_archive"
        )

    highest = max(archived, default=None, key=lambda item: item[0])
    if highest is None:
        state = "NO_CHECKPOINTS"
    elif latest == highest[1]:
        state = "ALIGNED"
    else:
        state = "REPAIRABLE_LATEST"

    return {
        "state": state,
        "archived_count": len(archived),
        "pending_count": len(plan["pending_timestamps"]),
        "skipped_slot_count": len(plan["skipped"]),
        "highest_archived_slot": highest[0] if highest else None,
        "latest_slot": latest["source_timestamp_ms"] if latest is not None else None,
        "model_stage": "PROTOTYPE_SIMULATION",
        "read_only": True,
    }


def inspect_demo_checkpoints(
    db, *, session_id, model_version, max_source_slots=500,
):
    """Fail before ANY database access unless explicitly demo-Emulator bound."""
    require_worker_emulator(db)
    if type(max_source_slots) is not int or not 2 <= max_source_slots <= 5000:
        raise ValueError("checkpoint_audit:invalid_source_limit")
    history = _snapshot(db)
    # Reject oversized input before reading second path.
    if len(history) > max_source_slots:
        raise CheckpointIntegrityReviewRequired(
            "checkpoint_audit:source_limit_exceeded"
        )
    latest = db.reference(LATEST_PATH).get()
    return inspect_checkpoint_integrity(
        history, latest, session_id=session_id, model_version=model_version,
        max_source_slots=max_source_slots,
    )
