#!/usr/bin/env python3
"""Jalankan perekam history + AI realtime untuk hardware_test sekaligus.

Alur sama dengan mode simulasi (simulator → history → AI → website), hanya
sumbernya alat ESP32 asli:

    ESP32 → nodes/Nx/latest → [perekam] → history/<slot> → [AI] → analysis

    python3 scripts/run_hardware_test_stack.py           # dry-run (tidak menulis)
    python3 scripts/run_hardware_test_stack.py --write   # sesi lapangan

Butuh iot/serviceAccountKey.json dan ai/models/tasnim_ai_bundle.joblib.
Ctrl+C menghentikan keduanya.
"""
import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pump(name, process):
    for line in process.stdout:
        print(f"[{name}] {line}", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true",
                        help="Tulis history dan hasil AI ke Firebase (default dry-run)")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="Jeda polling perekam dalam detik")
    args = parser.parse_args()

    missing = [p for p in ("iot/serviceAccountKey.json", "ai/models/tasnim_ai_bundle.joblib")
               if not (ROOT / p).is_file()]
    if missing:
        raise SystemExit("[STOP] File belum ada: " + ", ".join(missing)
                         + "\n       Lihat docs/PANDUAN_WEBSITE_DATA_ALAT.md bagian Persiapan.")

    recorder = [sys.executable, "-u", "-m", "iot.hardware_test_history_recorder",
                "--interval", str(args.interval)]
    ai = [sys.executable, "-u", "-m", "ai.realtime_inference", "--root", "hardware_test"]
    if args.write:
        recorder.append("--write")
    else:
        ai.append("--dry-run")

    print("TAS[N]IM hardware_test stack:", "WRITE" if args.write else "DRY-RUN")
    processes = []
    try:
        for name, command in (("REKAM", recorder), ("AI", ai)):
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
            processes.append(process)
            threading.Thread(target=pump, args=(name, process), daemon=True).start()
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        print("[STOP] Salah satu proses berhenti; menghentikan yang lain.")
    except KeyboardInterrupt:
        print("\nMenghentikan perekam dan AI...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    codes = [p.returncode for p in processes]
    return 0 if all(code in (0, -15, None) for code in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
