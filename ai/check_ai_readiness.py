"""Read-only completeness and sanity gate for TASNIM REAL_TEST/FIELD history.
Not a sensor accuracy certificate or a model inference runner.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path

NODES = ('N0', 'N1', 'N2')
SENSORS = ('ph', 'tds', 'turbidity')
SLOT_MS = 300_000
WITA = timezone(timedelta(hours=8))
DB_URL = 'https://omirisetmonitoring-default-rtdb.asia-southeast1.firebasedatabase.app'
INFO_FLAGS = {'BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED'}


def valid_number(value, sensor):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    return 0 <= value <= 14 if sensor == 'ph' else value >= 0


def audit_slot(slot_key, record):
    reasons = []
    try:
        slot = int(slot_key)
        if slot <= 0 or slot % SLOT_MS:
            raise ValueError
    except (ValueError, TypeError):
        return ['INVALID_SLOT_KEY']

    if not isinstance(record, dict):
        return ['INVALID_RECORD']

    for node in NODES:
        packet = record.get(node)
        if not isinstance(packet, dict):
            reasons.append(f'{node}:MISSING')
            continue
        timestamp = packet.get('timestamp')
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
                or not math.isfinite(timestamp) or int(timestamp) // SLOT_MS != slot // SLOT_MS):
            reasons.append(f'{node}:BAD_TIMESTAMP_OR_SLOT')
        for sensor in SENSORS:
            if not valid_number(packet.get(sensor), sensor):
                reasons.append(f'{node}:{sensor.upper()}_INVALID_OR_MISSING')
        flags = packet.get('quality_flags', [])
        if not isinstance(flags, list):
            reasons.append(f'{node}:BAD_QUALITY_FLAGS')
        else:
            blocked = [str(flag) for flag in flags if flag not in INFO_FLAGS]
            if blocked:
                reasons.append(f'{node}:FLAGS={",".join(blocked)}')
    return reasons


def self_test():
    slot = 1_791_637_200_000
    good = {node: {'timestamp': slot + 5000, 'ph': 7.1, 'tds': 420.0,
                   'turbidity': 11.0, 'quality_flags': list(INFO_FLAGS)}
            for node in NODES}
    assert audit_slot(str(slot), good) == []
    bad = {node: dict(packet) for node, packet in good.items()}
    bad['N0']['ph'] = None
    bad['N0']['quality_flags'] = ['PH_INVALID']
    bad.pop('N2')
    assert any('PH_INVALID' in s for s in audit_slot(str(slot), bad))
    assert 'N2:MISSING' in audit_slot(str(slot), bad)
    assert audit_slot(str(slot + 1), good) == ['INVALID_SLOT_KEY']
    print('[PASS] 3 offline checks — no Firebase access')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', choices=('real_test', 'field'), default='real_test')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    key = Path('iot/serviceAccountKey.json')
    if not key.is_file():
        print('[STOP] Service account tidak ditemukan')
        return

    import firebase_admin
    from firebase_admin import credentials, db
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(key)),
                                      {'databaseURL': DB_URL})
    rows = (db.reference(f'{args.root}/history')
            .order_by_key().limit_to_last(max(1, min(args.limit, 1000))).get()) or {}
    stats = Counter()
    print(f'=== TASNIM AI READ-ONLY GATE: {args.root} ===')
    print('History slots:', len(rows))
    for slot, record in sorted(rows.items(), key=lambda kv: kv[0]):
        reasons = audit_slot(slot, record)
        try:
            timestamp = datetime.fromtimestamp(int(slot)/1000, WITA).strftime('%d/%m %H:%M WITA')
        except (ValueError, OverflowError, OSError):
            timestamp = str(slot)
        if reasons:
            stats['incomplete'] += 1
            print(f'[SKIP] {timestamp} | {"; ".join(reasons)}')
        else:
            stats['candidate'] += 1
            print(f'[CANDIDATE] {timestamp} | 3 node × 3 sensor valid secara struktur')
    print(f"[RESULT] Candidate: {stats['candidate']} | Incomplete: {stats['incomplete']}")
    print('[INFO] Candidate bukan bukti kalibrasi akurat atau model layak untuk riset.')
    print('[PASS] READ ONLY; tidak menjalankan AI atau menulis Firebase')


if __name__ == '__main__':
    main()
