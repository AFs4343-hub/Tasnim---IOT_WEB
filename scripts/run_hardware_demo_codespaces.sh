#!/usr/bin/env bash
# Private Codespaces demo: ONLY synthetic Auth+RTDB localhost emulators.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(git branch --show-current)" != "infra/field-data" ]]; then
  echo "[STOP] Must be in infra/field-data" >&2; exit 1
fi
python3 - <<'PY'
from pathlib import Path
from importlib.util import find_spec
import json, socket
assert json.loads(Path('tasnim.config.json').read_text()) == {
    'activeDataRoot':'simulation','mode':'SIMULATION'
}
assert json.loads(Path('firebase.json').read_text())['database']['rules'] == 'database.rules.json'
em = json.loads(Path('firebase.emulator.security.json').read_text())
assert em['database']['rules'] == 'database.hardware_test.v2.candidate.rules.json'
assert em['emulators']['auth'] == {'host':'127.0.0.1','port':19004}
assert em['emulators']['database'] == {'host':'127.0.0.1','port':19003}
assert find_spec('firebase_admin'), 'Please install Python firebase-admin first'
for port in (5173,19003,19004):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port)) == 0:
            raise SystemExit(f'[STOP] Port {port} already in use. Stop earlier Vite/Emulator with Ctrl+C.')
print('[SAFE] production config untouched; all emulator addresses localhost')
PY
command -v firebase >/dev/null || { echo '[STOP] Firebase CLI required'; exit 1; }
command -v npm >/dev/null || { echo '[STOP] npm required'; exit 1; }

LOG=/tmp/tasnim-browser-demo-emulators.log
EMU_PID=''
cleanup() {
  if [[ -n "$EMU_PID" ]]; then
    kill -INT "$EMU_PID" 2>/dev/null || true
    wait "$EMU_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[DEMO] Starting local Firebase emulators (Auth 19004; RTDB 19003)"
firebase emulators:start --only database,auth \
  --project demo-tasnim-security \
  --config firebase.emulator.security.json > "$LOG" 2>&1 &
EMU_PID=$!

python3 - <<'PY'
import socket,time,sys
for _ in range(120):
    try:
        for port in (19003,19004):
            with socket.create_connection(('127.0.0.1',port),timeout=1): pass
        print('[PASS] Two emulators started')
        break
    except OSError:
        time.sleep(1)
else:
    print('[STOP] Check /tmp/tasnim-browser-demo-emulators.log')
    sys.exit(1)
PY

export GCLOUD_PROJECT=demo-tasnim-security
export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:19004
export FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003
export TASNIM_AUTH_TEST_EMULATOR_ONLY=YES
export TASNIM_DEMO_LOGIN_MODE=YES
export VITE_TASNIM_DEMO_LOGIN=YES
export VITE_TASNIM_HARDWARE_V2_PREVIEW=YES

python3 tests/seed_hardware_auth_emulator.py
echo
echo '[DEMO READY] Open Codespaces port 5173, visibility PRIVATE.'
echo 'Demo email: viewer@tasnim-auth-demo.invalid'
echo 'Demo password: EmulatorOnly_2026_Test!'
echo 'Other permitted roles: admin, manager.'
echo 'Press Ctrl+C in this terminal to stop the demo.'
echo
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
