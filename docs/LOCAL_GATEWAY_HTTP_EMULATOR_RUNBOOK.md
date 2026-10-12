# TASNIM Local HTTP Gateway V1 — Emulator Runbook

**DEVELOPMENT ONLY.** This server only binds `127.0.0.1`, speaks
unencrypted HTTP, and will REFUSE startup without a demo Firebase project
and the RTDB Emulator target. It is not a usable public HTTPS gateway.

## Automated verification (preferred)

After pulling branch `infra/field-data`, with the existing private model
bundle available in Codespaces, run:

```bash
bash scripts/check_ai_v2_candidate.sh
```

This runs model-dependent offline tests and the Firebase Database emulator
suite (including signed gateway, actual local HTTP and browser permission
rules), then builds the web app. No LIVE Firebase deploy or firmware flash.

GitHub Actions `.github/workflows/tasnim-candidate-offline.yml` separately
runs **model-independent** offline unit tests and a web build on push.
It cannot prove the `.joblib`-dependent inference path or RTDB emulator
transaction semantics by itself.

## Optional manual HTTP demonstration (separate terminal tabs)

**Terminal A: run local Firebase Database Emulator**:

```bash
firebase emulators:start \
  --only database \
  --project demo-tasnim-security \
  --config firebase.emulator.security.json
```

**Terminal B: run local gateway** using **fake keys** (not field keys):

```bash
export TASNIM_GATEWAY_EMULATOR_ONLY=YES
export GCLOUD_PROJECT=demo-tasnim-security
export FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003
export TASNIM_TEST_KEY_N0_HEX="$(python3 -c 'print("11"*32)')"
export TASNIM_TEST_KEY_N1_HEX="$(python3 -c 'print("22"*32)')"
export TASNIM_TEST_KEY_N2_HEX="$(python3 -c 'print("33"*32)')"
python3 -m iot.hardware_test_gateway_http_v1 --port 18080
```

**Terminal C: optional health check**:

```bash
curl --fail http://127.0.0.1:18080/healthz
```

An optional signed demo client is in `scripts/signed_gateway_demo_client.py`.
To send a pre-existing JSON measurement, first save an example from the
handoff contract in a local `/tmp/tasnim-test-packet.json`. Keep its
timestamp original; the client signs a fresh request timestamp.

```bash
python3 -m scripts.signed_gateway_demo_client \
  --node N0 \
  --packet /tmp/tasnim-test-packet.json \
  --send-demo
```

Run that client **only in the same environment** where the three
`TASNIM_TEST_KEY_N*_HEX` variables and emulator-only guards are set.
Without `--send-demo`, it only generates a signature in memory and
does not send any network request.

The demo host port is NOT accessible from a physical ESP32 on a different
network. DO NOT open Codespaces port forwarding publicly to fake a
production HTTPS server.

## Return status reference

- 200 `HISTORY_AND_LATEST_CONFIRMED`: durable history and latest decision.
- 401 `UNAUTHORIZED`: auth/signature/request clock problem.
- 409 `CONFLICT_REVIEW_REQUIRED`: nonce, history, or latest collision;
  investigate, do not silently drop the queued measurement.
- 411 `LENGTH_REQUIRED`, 413 `PAYLOAD_TOO_LARGE`: malformed HTTP.
- 422 `INVALID_MEASUREMENT`: invalid V2 packet.
- 503 `RETRY_LATER`: backend temporarily failed. Retry same packet.
- HTTP timeout/network failure: **unknown** whether server committed data;
  retry the exact measurement.

Future production prerequisites: approved domain, trusted TLS termination,
edge rate limits, secret storage/rotation, nonce expiry and retention
policy, monitoring/alerts, hardened input validation, service-level tests,
device provisioning and rollback. No LIVE migration has been approved.
