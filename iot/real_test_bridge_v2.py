#!/usr/bin/env python3
"""TASNIM demo-only bridge: Firebase /hardware_test -> /real_test.

READ ONLY BY DEFAULT. Use --write to store diagnostic copies.
No writes to /field, /simulation or /hardware_test.
Service account never bundled or printed.
"""
import argparse
import math
import time
from pathlib import Path

DB_URL = 'https://omirisetmonitoring-default-rtdb.asia-southeast1.firebasedatabase.app'
SERVICE_ACCOUNT = Path('iot/serviceAccountKey.json')
NODES = ('N0', 'N1', 'N2')
SLOT_MS = 300_000
MAX_AGE_MS = 120_000
MAX_FUTURE_MS = 60_000
MIN_TIMESTAMP_MS = 1_704_067_200_000  # 2024-01-01 UTC


def number(value):
    # booleans aren't legitimate numeric sensor values
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if math.isfinite(v) else None


def normalize(raw, node, now_ms):
    """Return (packet, status). Preserve source in hardware_test; never invent sensors."""
    if not isinstance(raw, dict):
        return None, 'NO_DATA'
    timestamp_number = number(raw.get('timestamp'))
    if timestamp_number is None or timestamp_number != int(timestamp_number):
        return None, 'BAD_TIMESTAMP'
    timestamp = int(timestamp_number)
    if timestamp < MIN_TIMESTAMP_MS or timestamp > now_ms + MAX_FUTURE_MS:
        return None, 'BAD_TIMESTAMP'
    age = now_ms - timestamp
    if age > MAX_AGE_MS:
        return None, f'STALE_{age // 1000}s'

    packet = {
        'timestamp': timestamp,
        'source': 'hardware_test',
        'status': 'TEST_UNVERIFIED',
    }
    flags = []
    ph = number(raw.get('ph'))
    if ph is not None and 0 <= ph <= 14:
        packet['ph'] = ph
    else:
        flags.append('PH_INVALID')

    tds = number(raw.get('tds'))
    if tds is not None and 0 <= tds <= 5000:
        packet['tds'] = tds
        if tds == 0:
            flags.append('TDS_ZERO_CHECK_CLAMP')
    else:
        flags.append('TDS_INVALID')

    turb = number(raw.get('turbidity'))
    if turb is not None and 0 <= turb < 3000:
        packet['turbidity'] = turb
        if turb == 0:
            flags.append('TURB_ZERO_VERIFY')
    elif turb is not None and turb >= 3000:
        flags.append('TURB_SATURATED')
    else:
        flags.append('TURB_INVALID_OR_MISSING')

    seq = number(raw.get('sequence'))
    if seq is not None and seq >= 0 and seq == int(seq):
        packet['sequence'] = int(seq)
    rssi = number(raw.get('rssi'))
    if rssi is not None:
        packet['rssi'] = int(rssi)

    # Firebase RTDB omits JSON null children; absent values mean invalid/missing.
    packet['quality_flags'] = flags if flags else ['BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED']
    return packet, 'OK'


def handle_cycle(db, write=False, last_seen=None, now_ms=None):
    if last_seen is None:
        last_seen = {}
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    stats = {'updated': 0, 'history': 0}
    for node in NODES:
        try:
            raw = db.reference(f'hardware_test/nodes/{node}/latest').get()
            packet, status = normalize(raw, node, now_ms)
            if status != 'OK':
                print(f'[{status}] {node}', flush=True)
                continue
            if last_seen.get(node) == packet['timestamp']:
                continue
            slot = packet['timestamp'] // SLOT_MS * SLOT_MS
            sensors = ', '.join(f'{k}={packet.get(k, "MISSING")}' for k in ('ph', 'tds', 'turbidity'))
            flags = '/'.join(packet['quality_flags'])
            if not write:
                print(f'[DRY-RUN] {node} {sensors} | flags={flags} | slot={slot}', flush=True)
                last_seen[node] = packet['timestamp']
                continue

            # Distinct test root; NEVER uses field paths.
            db.reference(f'real_test/nodes/{node}/latest').set(packet)
            history_ref = db.reference(f'real_test/history/{slot}/{node}')
            if history_ref.get() is None:
                history_ref.set(packet)
                stats['history'] += 1
                print(f'[HISTORY] {node} slot={slot} | flags={flags}', flush=True)
            last_seen[node] = packet['timestamp']
            stats['updated'] += 1
            print(f'[LATEST] {node} {sensors} | flags={flags}', flush=True)
        except Exception as exc:
            # A transient connection issue must not terminate all monitoring.
            print(f'[ERROR] {node}: {type(exc).__name__}: {exc}', flush=True)
    return stats


def main():
    parser = argparse.ArgumentParser(description='TASNIM demo telemetry bridge (safe by default)')
    parser.add_argument('--write', action='store_true', help='Explicitly write to /real_test only')
    parser.add_argument('--once', action='store_true', help='Process one iteration then stop')
    parser.add_argument('--interval', type=int, default=15)
    args = parser.parse_args()
    if not SERVICE_ACCOUNT.is_file():
        print('[STOP] Missing iot/serviceAccountKey.json; run from repository root')
        return 1
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT)), {'databaseURL': DB_URL})
    except ImportError:
        print('[STOP] Install firebase-admin in your Codespaces Python environment')
        return 1

    print('TASNIM REAL_TEST BRIDGE v2', flush=True)
    print('MODE: WRITE /real_test ONLY' if args.write else 'MODE: DRY-RUN / NO WRITES', flush=True)
    print('FIELD and SIMULATION are never modified.', flush=True)
    last_seen = {}
    try:
        while True:
            handle_cycle(db, write=args.write, last_seen=last_seen)
            if args.once:
                break
            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print('\n[STOP] Bridge stopped', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
