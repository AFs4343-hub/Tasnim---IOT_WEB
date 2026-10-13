"""Hapus data history hardware_test dengan cadangan otomatis dan daftar hapus.

Alur ``hapus``:
1. Data yang akan dihapus disalin utuh ke **tempat sampah** Firebase
   ``tasnim_trash/<batch_id>`` (tidak terlihat di website) dan dibaca ulang
   untuk memastikan cadangan benar-benar tersimpan.
2. Baru setelah itu data dihapus dari ``hardware_test/history``.
3. Rentang waktu + node dicatat di **daftar hapus**
   ``tasnim_meta/deleted_ranges/<batch_id>``. Impor CSV dan perekam live
   membaca daftar ini dan otomatis melewati data di rentang tersebut, jadi
   data yang sudah dihapus tidak masuk lagi walaupun CSV di microSD masih
   memuatnya. File CSV asli tidak diubah.
4. ``analysis/latest`` diperbaiki jika menunjuk slot yang dihapus.

``pulihkan`` mengembalikan isi tempat sampah (hanya ke slot yang kosong,
tidak menimpa) dan mencabut rentang dari daftar hapus.

Semua fungsi menerima objek ``db`` bergaya ``firebase_admin.db`` sehingga
bisa diuji offline.
"""
from __future__ import annotations

import copy
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

ROOT = "hardware_test"
TRASH = "tasnim_trash"
DELETED_RANGES = "tasnim_meta/deleted_ranges"
NODES = ("N0", "N1", "N2")
SLOT_MS = 300_000
WITA = timezone(timedelta(hours=8))


class DeleteError(RuntimeError):
    pass


def wita(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, WITA).strftime("%d/%m/%Y %H:%M WITA")


def normalize_nodes(nodes):
    chosen = sorted(set(nodes or NODES))
    if not chosen or any(n not in NODES for n in chosen):
        raise DeleteError("node harus N0, N1 dan/atau N2")
    return chosen


def slot_range(start_ms, end_ms):
    """Slot pertama dan terakhir yang tercakup rentang [start, end]."""
    if type(start_ms) is not int or type(end_ms) is not int or end_ms < start_ms:
        raise DeleteError("rentang waktu tidak valid (dari harus <= sampai)")
    return start_ms // SLOT_MS * SLOT_MS, end_ms // SLOT_MS * SLOT_MS


# ---------------------------------------------------------------- daftar hapus

def load_deleted_ranges(db):
    raw = db.reference(DELETED_RANGES).get() or {}
    ranges = []
    if isinstance(raw, dict):
        for batch_id, item in raw.items():
            if not isinstance(item, dict):
                continue
            try:
                first, last = slot_range(int(item["start_ms"]), int(item["end_ms"]))
                nodes = normalize_nodes(item.get("nodes"))
            except (KeyError, TypeError, ValueError, DeleteError):
                continue
            ranges.append({**item, "batch_id": batch_id, "first_slot": first,
                           "last_slot": last, "nodes": nodes})
    return sorted(ranges, key=lambda r: r["first_slot"])


def is_deleted(ranges, slot_ms, node):
    """True jika (slot, node) termasuk rentang yang pernah dihapus."""
    return any(r["first_slot"] <= slot_ms <= r["last_slot"] and node in r["nodes"]
               for r in ranges)


# ---------------------------------------------------------------- rencana

def plan_delete(db, start_ms, end_ms, nodes=None):
    """Hitung apa yang akan dihapus. Tidak menulis apa pun."""
    first, last = slot_range(start_ms, end_ms)
    chosen = normalize_nodes(nodes)
    whole_slot = chosen == list(NODES)
    history = (db.reference(f"{ROOT}/history").order_by_key()
               .start_at(str(first)).end_at(str(last)).get()) or {}
    items = {}
    count = {"slot": 0, "node": 0, "analysis": 0}
    for key, record in sorted(history.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        if not key.isdigit() or not first <= int(key) <= last or not isinstance(record, dict):
            continue
        if whole_slot:
            selected = {k: v for k, v in record.items()}
        else:
            selected = {n: record[n] for n in chosen if n in record}
            # Analisis slot itu bergantung pada node yang dihapus.
            if selected and "analysis" in record:
                selected["analysis"] = record["analysis"]
        if not selected:
            continue
        items[key] = selected
        count["slot"] += 1
        count["node"] += sum(1 for n in selected if n in NODES)
        count["analysis"] += 1 if "analysis" in selected else 0
    return {
        "start_ms": start_ms, "end_ms": end_ms, "first_slot": first, "last_slot": last,
        "nodes": chosen, "whole_slot": whole_slot, "items": items, "count": count,
    }


def describe_plan(plan):
    lines = [
        f"Rentang : {wita(plan['first_slot'])} → {wita(plan['last_slot'])}",
        f"Node    : {', '.join(plan['nodes'])}"
        + (" (seluruh slot)" if plan["whole_slot"] else ""),
        f"Terkena : {plan['count']['slot']} slot, {plan['count']['node']} data node, "
        f"{plan['count']['analysis']} hasil AI",
    ]
    for key in list(plan["items"])[:8]:
        lines.append(f"  - {wita(key)}: {', '.join(sorted(plan['items'][key]))}")
    if len(plan["items"]) > 8:
        lines.append(f"  … dan {len(plan['items']) - 8} slot lainnya")
    return "\n".join(lines)


# ---------------------------------------------------------------- hapus

def _same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _repair_latest_analysis(db, deleted_slots):
    latest = db.reference(f"{ROOT}/analysis/latest").get()
    if not isinstance(latest, dict) or str(latest.get("source_timestamp_ms")) not in deleted_slots:
        return "tidak berubah"
    history = db.reference(f"{ROOT}/history").get() or {}
    candidates = [int(k) for k, v in history.items()
                  if k.isdigit() and isinstance(v, dict) and isinstance(v.get("analysis"), dict)]
    if candidates:
        newest = str(max(candidates))
        db.reference(f"{ROOT}/analysis/latest").set(history[newest]["analysis"])
        return f"diganti ke hasil AI {wita(newest)}"
    db.reference(f"{ROOT}/analysis/latest").delete()
    return "dikosongkan (tidak ada hasil AI tersisa)"


def apply_delete(db, plan, reason, *, now_ms=None, batch_id=None):
    """Cadangkan ke tempat sampah, verifikasi, lalu hapus. Return info batch."""
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise DeleteError("alasan wajib diisi (min. 3 karakter), mis. 'uji coba'")
    now = int(time.time() * 1000) if now_ms is None else now_ms
    batch_id = batch_id or (datetime.fromtimestamp(now / 1000, WITA).strftime("%Y%m%d_%H%M%S")
                            + "_" + secrets.token_hex(2))
    entry = {
        "created_ms": now, "reason": reason[:200],
        "start_ms": plan["start_ms"], "end_ms": plan["end_ms"], "nodes": plan["nodes"],
        "count": plan["count"],
    }
    # Selalu dicatat, juga bila Firebase belum berisi data di rentang itu:
    # rentang tetap masuk daftar hapus agar CSV tidak mengimpornya nanti.
    trash_ref = db.reference(f"{TRASH}/{batch_id}")
    trash_ref.set({**entry, "items": plan["items"]})
    if plan["items"]:
        stored = trash_ref.get() or {}
        if not _same(stored.get("items"), plan["items"]):
            raise DeleteError("cadangan tidak terverifikasi; tidak ada data yang dihapus")
        updates = {}
        for slot, selected in plan["items"].items():
            if plan["whole_slot"]:
                updates[slot] = None
            else:
                for key in selected:
                    updates[f"{slot}/{key}"] = None
        db.reference(f"{ROOT}/history").update(updates)
    db.reference(f"{DELETED_RANGES}/{batch_id}").set({**entry, "trash": batch_id})
    latest = _repair_latest_analysis(db, set(plan["items"])) if plan["items"] else "tidak berubah"
    return {"batch_id": batch_id, "latest_analysis": latest, **entry}


# ---------------------------------------------------------------- pulihkan

def restore(db, batch_id):
    """Kembalikan isi tempat sampah ke slot kosong; cabut dari daftar hapus."""
    trash = db.reference(f"{TRASH}/{batch_id}").get()
    if not isinstance(trash, dict):
        raise DeleteError(f"cadangan {batch_id} tidak ditemukan")
    restored = skipped = 0
    for slot, selected in (trash.get("items") or {}).items():
        current = db.reference(f"{ROOT}/history/{slot}").get() or {}
        for key, value in selected.items():
            if key in current:
                skipped += 1
                continue
            db.reference(f"{ROOT}/history/{slot}/{key}").set(copy.deepcopy(value))
            restored += 1
    db.reference(f"{DELETED_RANGES}/{batch_id}").delete()
    db.reference(f"{TRASH}/{batch_id}/restored_ms").set(int(time.time() * 1000))
    _point_latest_to_newest(db)
    return {"restored": restored, "skipped_existing": skipped}


def _point_latest_to_newest(db):
    """Setelah pulih, analysis/latest menunjuk hasil AI terbaru yang ada."""
    history = db.reference(f"{ROOT}/history").get() or {}
    candidates = [int(k) for k, v in history.items()
                  if k.isdigit() and isinstance(v, dict) and isinstance(v.get("analysis"), dict)]
    if not candidates:
        return
    newest = str(max(candidates))
    latest = db.reference(f"{ROOT}/analysis/latest").get()
    current = latest.get("source_timestamp_ms") if isinstance(latest, dict) else None
    if current is None or int(current) < int(newest):
        db.reference(f"{ROOT}/analysis/latest").set(history[newest]["analysis"])


def list_batches(db):
    trash = db.reference(TRASH).get() or {}
    active = {r["batch_id"] for r in load_deleted_ranges(db)}
    rows = []
    for batch_id, item in sorted(trash.items()) if isinstance(trash, dict) else []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "batch_id": batch_id, "reason": item.get("reason"),
            "range": f"{wita(item['start_ms'])} → {wita(item['end_ms'])}",
            "nodes": item.get("nodes"), "count": item.get("count"),
            "status": "aktif (dilewati saat impor)" if batch_id in active
            else ("dipulihkan" if item.get("restored_ms") else "tidak aktif"),
        })
    return rows
