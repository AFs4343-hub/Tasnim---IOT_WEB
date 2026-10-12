# TASNIM — Signed ESP32 Gateway V1 (Candidate)

**Status: DEVELOPMENT ONLY; NO PUBLIC HTTP SERVER, NO FIREBASE LIVE, NO FIRMWARE CHANGE.**

This design is proposed, not yet approved as the final device-authentication choice.
It is intended to work with the existing V2 contract:
`/hardware_test/history/<slot_ms>/<node>`,
`/hardware_test/nodes/<node>/latest`,
`/hardware_test/history/<slot_ms>/analysis`, and
`/hardware_test/analysis/latest`.

## Proposed request: ESP32 to trusted HTTPS gateway

The transport layer is NOT implemented yet. A future server should expose a
strictly authenticated POST endpoint behind HTTPS and rate limits.

- `Content-Type: application/json`
- `X-Tasnim-Node: N0|N1|N2`
- `X-Tasnim-Time: <current UTC epoch milliseconds>` (13 digits)
- `X-Tasnim-Nonce: <random unique 16–80 character ASCII token>`
- `X-Tasnim-Signature: <lowercase hex HMAC-SHA256>`

The signature input is **exactly**:

```text
TASNIM-DEVICE-V1\n
<node>\n
<request_timestamp_ms>\n
<nonce>\n
<raw JSON request bytes>
```

The backslash-n above means one literal LF (0x0A) between fields; there
must be no extra spaces or newlines. Use HMAC-SHA256 with a distinct
random 32+ byte secret per node. The body is signed as transmitted bytes;
changing JSON whitespace invalidates that signature.

## Backlog microSD

**Measurement time** (`timestamp`) and **request time** are distinct.

- ESP32 may record measurements offline, with stable `sample_id` and
  monotonic `sequence` across restarts.
- On Wi-Fi recovery, ESP32 must obtain reliable current UTC time and sign a
  *fresh* request for each queued measurement; old measurement timestamps
  remain unchanged.
- Request clock difference exceeding 5 minutes is rejected.
- An identical signed request may retry safely even if history succeeded
  but latest write was interrupted.
- Reusing a nonce with different signed content is rejected.
- A nonce registered under `/gateway_state/nonces/<node>/<nonce>` is
  **backend-only** and not accessible by browser/ESP32 client Rules.

## Security boundaries (important)

The candidate accepts injected secrets as bytes and never stores secrets
in GitHub. It does not implement secret issuance/rotation, revocation,
HSM/secret-manager integration, device enrollment, or TLS termination.

A bounded request timestamp is NOT, by itself, a complete anti-replay or
anti-DoS solution. Identical signed retries are intentionally accepted.
Production still needs edge-level rate limiting, quotas, observability,
durable nonce TTL cleanup, abuse monitoring, secure time sync, and a
well-defined token/secret recovery procedure. Do not deploy this directly.

The backend Admin SDK bypasses Realtime Database Rules. Its credentials
must stay on the trusted server ONLY, never in ESP32 or browser code.

`iot/hardware_test_gateway_auth_v1.py` is only a transport-neutral Python
function and not an HTTPS listener, Cloud Function, Docker service, or
production background worker.

## What gets tested

- Request signature verification and node identity binding
- Fresh request with delayed sensor measurement
- Reject tampering, expired requests, wrong node keys, invalid packets
- RTDB backend-only nonce registry collisions and identical retries
- Firebase Emulator ingestion transactions, RF/IF preview, AI analysis
  archive, and monotonic latest (all with synthetic data)
- Browser and device denial from nonce registry in emulator Rules

These are software integration tests, not a claim of ESP32 physical uptime,
Wi-Fi failover, microSD persistence, calibrated sensor accuracy, or valid
scientific model performance.

## Remaining before any LIVE approval

1. User-approved gateway hosting/budget and device-auth design.
2. Real HTTPS server and its ingress validation, error codes and quotas.
3. Secure secret provisioning and rotation for N0, N1 and N2.
4. Durable nonce cleanup and metrics, plus retry/replay policy.
5. Full firmware contract including time sync and SD outbox acknowledgments.
6. AI source snapshot/versioning and late-backfill recomputation.
7. Firebase Authentication and role-aware web UI (still missing).
8. On-site field tests, sensor calibration and complete research sessions.

No production Firebase Rules, database data, website, firmware, or branch
`main` may be changed by this candidate test phase.
