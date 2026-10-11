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
    parser.add_argument(
        "--write-real-test",
        action="store_true",
        help="Aktifkan penulisan ke REAL_TEST saja",
    )
    parser.add_argument(
        "--confirm-write",
        default=None,
        metavar="PHRASE",
        help="Konfirmasi eksplisit REAL_TEST_ONLY",
    )

    args = parser.parse_args()

    # TASNIM_REAL_TEST_WRITE_GATE_V1
    if args.write_real_test:
        if args.confirm_write != "REAL_TEST_ONLY":
            parser.error(
                "WRITE ditolak: gunakan "
                "--confirm-write REAL_TEST_ONLY"
            )
    elif args.confirm_write is not None:
        parser.error(
            "--confirm-write hanya boleh bersama "
            "--write-real-test"
        )

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
    ]

    if args.write_real_test:
        bridge.append("--write")
    else:
        ai.append("--dry-run")

    print("=== TASNIM REAL_TEST STACK ===", flush=True)
    if args.write_real_test:
        print("[WRITE] REAL_TEST ONLY — EXPLICIT OPT-IN", flush=True)
        print("[WRITE] Bridge dan AI boleh menulis REAL_TEST", flush=True)
    else:
        print("[SAFE] Bridge READ ONLY", flush=True)
        print("[SAFE] AI DRY-RUN", flush=True)
        print("[SAFE] Tidak ada Firebase write", flush=True)

    print("[SAFE] SIMULATION config tetap", flush=True)

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
        # Simpan setiap proses segera agar finally tetap
        # dapat membersihkan proses pertama jika proses kedua gagal.
        children.append(
            subprocess.Popen(
                bridge + ["--interval", "15"],
                cwd=ROOT,
                start_new_session=True,
            )
        )
        children.append(
            subprocess.Popen(
                ai,
                cwd=ROOT,
                start_new_session=True,
            )
        )

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
