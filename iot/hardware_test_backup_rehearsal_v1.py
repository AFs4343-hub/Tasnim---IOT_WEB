"""Strict synthetic-backup rehearsal, NO production export or restore API.

Copies only explicitly supplied synthetic /hardware_test fixture data into a
verifiable in-memory payload. The function returning the restored COPY has
no database adapter, credentials or write capability.
"""
from __future__ import annotations

import copy
import hashlib
import json

MAX_FIXTURE_BYTES = 2_000_000
FIXTURE_TYPE = "TASNIM_SYNTHETIC_HARDWARE_TEST_BACKUP_V1"


class DemoRestoreReviewRequired(RuntimeError):
    pass


def _encoded(value):
    try:
        data = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, OverflowError) as exc:
        raise DemoRestoreReviewRequired("demo_backup:invalid_json") from exc
    if len(data) > MAX_FIXTURE_BYTES:
        raise DemoRestoreReviewRequired("demo_backup:size_limit")
    return data


def prepare_synthetic_backup(hardware_test):
    """Build an in-memory envelope; never read Firebase, files or secrets."""
    if type(hardware_test) is not dict or set(hardware_test) - {
        "history", "nodes", "analysis", "operations",
    } or not hardware_test:
        raise DemoRestoreReviewRequired("demo_backup:unexpected_root")
    data = _encoded(hardware_test)
    return {
        "kind": FIXTURE_TYPE,
        "sha256": hashlib.sha256(data).hexdigest(),
        "hardware_test": json.loads(data),
    }


def rehearse_synthetic_restore(envelope):
    """Verify a backup then create a NEW dictionary, never write a database."""
    if type(envelope) is not dict or set(envelope) != {
        "kind", "sha256", "hardware_test",
    } or envelope["kind"] != FIXTURE_TYPE:
        raise DemoRestoreReviewRequired("demo_backup:invalid_envelope")
    if type(envelope["sha256"]) is not str:
        raise DemoRestoreReviewRequired("demo_backup:invalid_digest")
    content = envelope["hardware_test"]
    if type(content) is not dict or not content or set(content) - {
        "history", "nodes", "analysis", "operations",
    }:
        raise DemoRestoreReviewRequired("demo_backup:unexpected_root")
    data = _encoded(content)
    if hashlib.sha256(data).hexdigest() != envelope["sha256"]:
        raise DemoRestoreReviewRequired("demo_backup:digest_mismatch")
    return copy.deepcopy(content)
