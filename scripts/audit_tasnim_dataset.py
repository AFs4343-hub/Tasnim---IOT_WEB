#!/usr/bin/env python3
"""Offline history audit. No Firebase connection or writes."""

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai.check_ai_readiness import audit_slot

INTERVAL = 300000
NODES = ("N0", "N1", "N2")
WITA = timezone(timedelta(hours=8))


def local_time(ms):
    return datetime.fromtimestamp(
        ms / 1000, WITA
    ).strftime("%Y-%m-%d %H:%M WITA")


def parse_time(text):
    dt = datetime.strptime(text, "%Y-%m-%dT%H:%M")
    return int(dt.replace(tzinfo=WITA).timestamp() * 1000)


def main():
    parser = argparse.ArgumentParser(
        description="TASNIM offline dataset completeness audit"
    )

    parser.add_argument(
        "--input", required=True, type=Path
    )
    parser.add_argument("--start-wita")
    parser.add_argument("--end-wita")

    args = parser.parse_args()

    if bool(args.start_wita) != bool(args.end_wita):
        parser.error(
            "Start dan end harus diberikan bersama"
        )

    snapshot = json.loads(
        args.input.read_text(encoding="utf-8")
    )

    root = snapshot.get("root")
    history = snapshot.get("history")

    if root not in ("real_test", "field"):
        raise SystemExit("[STOP] Root tidak dikenali")

    if not isinstance(history, dict):
        raise SystemExit("[STOP] Struktur history invalid")

    indexed = {}

    for key, value in history.items():
        try:
            timestamp = int(key)
        except (ValueError, TypeError):
            raise SystemExit(
                f"[STOP] Slot key invalid: {key}"
            )

        if (
            str(timestamp) != key
            or timestamp % INTERVAL != 0
        ):
            raise SystemExit(
                f"[STOP] Slot tidak valid: {key}"
            )

        indexed[timestamp] = value

    if args.start_wita:
        start = parse_time(args.start_wita)
        end = parse_time(args.end_wita)
        explicit_window = True
    elif indexed:
        start = min(indexed)
        end = max(indexed) + INTERVAL
        explicit_window = False
    else:
        print("[WARN] History kosong")
        print("[INFO] Gunakan start/end untuk audit periode tertentu")
        return

    if (
        end <= start
        or start % INTERVAL
        or end % INTERVAL
    ):
        raise SystemExit(
            "[STOP] Rentang waktu invalid atau "
            "tidak sejajar interval 5 menit"
        )

    expected = (end - start) // INTERVAL

    if expected > 100000:
        raise SystemExit("[STOP] Rentang terlalu besar")

    stats = {
        node: Counter()
        for node in NODES
    }

    present_slots = 0
    complete_slots = 0
    missing_slots = []
    invalid_slots = 0

    for timestamp in range(start, end, INTERVAL):
        record = indexed.get(timestamp)

        if not isinstance(record, dict):
            missing_slots.append(timestamp)
            for node in NODES:
                stats[node]["missing"] += 1
            continue

        present_slots += 1

        reasons = audit_slot(
            str(timestamp), record
        )

        if not reasons:
            complete_slots += 1
        else:
            invalid_slots += 1

        for node in NODES:
            packet = record.get(node)

            if not isinstance(packet, dict):
                stats[node]["missing"] += 1
                continue

            stats[node]["present"] += 1

            flags = packet.get("quality_flags", [])

            if flags:
                stats[node]["flagged"] += 1

            node_errors = [
                reason for reason in reasons
                if reason.startswith(node + ":")
            ]

            if not node_errors:
                stats[node]["gate_pass"] += 1

    print()
    print("=== TASNIM DATASET COMPLETENESS REPORT ===")
    print("Source       :", args.input)
    print("Root         :", root)
    print("Start        :", local_time(start))
    print("End exclusive:", local_time(end))
    print("Expected     :", expected)
    print("Present slots:", present_slots)
    print("Missing slots:", len(missing_slots))
    print("Complete     :", complete_slots)
    print("Incomplete   :", invalid_slots)

    print()
    print("=== COVERAGE ===")

    coverage = 100 * present_slots / expected
    completeness = 100 * complete_slots / expected

    print(f"Slot coverage     : {coverage:.2f}%")
    print(f"Complete slot rate: {completeness:.2f}%")

    for node in NODES:
        s = stats[node]

        availability = 100 * s["present"] / expected
        gate_rate = 100 * s["gate_pass"] / expected

        print()
        print(f"Node {node}")
        print(f"  Available : {s['present']}/{expected}")
        print(f"  Coverage  : {availability:.2f}%")
        print(f"  Gate pass : {s['gate_pass']}/{expected}")
        print(f"  Gate rate : {gate_rate:.2f}%")
        print(f"  Flagged   : {s['flagged']}")
        print(f"  Missing   : {s['missing']}")

    if missing_slots:
        print()
        print("=== FIRST 10 MISSING SLOTS ===")

        for timestamp in missing_slots[:10]:
            print("-", local_time(timestamp))

    outside = sum(
        not (start <= timestamp < end)
        for timestamp in indexed
    )

    if outside:
        print(
            f"[INFO] {outside} slot di luar "
            "periode audit tidak dihitung"
        )

    if not explicit_window:
        print()
        print(
            "[WARN] Periode otomatis hanya "
            "dari slot pertama sampai terakhir."
        )
        print(
            "[WARN] Ini bukan pengukuran "
            "kelengkapan enam hari."
        )

    print()
    print("[PASS] OFFLINE AUDIT COMPLETED")
    print("[PASS] Tidak membaca/menulis Firebase")
    print("[PASS] Tidak mengubah dataset")


if __name__ == "__main__":
    main()
