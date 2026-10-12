# TAS[N]IM — IoT River-Water Monitoring (Candidate Research Software)

This repository contains the **TAS[N]IM** website, experimental three-node
measurement data contract, signed gateway candidate, and prototype AI
Supervisor. The active website configuration remains **SIMULATION**.

**Important:** This is research software in development. A passing build,
a green GitHub Action, and synthetic Emulator demonstrations are NOT proof
of measured water safety, trained-model field accuracy, real-device
reliability, or approval to deploy Firebase LIVE.

## Work area

Development candidate: `infra/field-data`. The `main` branch, production
`database.rules.json`, `firebase.json`, `tasnim.config.json`,
`src/services/firebase.js`, LIVE Firebase, and physical ESP32 firmware are
**not modified by candidate testing**. Untracked field calibration archives
in Codespaces belong to collaborators; do not clean, overwrite or commit
them without separate review.

## Architecture (local synthetic candidate)

```text
N0/N1/N2 synthetic signed device requests (HMAC SHA-256)
          |
          v
localhost HTTP gateway candidate (127.0.0.1; NOT HTTPS production)
          |
          v
localhost Firebase RTDB Emulator: immutable 5-minute V2 history + latest
          |
          v
Guarded AI Worker + Supervisor (injected synthetic predictor for E2E test)
          |
          +--> source digests, AI analysis checkpoints
          +--> private status / bounded audit + sanitized browser feed
          |
          v
Firebase Auth Emulator + read-only browser demo / Vite dashboard
```

**Do not use physical device keys, production secrets, production URLs or
actual field measurements in the demo.** The `joblib` prototype model is
kept locally and is not required to prove the synthetic CI contract.

## Primary verification

From the repo root on `infra/field-data`:

```bash
python3 scripts/check_production_baseline_guard.py
python3 -m unittest discover -s tests -p 'test_gateway_fault_matrix_v1.py' -v
python3 -m unittest discover -s tests -p 'test_candidate_operations_rehearsal.py' -v
python3 -m unittest discover -s tests -p 'test_candidate_release_evidence.py' -v
npm ci
npm run build
```

The full Emulator test pack is run by
`.github/workflows/tasnim-auth-emulator-candidate.yml`, not against
Firebase LIVE. The offline/build CI is
`.github/workflows/tasnim-candidate-offline.yml`.
Both workflows upload a scoped candidate-evidence JSON artifact and
explicitly report that production deployment remains blocked.

For a comprehensive **local** test pack (requires the trusted local
prototype AI bundle and installed Firebase Emulator tools):

```bash
bash scripts/check_ai_v2_candidate.sh
```

The script checks branch, simulation config and Emulator isolation first;
it must not be pointed at a public Firebase project.

## Docs and limits

- [Candidate release gates](docs/GITHUB_CANDIDATE_RELEASE_GATE_20261012.md)
- [Security, nonce, backup and incident runbook](docs/CANDIDATE_SECURITY_OPERATIONS_RUNBOOK_20261012.md)
- [AI V2 worker](docs/HARDWARE_TEST_AI_WORKER_V2_CANDIDATE.md)
- [Signed gateway contract draft](docs/HARDWARE_TEST_SIGNED_GATEWAY_V1_DRAFT.md)
- [Local HTTP Emulator runbook](docs/LOCAL_GATEWAY_HTTP_EMULATOR_RUNBOOK.md)
- [Firmware handoff draft](docs/FIRMWARE_HANDOFF_V2_GATEWAY_CONTRACT_DRAFT.md)

The real collaborator firmware will be reconciled **at the final integration
stage**, after the GitHub software candidate and tests have been reviewed.
Compiling, flashing, physical calibration and scientific field trials are
separate future acceptance gates.
