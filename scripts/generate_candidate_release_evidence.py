#!/usr/bin/env python3
"""Create CI evidence for LOCAL/SYNTHETIC candidate verification, never LIVE.

Call only AFTER the corresponding workflow checks have passed. The evidence
is scoped to the current job, and does not claim the other CI job passed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from check_production_baseline_guard import verify_production_baseline

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    "offline": [
        "production_baseline_hashes",
        "python_synthetic_unit_regressions",
        "node_read_only_dashboard_contract",
        "vite_website_build",
    ],
    "emulator": [
        "production_baseline_hashes",
        "local_auth_and_rtdb_rules",
        "signed_http_gateway_to_worker_to_browser",
        "transaction_fault_and_demo_restore_rehearsals",
    ],
}
BLOCKERS = [
    "production_https_gateway_and_edge_rate_limits_not_approved",
    "device_secret_rotation_and_nonce_gc_policy_not_approved",
    "backups_monitoring_and_rollback_for_live_not_approved",
    "cross_path_atomicity_and_provenance_fencing_not_established",
    "model_not_field_validated",
    "final_firmware_and_physical_calibration_deferred",
    "firebase_live_or_main_change_requires_explicit_approval",
]


def evidence(scope, *, revision, runner="local"):
    if scope not in SCOPES:
        raise ValueError("release_evidence:invalid_scope")
    files = verify_production_baseline(ROOT)
    return {
        "schema_version": 1,
        "project": "TASNIM",
        "branch": "infra/field-data",
        "revision": revision,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner": runner,
        "scope": scope,
        "checks_completed_before_report": SCOPES[scope],
        "frozen_production_files_checked": len(files),
        "candidate_status": "TESTED_IN_NAMED_SCOPE",
        "release_decision": "LIVE_DEPLOYMENT_BLOCKED",
        "production_blockers": BLOCKERS,
        "firmware_stage": "LAST_STAGE_NOT_INTEGRATED",
        "real_field_accuracy_verified": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scope", required=True, choices=sorted(SCOPES))
    p.add_argument("--output", required=True)
    args = p.parse_args()
    report = evidence(
        args.scope, revision=os.getenv("GITHUB_SHA", "LOCAL_UNVERIFIED_SHA"),
        runner="github-actions" if os.getenv("GITHUB_ACTIONS") == "true"
        else "manual",
    )
    target = Path(args.output)
    if not target.parent.is_dir() or target.is_symlink() or target.exists():
        raise ValueError("release_evidence:invalid_output_path")
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("[PASS] Candidate evidence written for scope:", args.scope)
    print("[SAFE] LIVE remains BLOCKED; report includes no keys or readings")


if __name__ == "__main__":
    main()
