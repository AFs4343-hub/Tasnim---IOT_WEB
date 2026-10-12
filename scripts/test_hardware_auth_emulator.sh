#!/usr/bin/env bash
# Guarded integration test. ONLY invoked inside local demo emulators:exec.
set -euo pipefail
if [[ "${TASNIM_AUTH_TEST_EMULATOR_ONLY:-}" != "YES" ]] ||
   [[ "${GCLOUD_PROJECT:-}" != "demo-tasnim-security" ]] ||
   [[ "${FIREBASE_AUTH_EMULATOR_HOST:-}" != "127.0.0.1:19004" ]] ||
   [[ "${FIREBASE_DATABASE_EMULATOR_HOST:-}" != "127.0.0.1:19003" ]]; then
  echo "[STOP] Auth tests require local demo emulators and explicit opt-in" >&2
  exit 1
fi
python3 tests/seed_hardware_auth_emulator.py
node --test tests/test_demo_bridge_emulator.mjs
node --test tests/test_hardware_auth_emulator.mjs

# Real database-emulator tests for worker retries, bounded dry-run and review gate.
# Their setUp deletes ONLY the isolated demo hardware_test namespace.
python3 -m unittest discover -s tests -p 'test_hardware_test_worker_emulator.py' -v
python3 -m unittest discover -s tests -p 'test_hardware_test_worker_lease_emulator.py' -v
python3 -m unittest discover -s tests -p 'test_hardware_test_supervisor_emulator.py' -v
