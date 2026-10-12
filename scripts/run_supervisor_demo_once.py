#!/usr/bin/env python3
"""One-shot, expressly invoked TASNIM demo supervisor; NEVER LIVE.

Run in a second Codespaces terminal WHILE
bash scripts/run_hardware_demo_codespaces.sh is running in terminal one.

  python3 scripts/run_supervisor_demo_once.py --preview  # NO DB writes
  python3 scripts/run_supervisor_demo_once.py --run      # demo ONLY; one cycle
  python3 scripts/run_supervisor_demo_once.py --status   # NO DB writes

The predictor here is a deterministic SYNTHETIC fixture, NOT a trained AI model.
No daemon, no auto-triggering, no Firebase service account, no LIVE fallback.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "demo-tasnim-security"
DB_HOST = "127.0.0.1:19003"
AUTH_HOST = "127.0.0.1:19004"
URL = f"http://{DB_HOST}/?ns={PROJECT}-default-rtdb"
SESSION = "SYNTHETIC_BROWSER_DEMO"
MODEL = "SYNTHETIC_DEMO_ONLY"


def refuse(message):
    raise RuntimeError("REFUSED: " + message)


def validate_local_configuration():
    """Fail before any Firebase initialization or database access."""
    if Path.cwd().resolve() != ROOT:
        refuse("run from the repository root")
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if branch != "infra/field-data":
        refuse("expected infra/field-data branch")

    cfg = json.loads((ROOT / "tasnim.config.json").read_text())
    live = json.loads((ROOT / "firebase.json").read_text())
    emulator = json.loads((ROOT / "firebase.emulator.security.json").read_text())
    if cfg != {"activeDataRoot": "simulation", "mode": "SIMULATION"}:
        refuse("website configuration is not SIMULATION")
    if live.get("database", {}).get("rules") != "database.rules.json":
        refuse("production Firebase config changed")
    if emulator.get("database", {}).get("rules") != "database.hardware_test.v2.candidate.rules.json":
        refuse("unexpected emulator security rules")
    emulators = emulator.get("emulators", {})
    if emulators.get("auth") != {"host": "127.0.0.1", "port": 19004}:
        refuse("unexpected Auth Emulator endpoint")
    if emulators.get("database") != {"host": "127.0.0.1", "port": 19003}:
        refuse("unexpected Database Emulator endpoint")
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        refuse("remove GOOGLE_APPLICATION_CREDENTIALS from this demo terminal")
    for key, allowed in (
        ("GCLOUD_PROJECT", PROJECT),
        ("FIREBASE_DATABASE_EMULATOR_HOST", DB_HOST),
        ("FIREBASE_AUTH_EMULATOR_HOST", AUTH_HOST),
        ("TASNIM_AI_WORKER_EMULATOR_ONLY", "YES"),
        ("TASNIM_AI_COORDINATION_EMULATOR_ONLY", "YES"),
    ):
        if os.getenv(key) not in (None, "", allowed):
            refuse(f"{key} conflicts with explicit demo settings")
        os.environ[key] = allowed

    # Both emulators must already be running; do NOT spawn any.
    for port in (19003, 19004):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                pass
        except OSError:
            refuse(f"localhost port {port} is not running; start browser demo first")


def predictor(frame, bundle):
    """Fixed synthetic fixture labels, not model inference or scientific proof."""
    return {
        "session_id": str(frame.iloc[-1]["session_id"]),
        "status": "NORMAL",
        "timestamp": "SYNTHETIC_DEMO_ONLY",
        "location": None,
        "random_forest": {"prediction": "NORMAL", "confidence": 0.55},
        "isolation_forest": {"is_anomaly": False, "decision_score": 0.1},
        "dominant_zscore": {
            "node": "N0", "parameter": "tds", "zscore": 0.2,
        },
    }


def confirm_demo_fixture(adapter):
    """Reject foreign demo records; never clear or reset an analysis marker."""
    history = adapter.reference("hardware_test/history").get()
    latest = adapter.reference("hardware_test/analysis/latest").get()
    from ai.hardware_test_history_v2 import prepare_backlog

    if not isinstance(history, dict) or not 2 <= len(history) <= 20:
        refuse("expected small pre-seeded synthetic browser-demo history")
    if not isinstance(latest, dict) or latest.get("session_id") != SESSION \
            or latest.get("model_version") != MODEL \
            or latest.get("model_stage") != "PROTOTYPE_SIMULATION":
        refuse("latest marker is not the canonical synthetic demo fixture")
    # Worker performs complete provenance and checkpoint validation before
    # proceeding. This first check just prevents human operator confusion.
    plan = prepare_backlog(
        history, session_id=SESSION, expected_model_version=MODEL,
    )
    if not plan["rows"] or latest.get("source_timestamp_ms") != plan["rows"][-1]["source_timestamp_ms"]:
        refuse("latest marker does not belong to the most recent complete demo slot")


def execute(mode):
    validate_local_configuration()
    sys.path.insert(0, str(ROOT))
    # Firebase is imported ONLY after all fixed demo guards have succeeded.
    import firebase_admin
    from firebase_admin import db
    from ai.hardware_test_supervisor_v1 import run_supervised_emulator_cycle
    from ai.hardware_test_supervisor_status_v1 import STATUS_PATH
    from ai.hardware_test_supervisor_feed_v1 import FEED_PATH

    class LocalDemoAdapter:
        emulator_only = True
        emulator_project = PROJECT
        emulator_host = DB_HOST

        def __init__(self, app):
            self.app = app

        def reference(self, path):
            return db.reference(path, app=self.app)

    app = firebase_admin.initialize_app(
        options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
        name="tasnim-one-shot-demo-supervisor",
    )
    try:
        adapter = LocalDemoAdapter(app)
        if mode == "status":
            # Status-only read, no model or worker writes.
            private = adapter.reference(STATUS_PATH).get()
            feed = adapter.reference(FEED_PATH).get()
            print(json.dumps({
                "status": private if type(private) is dict else None,
                "browser_feed_matches": private is not None and private == feed,
            }, sort_keys=True))
            return 0
        confirm_demo_fixture(adapter)
        dry_run = mode == "preview"
        report = run_supervised_emulator_cycle(
            adapter, session_id=SESSION, model_version=MODEL,
            model_bundle=None, predict_fn=predictor,
            dry_run=dry_run, record_status=not dry_run,
            max_actions_per_cycle=3, max_source_slots=20,
            max_attempts=2,
        )
        print("[SAFE] Fixed localhost demo project; synthetic predictor only.")
        print(json.dumps(report, sort_keys=True))
        if not dry_run:
            private = adapter.reference(STATUS_PATH).get()
            public = adapter.reference(FEED_PATH).get()
            if private != public or not report["status_persisted"] \
                    or not report["feed_persisted"]:
                print("[STOP] private/browser status mismatch; manual review required.")
                return 2
        return 0 if report["state"] in ("PREVIEW", "PROCESSED", "IDLE") else 2
    finally:
        firebase_admin.delete_app(app)


def main():
    parser = argparse.ArgumentParser(description="Explicit localhost demo supervisor")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preview", action="store_true",
                       help="read-only plan; no lock/AI/status writes")
    modes.add_argument("--run", action="store_true",
                       help="ONE supervised synthetic demo cycle (writes Emulator ONLY)")
    modes.add_argument("--status", action="store_true",
                       help="read-only status and browser feed check")
    args = parser.parse_args()
    return execute("preview" if args.preview else "run" if args.run else "status")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as error:
        # Never print model/DB exception internals or credentials.
        print("[STOP] Demo supervisor refused or requires review:", type(error).__name__)
        sys.exit(2)
