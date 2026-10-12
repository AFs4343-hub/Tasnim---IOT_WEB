#!/usr/bin/env bash
# TASNIM AI V2 candidate test pack — Codespaces/demo emulator only.
# No Firebase LIVE deployment, no service-account reads, no firmware changes.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== TASNIM AI V2 + SIGNED HTTP GATEWAY CANDIDATE CHECK ==="
if [ "$(git branch --show-current)" != "infra/field-data" ]; then
  echo "[STOP] Must run on infra/field-data"; exit 1
fi
if [ -n "$(git diff --name-only)" ] || [ -n "$(git diff --cached --name-only)" ]; then
  echo "[STOP] Unexpected tracked/staged changes"; exit 1
fi

python3 - <<'PY'
from pathlib import Path
import json
from importlib.util import find_spec
cfg = json.loads(Path("tasnim.config.json").read_text())
assert cfg == {"activeDataRoot":"simulation","mode":"SIMULATION"}
prod = json.loads(Path("firebase.json").read_text())
assert prod["database"]["rules"] == "database.rules.json"
emu = json.loads(Path("firebase.emulator.security.json").read_text())
assert emu["emulators"]["database"] == {"host":"127.0.0.1","port":19003}
assert emu["emulators"]["auth"] == {"host":"127.0.0.1","port":19004}
assert emu["database"]["rules"] == "database.hardware_test.v2.candidate.rules.json"
assert find_spec("firebase_admin") is not None
assert Path("ai/models/tasnim_ai_bundle.joblib").is_file(), (
    "Prototype model missing in Codespaces. Do not claim real-model smoke PASS."
)
print("[PASS] SIMULATION, emulator isolation, and local model preflight")
PY

echo "=== OFFLINE TEST PACK ==="
for pattern in \
  test_hardware_test_history_v2.py \
  test_hardware_test_preview_v2.py \
  test_hardware_test_worker_v2.py \
  test_hardware_test_worker_lease_v2.py \
  test_hardware_test_supervisor_v1.py \
  test_hardware_test_ingestion_core.py \
  test_hardware_test_contract_v2.py \
  test_real_test_bridge_v2.py \
  test_security_rules_candidate_static.py \
  test_real_test_regression.py \
  test_hardware_test_analysis_writer_v2.py \
  test_hardware_test_preview_real_model.py \
  test_hardware_test_gateway_auth_v1.py \
  test_hardware_test_gateway_http_v1.py \
  test_hmac_interop_v1.py
do
  python3 -m unittest discover -s tests -p "$pattern" -v
done

echo "=== FIREBASE DEMO EMULATOR PACK ==="
firebase emulators:exec \
  --only database,auth \
  --project demo-tasnim-security \
  --config firebase.emulator.security.json \
  "GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_ingestion_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_analysis_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_gateway_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_gateway_http_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_worker_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_worker_lease_emulator.py' -v && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 python3 -m unittest discover -s tests -p 'test_hardware_test_supervisor_emulator.py' -v && node tests/test_security_rules_emulator.mjs && GCLOUD_PROJECT=demo-tasnim-security FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:19004 TASNIM_AUTH_TEST_EMULATOR_ONLY=YES bash scripts/test_hardware_auth_emulator.sh"

echo "=== WEBSITE HARDWARE V2 READ-ONLY CONTRACT ==="
node --test tests/test_hardware_v2_view.mjs tests/test_demo_mode_guards.mjs tests/test_demo_legacy_adapter.mjs
echo "=== WEBSITE BUILD ==="
npm run build
git diff --check
echo "=== GIT STATUS ==="
git status -sb
echo "[PASS] AI V2 + SIGNED HTTP GATEWAY CANDIDATE TEST PACK COMPLETE"
echo "[SAFE] No Firebase LIVE deploy, no hardware firmware modification"
