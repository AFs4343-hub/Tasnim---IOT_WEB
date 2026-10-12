"""Cooperative single-flight gate for the TASNIM V2 *demo Emulator* worker.

This is NOT a production lease or distributed fencing lock. There is no TTL,
automatic stale takeover, background job, LIVE endpoint, or credential loading.

Only callers opting into run_exclusive_emulator_cycle are serialized.
The lower-level run_emulator_cycle remains a test/compatibility primitive.
"""
from __future__ import annotations

import os
import secrets
import time

from ai.hardware_test_worker_v2 import require_worker_emulator, run_emulator_cycle

LEASE_PATH = "worker_state/ai_v2_exclusive"
DEMO_COORDINATION_FLAG = "TASNIM_AI_COORDINATION_EMULATOR_ONLY"
# Admin SDK's RTDB transaction refuses None as a new value; use a durable
# owner-free tombstone. Only this exact value can be safely reacquired.
RELEASED = {"state": "RELEASED"}


class WorkerLeaseBusy(RuntimeError):
    """Another cooperative worker owns the demo lock; do not write."""


class WorkerLeaseOwnershipLost(RuntimeError):
    """A lock changed unexpectedly; stop and request manual review."""


def _require_exclusive_demo(db):
    # All checks happen BEFORE any Firebase read/write/transaction.
    require_worker_emulator(db)
    if os.getenv(DEMO_COORDINATION_FLAG) != "YES":
        raise RuntimeError("REFUSED: exclusive worker requires explicit demo opt-in")


def acquire_exclusive_emulator_lock(db):
    """Claim an absent or owner-released slot; never steal an active lock."""
    _require_exclusive_demo(db)
    record = {
        "state": "HELD",
        "owner_id": secrets.token_hex(16),
        "acquired_at_ms": int(time.time() * 1000),
    }
    ref = db.reference(LEASE_PATH)
    current = ref.transaction(
        lambda previous: record
        if previous is None or previous == RELEASED else previous
    )
    if current != record:
        raise WorkerLeaseBusy("demo_worker_lease_held_or_requires_manual_review")
    return record["owner_id"]


def release_exclusive_emulator_lock(db, *, owner_id):
    """Only the owner can atomically mark a held lock RELEASED."""
    _require_exclusive_demo(db)
    if not isinstance(owner_id, str) or len(owner_id) != 32:
        raise ValueError("owner_id:invalid")
    attempted_owner_release = False

    def release(previous):
        nonlocal attempted_owner_release
        if (type(previous) is dict and previous.get("state") == "HELD"
                and previous.get("owner_id") == owner_id):
            attempted_owner_release = True
            # Firebase Admin SDK disallows None in transaction(),
            # so transactional deletion is not viable here.
            return dict(RELEASED)
        return previous

    final = db.reference(LEASE_PATH).transaction(release)
    if not attempted_owner_release or final != RELEASED:
        raise WorkerLeaseOwnershipLost("demo_worker_lock_changed_or_missing")


def run_exclusive_emulator_cycle(db, **worker_kwargs):
    """Serialize one worker invocation on localhost demo RTDB, fail closed.

    A normal exception releases a lock with matching owner. A hard crash may
    strand it: human review/reset of the *demo Emulator only* is required.
    Dry runs delegate directly, preserving the zero-write guarantee.
    """
    _require_exclusive_demo(db)
    if worker_kwargs.get("dry_run") is True:
        return run_emulator_cycle(db, **worker_kwargs)

    owner = acquire_exclusive_emulator_lock(db)
    try:
        result = run_emulator_cycle(db, **worker_kwargs)
        result["coordination"] = "DEMO_EXCLUSIVE_SINGLE_FLIGHT"
        return result
    finally:
        release_exclusive_emulator_lock(db, owner_id=owner)
