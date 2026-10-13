"""Impor CSV microSD N0/N1/N2 ke format history hardware_test.

Tiga keluaran (bisa digabung):

1. Ringkasan di terminal (selalu; tanpa jaringan).
2. ``--out-json FILE``: file JSON berbentuk ekspor ``hardware_test`` yang
   bisa dibuka di website lewat tombol **Buka CSV/JSON** (tanpa Firebase).
   Tambah ``--analyze`` untuk menyertakan hasil AI per slot (butuh model
   ``ai/models/tasnim_ai_bundle.joblib``).
3. ``--write``: menulis ``hardware_test/history/<slot>/<node>`` ke Firebase.
   Hanya mengisi slot yang masih KOSONG (tidak pernah menimpa), tidak
   mengubah ``nodes/latest`` maupun ``analysis``. Setelah itu jalankan
   ``python3 -m ai.realtime_inference --root hardware_test --once`` agar AI
   menganalisis seluruh backlog dan website menampilkannya.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from iot.hardware_test_history_recorder import (
    DEFAULT_CREDENTIALS, DEFAULT_DATABASE_URL, NODES, RECENT_SLOT_GUARD_MS, ROOT,
    initialize_firebase, packet_from_observation, store_packet, wita,
)
from iot.hardware_test_delete import is_deleted, load_deleted_ranges
from iot.hardware_test_legacy_history_capture_v1 import FieldCaptureRejected
from iot.sd_csv import CsvFormatError, read_csv_file

DEFAULT_MODEL = Path("ai/models/tasnim_ai_bundle.joblib")
BATCH_SIZE = 400


def build_import(readings, *, now_ms=None, deleted_ranges=()):
    """Pembacaan CSV → paket history kanonik, satu per (slot, node).

    Sampel pertama (timestamp terkecil, lalu sequence) dalam slot dipakai,
    sama dengan perekam live dan pembaca CSV di website. Baris yang masuk
    rentang di daftar hapus dilewati (``excluded_deleted``).
    """
    now = int(time.time() * 1000) if now_ms is None else now_ms
    history = {}
    latest = {}
    stats = Counter()
    rejected = Counter()
    ordered = sorted(readings, key=lambda r: (r["timestamp"], r.get("sequence", 0)))
    for reading in ordered:
        node = reading["node"]
        raw = {k: v for k, v in reading.items() if k not in ("node", "source_line")}
        try:
            packet, slot = packet_from_observation(
                raw, node, now_ms=now, allow_missing_sequence=True)
        except (FieldCaptureRejected, ValueError) as exc:
            rejected[str(exc).split(":")[-1]] += 1
            continue
        if deleted_ranges and is_deleted(deleted_ranges, slot, node):
            stats["excluded_deleted"] += 1
            continue
        stats["valid_rows"] += 1
        stats[f"rows_{node}"] += 1
        slot_record = history.setdefault(str(slot), {})
        if node in slot_record:
            stats["extra_in_slot"] += 1
        else:
            slot_record[node] = packet
        previous = latest.get(node)
        if previous is None or (packet["timestamp"], packet["sequence"]) >= (
                previous["timestamp"], previous["sequence"]):
            latest[node] = packet
    stats["slots"] = len(history)
    stats["complete_slots"] = sum(1 for rec in history.values() if all(n in rec for n in NODES))
    return {"history": history, "latest": latest, "stats": stats, "rejected": rejected}


def analyze_history(history, model_bundle):
    """Hasil AI per slot lengkap (tanpa Firebase). Return dict slot → hasil."""
    from ai.realtime_inference import build_analysis_result, history_to_frame

    frame, pending, time_mode = history_to_frame(history, ROOT, verbose=False)
    if frame is None:
        return {}
    results = {}
    now = int(time.time() * 1000)
    for target in sorted(int(t) for t in pending):
        result = build_analysis_result(
            frame, target, time_mode, model_bundle, ROOT, inference_timestamp_ms=now)
        if result is not None:
            results[str(target)] = result
    return results


def export_json(imported, analyses=None):
    history = {slot: dict(record) for slot, record in imported["history"].items()}
    latest_analysis = None
    for slot, result in sorted((analyses or {}).items(), key=lambda kv: int(kv[0])):
        history[slot]["analysis"] = result
        latest_analysis = result
    return {
        ROOT: {
            "nodes": {node: {"latest": imported["latest"].get(node)} for node in NODES},
            "history": dict(sorted(history.items(), key=lambda kv: int(kv[0]))),
            "analysis": {"latest": latest_analysis} if latest_analysis else None,
        }
    }


def write_history(db, history, *, now_ms=None, progress=print):
    """Tulis hanya (slot, node) yang masih kosong di Firebase.

    Slot lama ditulis sekaligus per batch; slot <15 menit terakhir memakai
    transaksi first-wins karena perekam live mungkin sedang menulisnya.
    """
    now = int(time.time() * 1000) if now_ms is None else now_ms
    outcome = Counter()
    pending = {}
    slots = sorted(history, key=int)
    if not slots:
        return outcome
    existing = (db.reference(f"{ROOT}/history").order_by_key()
                .start_at(slots[0]).end_at(slots[-1]).get()) or {}
    for slot in slots:
        for node, packet in history[slot].items():
            if node not in NODES:
                continue
            if isinstance(existing.get(slot), dict) and node in existing[slot]:
                outcome["already_present"] += 1
                continue
            if now - int(slot) < RECENT_SLOT_GUARD_MS:
                outcome[store_packet(db, int(slot), node, packet).lower()] += 1
                continue
            pending[f"{slot}/{node}"] = packet
    items = list(pending.items())
    for start in range(0, len(items), BATCH_SIZE):
        chunk = dict(items[start:start + BATCH_SIZE])
        db.reference(f"{ROOT}/history").update(chunk)
        outcome["captured"] += len(chunk)
        progress(f"  ... {min(start + BATCH_SIZE, len(items))}/{len(items)} paket ditulis")
    return outcome


def print_summary(imported, skipped, files):
    stats, history = imported["stats"], imported["history"]
    print(f"File           : {', '.join(str(f) for f in files)}")
    print(f"Baris valid    : {stats['valid_rows']} "
          f"(N0={stats['rows_N0']}, N1={stats['rows_N1']}, N2={stats['rows_N2']})")
    if skipped:
        reasons = Counter(s["reason"] for s in skipped)
        print(f"Baris dilewati : {len(skipped)} {dict(reasons)}")
    if stats["excluded_deleted"]:
        print(f"Daftar hapus   : {stats['excluded_deleted']} baris dilewati (rentang yang pernah dihapus)")
    if imported["rejected"]:
        print(f"Ditolak kontrak: {sum(imported['rejected'].values())} {dict(imported['rejected'])}")
    print(f"Slot 5 menit   : {stats['slots']} (lengkap 3 node: {stats['complete_slots']})")
    if stats["extra_in_slot"]:
        print(f"Sampel ekstra  : {stats['extra_in_slot']} baris berada di slot yang sama "
              "(yang pertama dipakai, sisanya tetap di CSV)")
    if history:
        slots = sorted(int(s) for s in history)
        print(f"Rentang waktu  : {wita(slots[0])} → {wita(slots[-1])}")
    flags = Counter(flag for rec in history.values() for node, p in rec.items()
                    if node in NODES for flag in p.get("quality_flags", [])
                    if flag != "BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED")
    if flags:
        print(f"Quality flags  : {dict(flags)}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Impor CSV microSD TAS[N]IM ke history hardware_test (dry-run default)")
    parser.add_argument("files", nargs="+", type=Path, help="CSV per node, mis. tasnim_N0.csv")
    parser.add_argument("--node", choices=NODES,
                        help="Node untuk CSV tanpa kolom node dan tanpa N0/N1/N2 di nama file")
    parser.add_argument("--out-json", type=Path, help="Simpan hasil sebagai JSON untuk website")
    parser.add_argument("--analyze", action="store_true",
                        help="Sertakan hasil AI per slot di --out-json (butuh model joblib)")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--write", action="store_true",
                        help="Tulis history ke Firebase (hanya slot kosong)")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--database-url",
                        default=os.getenv("TASNIM_DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args(argv)
    if args.analyze and not args.out_json:
        parser.error("--analyze dipakai bersama --out-json")

    readings, skipped = [], []
    for path in args.files:
        try:
            rows, skip = read_csv_file(path, default_node=args.node)
        except (OSError, CsvFormatError) as exc:
            raise SystemExit(f"[STOP] {exc}")
        readings.extend(rows)
        skipped.extend({**s, "file": path.name} for s in skip)

    db = None
    deleted_ranges = []
    if args.write or args.credentials.is_file() or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST"):
        db = initialize_firebase(args.credentials, args.database_url)
        deleted_ranges = load_deleted_ranges(db)
    imported = build_import(readings, deleted_ranges=deleted_ranges)
    print("TAS[N]IM impor CSV microSD → hardware_test/history")
    if db is None:
        print("[INFO] Daftar hapus tidak dicek (tanpa kunci service account).")
    print_summary(imported, skipped, [p.name for p in args.files])
    if not imported["history"]:
        raise SystemExit("[STOP] Tidak ada baris valid untuk diimpor.")

    if args.out_json:
        analyses = None
        if args.analyze:
            if not args.model.is_file():
                raise SystemExit(f"[STOP] Model AI tidak ditemukan: {args.model}")
            import joblib
            analyses = analyze_history(imported["history"], joblib.load(args.model))
            print(f"Analisis AI    : {len(analyses)} slot dianalisis "
                  "(model PROTOTYPE_SIMULATION, bukan validasi lapangan)")
        payload = export_json(imported, analyses)
        args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        size_kb = args.out_json.stat().st_size / 1024
        print(f"JSON website   : {args.out_json} ({size_kb:.0f} KB) — buka lewat tombol "
              "'Buka CSV/JSON' di website")

    if not args.write:
        print("[DRY-RUN] Firebase tidak ditulis. Tambah --write untuk mengisi hardware_test/history.")
        return
    outcome = write_history(db, imported["history"])
    print(f"[WRITE] Firebase: {dict(outcome)}")
    print("Berikutnya: python3 -m ai.realtime_inference --root hardware_test --once "
          "(AI menganalisis seluruh backlog, website otomatis menampilkan).")


if __name__ == "__main__":
    sys.exit(main())
