"""Emulator-only, run-once AI worker candidate for TASNIM hardware V2.

No Firebase initialization, credentials, daemon, or production endpoints.
A caller must explicitly inject and authorize a localhost demo adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from ai.hardware_test_analysis_writer_v2 import (
    commit_verified_analysis, prepare_analysis_record,
)
from ai.hardware_test_history_v2 import (
    NODE_ORDER, model_frame_for_slot, prepare_backlog,
)
from ai.hardware_test_preview_v2 import annotate_preview

EMULATOR_HOST = "127.0.0.1:19003"
DEMO_PROJECT = "demo-tasnim-security"
HISTORY_PATH = "hardware_test/history"


class WorkerReviewRequired(RuntimeError):
    """Persisted analysis cannot safely be trusted or replaced."""


class WorkerSourceChanged(RuntimeError):
    """History changed during prediction. Retry from a fresh snapshot."""


def require_worker_emulator(db):
    if (
        os.getenv("TASNIM_AI_WORKER_EMULATOR_ONLY") != "YES"
        or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != EMULATOR_HOST
        or os.getenv("GCLOUD_PROJECT") != DEMO_PROJECT
        or getattr(db, "emulator_only", None) is not True
        or getattr(db, "emulator_project", None) != DEMO_PROJECT
        or getattr(db, "emulator_host", None) != EMULATOR_HOST
    ):
        raise RuntimeError("REFUSED: worker requires explicit demo emulator")


def _snapshot(db):
    value = db.reference(HISTORY_PATH).get()
    if value is None:
        return {}
    if type(value) is not dict:
        raise ValueError("history:expected_object")
    return value


def _source_packet(raw):
    """Normalize equivalent Realtime Database forms without modifying input."""
    packet = dict(raw)
    packet.setdefault("quality_flags", [])
    for key in ("ph", "tds", "turbidity", "rssi"):
        if key in packet:
            packet[key] = float(packet[key])
    return packet


def context_digests(history, plan):
    """SHA-256 of cumulative VALID model context, including sample metadata.

    Analysis contents are omitted. A late valid measurement before a target
    changes that target's fingerprint and requires human review.
    """
    stream = hashlib.sha256(b"TASNIM-AI-V2-CONTEXT\x00")
    digests = {}
    for row in plan["rows"]:
        slot = row["source_timestamp_ms"]
        readings = [_source_packet(history[str(slot)][n]) for n in NODE_ORDER]
        encoded = json.dumps(
            [slot, readings], sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
        stream.update(len(encoded).to_bytes(4, "big"))
        stream.update(encoded)
        digests[slot] = stream.hexdigest()
    return digests


def _check_markers(history, plan, digests):
    valid = {str(row["source_timestamp_ms"]) for row in plan["rows"]}
    for key, record in history.items():
        if not isinstance(record, dict) or record.get("analysis") is None:
            continue
        # A previously analyzed slot that is now incomplete or corrupt is
        # not eligible for silent omission, even if it is absent from rows.
        if key not in valid:
            raise WorkerReviewRequired(f"invalid_analyzed_source:{key}")
        marker = record["analysis"]
        slot = int(key)
        if (
            key in plan["blocked_analyses"]
            or type(marker) is not dict
            or marker.get("source_digest_sha256") != digests[slot]
        ):
            raise WorkerReviewRequired(f"analysis_checkpoint_review:{slot}")


def run_emulator_cycle(
    db, *, session_id, model_version, model_bundle, predict_fn, now_ms=None,
):
    """Process all eligible slots once; persist checkpoints in demo RTDB.

    On restart, identical archived analysis is replayed to repair a partial
    history/latest write. New inference is never run for an archived slot.
    Re-read source immediately before committing, but this is not an atomic
    snapshot/write lock: LIVE usage is explicitly prohibited.
    """
    require_worker_emulator(db)
    if not callable(predict_fn):
        raise ValueError("predict_fn:required")
    if not isinstance(model_version, str) or not model_version.strip() or len(model_version) > 80:
        raise ValueError("model_version:invalid")
    timestamp = int(time.time() * 1000) if now_ms is None else now_ms
    if type(timestamp) is not int or timestamp <= 0:
        raise ValueError("now_ms:invalid")

    initial = _snapshot(db)
    plan = prepare_backlog(
        initial, session_id=session_id, expected_model_version=model_version,
    )
    fingerprints = context_digests(initial, plan)
    _check_markers(initial, plan, fingerprints)

    processed, recovered = [], []
    for row in plan["rows"]:
        slot = row["source_timestamp_ms"]
        if slot in plan["warmup_slots"]:
            continue
        marker = initial[str(slot)].get("analysis")
        if marker is None and slot not in plan["pending_timestamps"]:
            continue

        if marker is None:
            frame = model_frame_for_slot(plan, slot)
            prediction = annotate_preview(
                predict_fn(frame, model_bundle),
                slot=slot, time_mode=plan["time_mode"],
            )
            prediction["source_digest_sha256"] = fingerprints[slot]
            candidate = prepare_analysis_record(
                prediction, model_version=model_version,
                inference_timestamp_ms=timestamp,
            )
        else:
            candidate = marker

        current = _snapshot(db)
        current_plan = prepare_backlog(
            current, session_id=session_id,
            expected_model_version=model_version,
        )
        current_digests = context_digests(current, current_plan)
        _check_markers(current, current_plan, current_digests)
        if current_digests.get(slot) != fingerprints[slot]:
            raise WorkerSourceChanged(f"source_prefix_changed:{slot}")
        if current[str(slot)].get("analysis") != marker:
            raise WorkerSourceChanged(f"analysis_marker_changed:{slot}")

        commit_verified_analysis(db, candidate)
        (processed if marker is None else recovered).append(slot)

    return {
        "processed_slots": processed,
        "recovered_slots": recovered,
        "warmup_slots": plan["warmup_slots"],
        "skipped": plan["skipped"],
        "source_root": "hardware_test",
        "model_stage": "PROTOTYPE_SIMULATION",
    }
