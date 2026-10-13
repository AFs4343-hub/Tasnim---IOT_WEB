#!/usr/bin/env python3
"""TAS[N]IM — perekam history hardware_test (latest → history 5 menit).

Firmware ESP32 saat ini hanya menulis ``hardware_test/nodes/<Nx>/latest``.
Perekam ini membaca latest secara berkala lalu mengarsipkan setiap
pengukuran baru ke ``hardware_test/history/<slot_ms>/<Nx>`` sehingga
website (grafik, statistik, History) dan AI punya deret waktu, sama seperti
alur simulasi (simulator → history → AI → website).

Aturan:
- DRY-RUN secara default. Penulisan hanya dengan ``--write``.
- Hanya menulis ``hardware_test/history``. Tidak pernah mengubah
  ``nodes/latest``, ``analysis``, ``simulation`` atau Rules.
- ``slot_ms = floor(timestamp / 300000) * 300000`` (timestamp = waktu ukur).
- Slot immutable: sampel PERTAMA node pada slot dipertahankan; retry yang
  identik tidak mengubah apa pun; sampel lain di slot yang sama dilewati.
- Nilai sensor di luar rentang tidak diubah menjadi angka palsu: field
  dihilangkan dan diberi quality flag (mis. PH_INVALID).

Jalankan dari root repo (butuh ``iot/serviceAccountKey.json``)::

    python3 -m iot.hardware_test_history_recorder            # dry-run
    python3 -m iot.hardware_test_history_recorder --write    # rekam terus
    python3 -m iot.hardware_test_history_recorder --write --once
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from iot.hardware_test_contract_v2 import ContractError, NODE_IDS, SLOT_MS
from iot.hardware_test_ingestion_core import stored_packet_matches
from iot.hardware_test_legacy_history_capture_v1 import (
    FieldCaptureRejected, normalize_legacy_observation,
)

ROOT = "hardware_test"
NODES = ("N0", "N1", "N2")
DEFAULT_DATABASE_URL = (
    "https://omirisetmonitoring-default-rtdb."
    "asia-southeast1.firebasedatabase.app"
)
DEFAULT_CREDENTIALS = Path("iot/serviceAccountKey.json")
WITA = timezone(timedelta(hours=8))
# Slot yang lebih tua dari ini aman ditulis sekaligus (batch) karena
# perekam live hanya menulis slot terbaru.
RECENT_SLOT_GUARD_MS = 15 * 60 * 1000


class RecorderError(RuntimeError):
    pass


def wita(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, WITA).strftime("%d/%m %H:%M:%S WITA")


def _as_int(value):
    """RTDB/JSON bisa mengembalikan 1.79e12 sebagai float bernilai bulat."""
    if type(value) is float and value.is_integer():
        return int(value)
    return value


def packet_from_observation(raw, node, *, now_ms, allow_missing_sequence=False):
    """Ubah satu pengukuran mentah (latest Firebase / baris CSV) menjadi
    paket history kanonik. Mengembalikan ``(packet, slot_ms)``.

    Raise ``FieldCaptureRejected`` jika timestamp/sequence/node tidak valid.
    """
    if node not in NODE_IDS or not isinstance(raw, dict):
        raise FieldCaptureRejected("field_history:invalid_node_or_payload")
    source = dict(raw)
    for key in ("timestamp", "sequence"):
        if key in source:
            source[key] = _as_int(source[key])
    if allow_missing_sequence and source.get("sequence") is None:
        # Sequence hanya metadata pengiriman, bukan nilai ukur.
        source["sequence"] = 0
    try:
        packet, slot = normalize_legacy_observation(source, node, now_ms=now_ms)
    except ContractError as exc:
        raise FieldCaptureRejected(str(exc)) from exc
    sample_id = raw.get("sample_id")
    if isinstance(sample_id, str) and re.fullmatch(rf"{node}_[A-Za-z0-9_-]{{1,80}}", sample_id):
        packet["sample_id"] = sample_id
    return packet, slot


def store_packet(db, slot, node, packet):
    """Simpan satu paket secara immutable (transaksi first-wins).

    Return: ``CAPTURED`` (baru), ``DUPLICATE`` (identik sudah ada) atau
    ``SLOT_TAKEN`` (slot node sudah berisi sampel lain; tidak ditimpa).
    """
    created = [False]

    def first_wins(old):
        created[0] = old is None
        return dict(packet) if old is None else old

    stored = db.reference(f"{ROOT}/history/{slot}/{node}").transaction(first_wins)
    if created[0] and stored_packet_matches(stored, packet):
        return "CAPTURED"
    if stored_packet_matches(stored, packet):
        return "DUPLICATE"
    return "SLOT_TAKEN"


def record_once(db, *, now_ms=None, write=False, seen=None):
    """Satu putaran: baca ketiga latest, arsipkan yang baru.

    ``seen`` (dict node → (timestamp, sequence)) mencegah transaksi ulang
    untuk sampel yang sama pada polling berikutnya.
    """
    now = int(time.time() * 1000) if now_ms is None else now_ms
    seen = {} if seen is None else seen
    latest_all = db.reference(f"{ROOT}/nodes").get() or {}
    if not isinstance(latest_all, dict):
        raise RecorderError("hardware_test/nodes bukan objek")
    outcomes = {}
    for node in NODES:
        raw = (latest_all.get(node) or {}).get("latest") if isinstance(latest_all.get(node), dict) else None
        if raw is None:
            outcomes[node] = ("NO_DATA", None, None)
            continue
        try:
            packet, slot = packet_from_observation(raw, node, now_ms=now)
        except FieldCaptureRejected as exc:
            outcomes[node] = ("REVIEW_REQUIRED", None, str(exc))
            continue
        identity = (packet["timestamp"], packet["sequence"])
        if seen.get(node) == identity:
            outcomes[node] = ("UNCHANGED", slot, packet)
            continue
        if not write:
            outcomes[node] = ("WOULD_CAPTURE", slot, packet)
            seen[node] = identity
            continue
        state = store_packet(db, slot, node, packet)
        seen[node] = identity
        outcomes[node] = (state, slot, packet)
    return outcomes


def initialize_firebase(credentials_path: Path, database_url: str):
    import firebase_admin
    from firebase_admin import credentials, db

    if not firebase_admin._apps:
        emulator = os.getenv("FIREBASE_DATABASE_EMULATOR_HOST")
        if emulator:
            firebase_admin.initialize_app(options={
                "databaseURL": database_url,
                "projectId": os.getenv("GCLOUD_PROJECT", "demo-tasnim"),
            })
        else:
            if not credentials_path.is_file():
                raise SystemExit(
                    f"[STOP] Service account tidak ditemukan: {credentials_path}\n"
                    "       Unduh dari Firebase Console → Project settings → "
                    "Service accounts, simpan ke iot/serviceAccountKey.json "
                    "(sudah di-.gitignore, JANGAN di-commit)."
                )
            firebase_admin.initialize_app(
                credentials.Certificate(str(credentials_path)),
                {"databaseURL": database_url},
            )
    return db


def _describe(node, outcome):
    state, slot, detail = outcome
    if state in ("NO_DATA", "UNCHANGED"):
        return None
    if state == "REVIEW_REQUIRED":
        return f"{node} | PERIKSA  | latest ditolak: {detail}"
    packet = detail
    values = " ".join(
        f"{key}={packet[key]}" for key in ("ph", "tds", "turbidity") if key in packet
    )
    flags = ",".join(f for f in packet.get("quality_flags", [])
                     if f != "BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED")
    label = {
        "CAPTURED": "TEREKAM",
        "DUPLICATE": "SUDAH ADA",
        "SLOT_TAKEN": "SLOT TERISI",
        "WOULD_CAPTURE": "DRY-RUN",
    }.get(state, state)
    return (f"{node} | {label:<11}| slot {wita(slot)} | ukur {wita(packet['timestamp'])}"
            f" | seq={packet['sequence']} {values}" + (f" | flag={flags}" if flags else ""))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rekam hardware_test/nodes/*/latest ke hardware_test/history (slot 5 menit)",
    )
    parser.add_argument("--write", action="store_true",
                        help="Benar-benar menulis history (default: dry-run)")
    parser.add_argument("--once", action="store_true", help="Satu putaran lalu berhenti")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="Jeda polling dalam detik (default 15)")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--database-url",
                        default=os.getenv("TASNIM_DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args(argv)
    if not 2 <= args.interval <= 600:
        parser.error("--interval harus 2–600 detik")

    db = initialize_firebase(args.credentials, args.database_url)
    mode = "WRITE" if args.write else "DRY-RUN (tidak menulis; tambah --write)"
    print("TAS[N]IM perekam history hardware_test")
    print(f"[MODE] {mode} | interval {args.interval:g} s | Ctrl+C untuk berhenti")
    seen = {}
    try:
        while True:
            try:
                outcomes = record_once(db, write=args.write, seen=seen)
            except Exception as exc:  # jaringan putus dsb.: coba lagi
                print(f"[WARN] Gagal membaca/menulis Firebase: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
                outcomes = {}
            for node in NODES:
                if node in outcomes:
                    line = _describe(node, outcomes[node])
                    if line:
                        print(line, flush=True)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nPerekam dihentikan.")


if __name__ == "__main__":
    main()
