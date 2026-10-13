#!/usr/bin/env python3
"""Hapus data history hardware_test dengan aman (cadangan otomatis).

Contoh (waktu dalam WITA):

  # 1) Cek dulu — tidak menghapus apa pun
  python3 scripts/hapus_data.py --dari "2026-10-12 00:00" --sampai "2026-10-13 09:30" --alasan "uji coba"

  # 2) Hapus (ketik HAPUS untuk konfirmasi)
  python3 scripts/hapus_data.py --dari "2026-10-12 00:00" --sampai "2026-10-13 09:30" --alasan "uji coba" --hapus

  # Hanya node tertentu
  python3 scripts/hapus_data.py --dari "2026-10-14 10:15" --sampai "2026-10-14 10:25" --node N1 --alasan "sensor terangkat" --hapus

  # Lihat riwayat penghapusan / pulihkan
  python3 scripts/hapus_data.py --daftar
  python3 scripts/hapus_data.py --pulihkan 20261014_103000_ab12

Data yang dihapus disimpan di tempat sampah Firebase (tasnim_trash) dan file
backups/hapus_<id>.json. Rentangnya masuk daftar hapus sehingga impor CSV
dan perekam live tidak memasukkannya lagi. CSV asli tidak diubah.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from iot.hardware_test_delete import (  # noqa: E402
    DeleteError, NODES, apply_delete, describe_plan, list_batches, plan_delete, restore,
)
from iot.hardware_test_history_recorder import (  # noqa: E402
    DEFAULT_CREDENTIALS, DEFAULT_DATABASE_URL, initialize_firebase,
)
from iot.sd_csv import parse_timestamp  # noqa: E402


def parse_wita(text, label):
    ms = parse_timestamp(text)
    if ms is None:
        raise SystemExit(f"[STOP] {label} tidak valid: {text!r}. Format: \"YYYY-MM-DD HH:MM\" (WITA)")
    return ms


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hapus data hardware_test dengan cadangan otomatis")
    parser.add_argument("--dari", help='awal rentang WITA, mis. "2026-10-12 00:00"')
    parser.add_argument("--sampai", help='akhir rentang WITA, mis. "2026-10-13 09:30"')
    parser.add_argument("--node", action="append", choices=NODES,
                        help="node yang dihapus (boleh diulang); default semua node")
    parser.add_argument("--alasan", default="", help="alasan penghapusan (wajib saat --hapus)")
    parser.add_argument("--hapus", action="store_true", help="benar-benar hapus (default: hanya cek)")
    parser.add_argument("--ya", action="store_true", help="tanpa pertanyaan konfirmasi (untuk GitHub Actions)")
    parser.add_argument("--daftar", action="store_true", help="tampilkan riwayat penghapusan")
    parser.add_argument("--pulihkan", metavar="ID", help="kembalikan data dari cadangan ID")
    parser.add_argument("--credentials", type=Path, default=ROOT_DIR / DEFAULT_CREDENTIALS)
    parser.add_argument("--database-url",
                        default=os.getenv("TASNIM_DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args(argv)

    db = initialize_firebase(args.credentials, args.database_url)
    try:
        if args.daftar:
            rows = list_batches(db)
            if not rows:
                print("Belum ada penghapusan.")
            for row in rows:
                count = row["count"] or {}
                print(f"{row['batch_id']} | {row['status']} | {row['range']} | "
                      f"node {','.join(row['nodes'] or [])} | {count.get('slot', 0)} slot | "
                      f"alasan: {row['reason']}")
            return 0

        if args.pulihkan:
            result = restore(db, args.pulihkan.strip())
            print(f"[OK] Dipulihkan: {result['restored']} data; dilewati karena slot sudah terisi: "
                  f"{result['skipped_existing']}. Rentang dicabut dari daftar hapus.")
            print("Jalankan AI bila perlu: python3 -m ai.realtime_inference --root hardware_test --once")
            return 0

        if not args.dari or not args.sampai:
            parser.error("--dari dan --sampai wajib diisi (atau pakai --daftar / --pulihkan)")
        plan = plan_delete(db, parse_wita(args.dari, "--dari"),
                           parse_wita(args.sampai, "--sampai"), args.node)
        print("TAS[N]IM hapus data hardware_test/history")
        print(describe_plan(plan))
        if not args.hapus:
            print("[CEK] Belum ada yang dihapus. Tambah --hapus untuk menghapus.")
            return 0
        if len(args.alasan.strip()) < 3:
            raise SystemExit("[STOP] --alasan wajib diisi, mis. --alasan \"uji coba\"")
        if not args.ya:
            answer = input("Hapus data di atas? (cadangan otomatis dibuat) ketik HAPUS: ").strip()
            if answer != "HAPUS":
                print("Dibatalkan.")
                return 0
        result = apply_delete(db, plan, args.alasan)
        backup = ROOT_DIR / "backups" / f"hapus_{result['batch_id']}.json"
        backup.parent.mkdir(exist_ok=True)
        backup.write_text(json.dumps({**result, "items": plan["items"]}, ensure_ascii=False, indent=1))
        print(f"[OK] Terhapus. ID cadangan: {result['batch_id']}")
        print(f"     Cadangan: Firebase tasnim_trash/{result['batch_id']} dan {backup.relative_to(ROOT_DIR)}")
        print(f"     analysis/latest: {result['latest_analysis']}")
        print("     Rentang ini masuk daftar hapus: impor CSV & perekam live akan melewatinya.")
        print(f"     Salah hapus? python3 scripts/hapus_data.py --pulihkan {result['batch_id']}")
        return 0
    except DeleteError as exc:
        raise SystemExit(f"[STOP] {exc}")


if __name__ == "__main__":
    sys.exit(main())
