"""Pembaca CSV microSD ESP32 TAS[N]IM (tanpa Firebase, tanpa jaringan).

Format firmware: ``timestamp,node,sequence,ph,tds,turbidity,rssi``

- timestamp: epoch UTC milidetik (epoch detik otomatis ×1000), atau teks
  ``YYYY-MM-DD HH:MM[:SS]`` (tanpa zona waktu dianggap WITA, UTC+8)
- ``NA``/kosong = nilai tidak ada (TIDAK diubah menjadi 0)
- pemisah koma, titik koma (Excel Indonesia, desimal koma) atau tab
- node dari kolom ``node`` atau dari nama file (``tasnim_N0.csv``)

Logika sama dengan ``src/services/sdCsv.js`` agar website dan backend
membaca file yang sama dengan hasil yang sama.
"""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

NODES = ("N0", "N1", "N2")
MIN_MS = 1_704_067_200_000  # 2024-01-01 UTC
WITA = timezone(timedelta(hours=8))
MISSING = {"", "na", "n/a", "nan", "null", "none", "missing", "-", "—"}
COLUMN_ALIASES = {
    "timestamp": ("timestamp", "timestamp_ms", "epoch_ms", "time_ms", "ts", "epoch",
                  "waktu", "datetime", "date_time", "time", "tanggal_waktu"),
    "node": ("node", "node_id", "nodeid", "id_node", "titik"),
    "sequence": ("sequence", "seq", "urutan", "no"),
    "ph": ("ph", "ph_value", "nilai_ph"),
    "tds": ("tds", "tds_ppm", "ppm"),
    "turbidity": ("turbidity", "turb", "ntu", "turbidity_ntu", "kekeruhan", "turbiditas"),
    "rssi": ("rssi", "rssi_dbm", "wifi_rssi"),
}
_DATE_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?\s*"
    r"(z|[+-]\d{2}:?\d{2})?$", re.IGNORECASE)
_NUMBER_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$", re.IGNORECASE)


class CsvFormatError(ValueError):
    pass


def _normalize_header(cell: str) -> str:
    cell = cell.strip().lower().lstrip("\ufeff")
    cell = re.sub(r"\s*\(.*\)\s*$", "", cell)
    return re.sub(r"[\s-]+", "_", cell)


def node_from_filename(name: str):
    match = re.search(r"(?:^|[^a-z0-9])(n[012])(?:[^0-9]|$)", name, re.IGNORECASE)
    return match.group(1).upper() if match else None


def parse_number(text, decimal_comma=False):
    raw = str(text if text is not None else "").strip()
    if raw.lower() in MISSING:
        return None
    if decimal_comma and "," in raw:
        raw = raw.replace(".", "").replace(",", ".", 1)
    if not _NUMBER_RE.match(raw):
        return None
    value = float(raw)
    if not math.isfinite(value):
        return None
    return int(value) if value.is_integer() and "." not in raw and "e" not in raw.lower() else value


def parse_timestamp(text):
    raw = str(text if text is not None else "").strip()
    if raw.lower() in MISSING:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        value = float(raw)
        ms = round(value * 1000 if value < 1e11 else value)
        return ms if ms >= MIN_MS else None
    match = _DATE_RE.match(raw)
    if not match:
        return None
    y, mo, d, h, mi, s, frac, zone = match.groups()
    tz = WITA
    if zone and zone.lower() == "z":
        tz = timezone.utc
    elif zone:
        sign = -1 if zone[0] == "-" else 1
        digits = zone[1:].replace(":", "")
        tz = timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:])))
    moment = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0),
                      int((frac or "0").ljust(3, "0")) * 1000, tzinfo=tz)
    ms = int(round(moment.timestamp() * 1000))
    return ms if ms >= MIN_MS else None


def parse_sd_csv(text: str, *, file_name: str = "", default_node=None):
    """Return ``(readings, skipped)``. Reading = dict mentah per baris."""
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines)
                         if line.strip() and not line.strip().startswith("#")), None)
    if header_index is None:
        raise CsvFormatError(f"{file_name or 'CSV'} kosong")
    header_line = lines[header_index]
    sep = max((";", ",", "\t"), key=header_line.count)
    if header_line.count(sep) == 0:
        sep = ","
    decimal_comma = sep == ";"
    rows = list(csv.reader(io.StringIO("\n".join(lines[header_index:])), delimiter=sep))
    headers = [_normalize_header(h) for h in rows[0]]
    columns = {}
    for field, aliases in COLUMN_ALIASES.items():
        for index, header in enumerate(headers):
            if header in aliases:
                columns[field] = index
                break
    if "timestamp" not in columns:
        raise CsvFormatError(
            f"{file_name or 'CSV'}: kolom timestamp tidak ditemukan "
            "(header yang diharapkan: timestamp,node,sequence,ph,tds,turbidity,rssi)")
    if not {"ph", "tds", "turbidity"} & set(columns):
        raise CsvFormatError(f"{file_name or 'CSV'}: kolom ph/tds/turbidity tidak ditemukan")
    file_node = default_node or node_from_filename(file_name)
    readings, skipped = [], []
    for offset, cells in enumerate(rows[1:], start=1):
        line_no = header_index + offset + 1
        if not cells or not any(c.strip() for c in cells) or cells[0].strip().startswith("#"):
            continue
        if [_normalize_header(c) for c in cells] == headers:
            continue  # header berulang (file digabung)

        def cell(field):
            index = columns.get(field)
            return cells[index] if index is not None and index < len(cells) else ""

        timestamp = parse_timestamp(cell("timestamp"))
        if timestamp is None:
            skipped.append({"line": line_no, "reason": "TIMESTAMP_INVALID"})
            continue
        node_text = str(cell("node")).strip().upper()
        if node_text in NODES:
            node = node_text
        elif node_text in ("0", "1", "2"):
            node = "N" + node_text
        elif node_text:
            node = None
        else:
            node = file_node
        if node not in NODES:
            skipped.append({"line": line_no,
                            "reason": "NODE_INVALID" if node_text else "NODE_UNKNOWN"})
            continue
        reading = {"node": node, "timestamp": timestamp, "source_line": line_no}
        sequence = parse_number(cell("sequence"))
        if isinstance(sequence, int) and sequence >= 0:
            reading["sequence"] = sequence
        for sensor in ("ph", "tds", "turbidity", "rssi"):
            value = parse_number(cell(sensor), decimal_comma)
            if value is not None:
                reading[sensor] = value
        readings.append(reading)
    return readings, skipped


def read_csv_file(path: Path, *, default_node=None):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    return parse_sd_csv(text, file_name=Path(path).name, default_node=default_node)
