"""Seed fake test-only accounts and sensor data in *local* Firebase emulators.

No credentials, no LIVE project, no production hostname, no invocation at
module import. Used only by scripts/test_hardware_auth_emulator.sh.
"""
import os
import sys
import time
from pathlib import Path

DEMO_PROJECT = "demo-tasnim-security"
AUTH_HOST = "127.0.0.1:19004"
DB_HOST = "127.0.0.1:19003"
DB_URL = f"http://{DB_HOST}/?ns={DEMO_PROJECT}-default-rtdb"
TEST_PASSWORD = "EmulatorOnly_2026_Test!"
DEMO_SUPERVISOR_SESSION = "SYNTHETIC_BROWSER_DEMO"
DEMO_SUPERVISOR_MODEL = "SYNTHETIC_DEMO_ONLY"
SLOT = 1_791_724_500_000


def require_local_emulator():
    if (
        os.getenv("TASNIM_AUTH_TEST_EMULATOR_ONLY") != "YES"
        or os.getenv("GCLOUD_PROJECT") != DEMO_PROJECT
        or os.getenv("FIREBASE_AUTH_EMULATOR_HOST") != AUTH_HOST
        or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != DB_HOST
    ):
        raise RuntimeError("REFUSED: Auth integration seed is local demo only")


def sample(node, slot=SLOT, sequence=1):
    return {
        "schema_version": 2,
        "node_id": node,
        "sample_id": f"{node}_{slot + 1000}_{sequence}",
        "timestamp": slot + 1000,
        "sequence": sequence,
        "ph": 7.0 + {"N0": 0, "N1": 0.15, "N2": -0.10}[node],
        "tds": 210.0 + {"N0": 0, "N1": 30, "N2": 20}[node],
        "turbidity": 12.0 + {"N0": 0, "N1": 2, "N2": 3}[node],
    }


def main():
    require_local_emulator()  # Guard BEFORE any imports or network calls.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if len(sys.argv) not in (1, 3):
        raise ValueError("usage: seed_hardware_auth_emulator.py [--set-viewer-role none|viewer]")

    # These imports are intentionally after the explicit environment guard.
    import firebase_admin
    from firebase_admin import auth, db

    app = firebase_admin.initialize_app(
        options={"projectId": DEMO_PROJECT, "databaseURL": DB_URL},
        name="tasnim-auth-demo-seeder",
    )
    try:
        if len(sys.argv) == 3:
            if sys.argv[1:] != ["--set-viewer-role", "none"] and sys.argv[1:] != ["--set-viewer-role", "viewer"]:
                raise ValueError("invalid role update request")
            claims = None if sys.argv[2] == "none" else {"tasnim_role": "viewer"}
            auth.set_custom_user_claims("tasnim-auth-viewer", claims, app=app)
            print("[PASS] Emulator-only viewer role changed")
            return

        for role in ("admin", "manager", "viewer", "unknown", "device", "badrole"):
            uid = f"tasnim-auth-{role}"
            auth.create_user(
                uid=uid,
                email=f"{role}@tasnim-auth-demo.invalid",
                password=TEST_PASSWORD,
                app=app,
            )
            claim = (
                {"tasnim_role": role}
                if role in ("admin", "manager", "viewer") else
                {"tasnim_role": "device"} if role == "device" else
                {"tasnim_role": "Admin"} if role == "badrole" else None
            )
            if claim is not None:
                auth.set_custom_user_claims(uid, claim, app=app)

        # Keep original fixed slot for reproducible API regression tests.
        # Add three fresh synthetic slots for a useful browser demonstration.
        now_slot = (int(time.time() * 1000) // 300_000) * 300_000
        slots = [now_slot - 600_000, now_slot - 300_000, now_slot]
        history = {str(SLOT): {n: sample(n) for n in ("N0", "N1", "N2")}}
        for seq, slot in enumerate(slots, start=2):
            packets = {n: sample(n, slot, seq) for n in ("N0", "N1", "N2")}
            if seq == 3:
                packets.pop("N2")  # Demonstrate missing history without fake zero.
            history[str(slot)] = packets
        # Seed a real, canonical *synthetic* checkpoint. The previous
        # display-only analysis/latest lacked an archived history record and
        # caused the guarded worker to (correctly) refuse every demo run.
        # No ML inference: all labels are explicitly synthetic fixture data.
        from ai.hardware_test_history_v2 import prepare_backlog
        from ai.hardware_test_worker_v2 import context_digests
        from ai.hardware_test_preview_v2 import annotate_preview
        from ai.hardware_test_analysis_writer_v2 import prepare_analysis_record

        plan = prepare_backlog(
            history, session_id=DEMO_SUPERVISOR_SESSION,
            expected_model_version=DEMO_SUPERVISOR_MODEL,
        )
        preview = annotate_preview({
            "session_id": DEMO_SUPERVISOR_SESSION,
            "status": "NORMAL",
            "timestamp": "SYNTHETIC_DEMO_ONLY",
            "location": None,
            "random_forest": {"prediction": "NORMAL", "confidence": 0.55},
            "isolation_forest": {"is_anomaly": False, "decision_score": 0.1},
            "dominant_zscore": {"node": "N0", "parameter": "tds", "zscore": 0.2},
        }, slot=slots[-1], time_mode=plan["time_mode"])
        preview["source_digest_sha256"] = context_digests(history, plan)[slots[-1]]
        latest_marker = prepare_analysis_record(
            preview, model_version=DEMO_SUPERVISOR_MODEL,
            inference_timestamp_ms=int(time.time() * 1000),
        )
        history[str(slots[-1])]["analysis"] = latest_marker
        nodes = {n: sample(n, slots[-1], 4) for n in ("N0", "N1", "N2")}
        db.reference("hardware_test", app=app).set({
            "nodes": {n: {"latest": packet} for n, packet in nodes.items()},
            "history": history,
            "analysis": {"latest": latest_marker},
        })
        db.reference("gateway_state/nonces/N0/test-only", app=app).set(
            {"fingerprint": "synthetic-only"}
        )
        print("[PASS] Emulator Auth accounts and RTDB fixtures seeded")
    finally:
        firebase_admin.delete_app(app)


if __name__ == "__main__":
    main()
