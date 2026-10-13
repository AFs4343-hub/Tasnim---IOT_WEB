#!/usr/bin/env python3
"""Pintasan: python3 scripts/import_sd_csv.py tasnim_N0.csv tasnim_N1.csv tasnim_N2.csv

Lihat iot/hardware_test_csv_import.py untuk semua opsi (--out-json,
--analyze, --write). Default dry-run: Firebase tidak ditulis.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iot.hardware_test_csv_import import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
