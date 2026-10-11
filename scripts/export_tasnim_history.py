#!/usr/bin/env python3
"""Read-only TASNIM history snapshot. No Firebase writes."""

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

from ai.check_ai_readiness import audit_slot

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = Path("/workspaces/TASNIM_PRIVATE_BACKUPS")
NODES = ("N0", "N1", "N2")
DB_URL = (
    "https://omirisetmonitoring-default-rtdb."
    "asia-southeast1.firebasedatabase.app"
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        required=True,
        choices=("real_test", "field"),
    )
    args = parser.parse_args()

    config = json.loads(
        (ROOT / "tasnim.config.json").read_text()
    )
    if (
        config.get("activeDataRoot") != "simulation"
        or config.get("mode") != "SIMULATION"
    ):
        raise SystemExit("[STOP] Konfigurasi bukan SIMULATION")

    key = ROOT / "iot/serviceAccountKey.json"
    if not key.is_file():
        raise SystemExit("[STOP] Firebase credential tidak ditemukan")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(key)),
            {"databaseURL": DB_URL},
        )

    print(f"[READ] /{args.root}/history", flush=True)

    history = db.reference(
        f"{args.root}/history"
    ).get()

    if history is None:
        history = {}

    if not isinstance(history, dict):
        raise SystemExit("[STOP] Struktur history tidak sesuai")

    # Lokasi penyimpanan selalu di luar repository.
    assert not BACKUP_DIR.resolve().is_relative_to(
        ROOT.resolve()
    )

    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )

    folder = BACKUP_DIR / f"{args.root}_{stamp}"
    folder.mkdir(mode=0o700)

    json_path = folder / "history.json"
    csv_path = folder / "history.csv"
    report_path = folder / "report.json"

    snapshot = {
        "root": args.root,
        "exported_at_utc": stamp,
        "history": history,
    }

    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, ensure_ascii=False)

    fields = [
        "slot_ms",
        "node",
        "timestamp",
        "ph",
        "tds",
        "turbidity",
        "sequence",
        "rssi",
        "source",
        "status",
        "quality_flags",
        "slot_valid",
        "gate_reasons",
        "has_analysis",
    ]

    candidates = 0
    incomplete = 0
    total_rows = 0

    with csv_path.open(
        "x", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()

        for slot_key, record in sorted(history.items()):
            reasons = audit_slot(slot_key, record)

            if reasons:
                incomplete += 1
            else:
                candidates += 1

            slot = record if isinstance(record, dict) else {}

            for node in NODES:
                packet = slot.get(node)
                packet = packet if isinstance(packet, dict) else {}

                row = {
                    "slot_ms": slot_key,
                    "node": node,
                    "timestamp": packet.get("timestamp"),
                    "ph": packet.get("ph"),
                    "tds": packet.get("tds"),
                    "turbidity": packet.get("turbidity"),
                    "sequence": packet.get("sequence"),
                    "rssi": packet.get("rssi"),
                    "source": packet.get("source"),
                    "status": packet.get("status"),
                    "quality_flags": json.dumps(
                        packet.get("quality_flags", [])
                    ),
                    "slot_valid": not bool(reasons),
                    "gate_reasons": json.dumps(reasons),
                    "has_analysis": isinstance(
                        slot.get("analysis"), dict
                    ),
                }

                writer.writerow(row)
                total_rows += 1

    report = {
        "data_root": args.root,
        "exported_at_utc": stamp,
        "total_slots": len(history),
        "complete_candidates": candidates,
        "incomplete_slots": incomplete,
        "csv_rows": total_rows,
        "note": (
            "Candidate hanya lolos pemeriksaan struktur, "
            "bukan bukti akurasi sensor atau validitas AI."
        ),
        "sha256": {
            "history.json": sha256(json_path),
            "history.csv": sha256(csv_path),
        },
    }

    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)

    for path in (json_path, csv_path, report_path):
        os.chmod(path, 0o600)

    print("[PASS] Firebase READ ONLY")
    print("[PASS] JSON + CSV + report dibuat")
    print("History slots :", len(history))
    print("Candidates    :", candidates)
    print("Incomplete    :", incomplete)
    print("CSV rows      :", total_rows)
    print("Backup folder :", folder)
    print("[PASS] Tidak ada Firebase write")


if __name__ == "__main__":
    main()
