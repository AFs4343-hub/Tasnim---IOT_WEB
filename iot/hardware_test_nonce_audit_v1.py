"""Read-only audit for private signed-gateway nonce registry.

No automatic cleanup, no Firebase initialization, no nonce/fingerprint logging.
48 hours is an example horizon for a FUTURE policy decision, not an active TTL.
"""
from __future__ import annotations

import re

from iot.hardware_test_gateway_auth_v1 import NONCE_PATTERN

NODE_IDS = ("N0", "N1", "N2")
DEFAULT_REVIEW_HORIZON_MS = 48 * 60 * 60 * 1000
MAX_AUDIT_ENTRIES = 20_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class NonceAuditReviewRequired(RuntimeError):
    pass


def audit_nonce_registry(
    registry, *, now_ms, review_horizon_ms=DEFAULT_REVIEW_HORIZON_MS,
    max_entries=MAX_AUDIT_ENTRIES,
):
    """Summarize candidate growth/expiry; NEVER disclose or remove records."""
    if type(now_ms) is not int or now_ms < 1_704_067_200_000:
        raise ValueError("nonce_audit:invalid_clock")
    if (type(review_horizon_ms) is not int
            or not 60_000 <= review_horizon_ms <= 30*86_400_000):
        raise ValueError("nonce_audit:invalid_horizon")
    if type(max_entries) is not int or not 1 <= max_entries <= MAX_AUDIT_ENTRIES:
        raise ValueError("nonce_audit:invalid_limit")
    if registry is None:
        registry = {}
    if type(registry) is not dict:
        raise NonceAuditReviewRequired("nonce_audit:invalid_registry")
    per_node = {node: {"total": 0, "past_review_horizon": 0, "invalid": 0}
                for node in NODE_IDS}
    count = 0
    invalid_nodes = 0
    for node, entries in registry.items():
        if node not in NODE_IDS or type(entries) is not dict:
            invalid_nodes += 1
            continue
        for nonce, record in entries.items():
            count += 1
            if count > max_entries:
                raise NonceAuditReviewRequired("nonce_audit:entry_budget_exceeded")
            target = per_node[node]
            target["total"] += 1
            if (type(nonce) is not str or not NONCE_PATTERN.fullmatch(nonce)
                    or type(record) is not dict
                    or set(record) != {"fingerprint", "request_ts_ms"}
                    or type(record["fingerprint"]) is not str
                    or not _SHA.fullmatch(record["fingerprint"])
                    or type(record["request_ts_ms"]) is not int
                    or record["request_ts_ms"] > now_ms + 300_000
                    or record["request_ts_ms"] < 1_704_067_200_000):
                target["invalid"] += 1
                continue
            if now_ms - record["request_ts_ms"] > review_horizon_ms:
                target["past_review_horizon"] += 1
    return {
        "state": "REVIEW_REQUIRED" if invalid_nodes or any(
            x["invalid"] for x in per_node.values()
        ) else "AUDITED_NO_DELETION",
        "entry_count": count,
        "invalid_node_count": invalid_nodes,
        "per_node": per_node,
        "review_horizon_ms": review_horizon_ms,
        "read_only": True,
        "cleanup_performed": False,
    }
