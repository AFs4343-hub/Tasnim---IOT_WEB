#!/usr/bin/env python3
"""TASNIM REAL_TEST Bridge + AI supervisor. DRY-RUN ONLY."""

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(
        description="TASNIM REAL_TEST safe dry-run supervisor"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Jalankan Bridge dan AI bersama sampai Ctrl+C",
    )
    args = parser.parse_args()

    config_path = ROOT / "tasnim.config.json"
    config = json.loads(config_path.read_text())

    if (
        config.get("activeDataRoot") != "simulation"
        or config.get("mode") != "SIMULATION"
    ):
        raise SystemExit(
            "[STOP] Konfigurasi utama bukan SIMULATION"
        )

    required = [
        ROOT / "iot/serviceAccountKey.json",
        ROOT / "iot/real_test_bridge_v2.py",
        ROOT / "ai/realtime_inference.py",
    ]

    for path in required:
        if not path.is_file():
            raise SystemExit(f"[STOP] File tidak ditemukan: {path}")

    bridge = [
        sys.executable, "-u",
        "iot/real_test_bridge_v2.py",
    ]

    ai = [
        sys.executable, "-u", "-m",
        "ai.realtime_inference",
        "--root", "real_test",
        "--dry-run",
    ]

    print("=== TASNIM REAL_TEST STACK ===", flush=True)
    print("[SAFE] Bridge READ ONLY", flush=True)
    print("[SAFE] AI DRY-RUN", flush=True)
    print("[SAFE] SIMULATION config tetap", flush=True)
    print("[SAFE] Tidak ada Firebase write", flush=True)

    if not args.continuous:
        subprocess.run(
            bridge + ["--once"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ai + ["--once"],
            cwd=ROOT,
            check=True,
        )
        print("[PASS] SAFE STACK ONE-CYCLE TEST")
        return 0

    children = []

    try:
        children = [
            subprocess.Popen(
                bridge + ["--interval", "15"],
                cwd=ROOT,
                start_new_session=True,
            ),
            subprocess.Popen(
                ai,
                cwd=ROOT,
                start_new_session=True,
            ),
        ]

        print("[RUNNING] Bridge + AI aktif", flush=True)

        while True:
            for name, process in zip(
                ("BRIDGE", "AI"), children
            ):
                code = process.poll()
                if code is not None:
                    print(
                        f"[STOP] {name} berhenti: exit={code}",
                        flush=True,
                    )
                    return 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[STOP] Ctrl+C diterima", flush=True)

    finally:
        for process in children:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)

        for process in children:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        print("[STOP] Kedua proses dihentikan", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
