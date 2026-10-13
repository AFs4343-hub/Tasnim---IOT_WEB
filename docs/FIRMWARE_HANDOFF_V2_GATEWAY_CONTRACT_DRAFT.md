# TASNIM ESP32 ↔ Backend V2 — Firmware Handoff Contract (CANDIDATE)

> **Status: DRAFT FOR TEAM REVIEW, NOT A PRODUCTION ENDPOINT.**
> The sensor team has reported calibrated N0/N1/N2 readings and a 5-minute
> `/hardware_test/.../latest` upload. microSD/history/failover/replay
> have **NOT** been confirmed on physical devices.
> Our tested gateway prototype runs on **localhost + Firebase Emulator only**.

This document is the one source to implement ESP32 firmware **after**
gateway/hosting, security, and field-session decisions are approved.
Do not replace the currently working direct-`latest` implementation yet.

## A. Physical node contract

- Exactly 3 nodes: `N0`, `N1`, `N2`.
- Every node samples once per **5 minutes**; use **UTC epoch milliseconds**
  for all protocol timestamps. Display WITA only in the user interface.
- Three sensors: `ph`, `tds`, `turbidity`.
- Measurement packet `timestamp` is **acquisition time**, not upload time.
- Each sample must have a **stable** `sample_id` and `sequence` surviving
  reset/reboot and retries. `sample_id` must match regex
  `^N[012]_[A-Za-z0-9_-]{1,80}$`.
- One unique measurement per node per UTC 5-minute slot. A second different
  measurement for the same node+slot causes **409 conflict** and is NOT
  silently overwritten. Resolve device scheduling/collision strategy before
  firmware is frozen.
- The timestamp must represent reliable acquisition time (NTP/RTC or clearly
  flagged untrusted clock). If trusted acquisition time is unavailable,
  queue locally; do **not** invent measurement timestamps.

## B. Measurement JSON schema V2

```json
{
  "schema_version": 2,
  "node_id": "N0",
  "sample_id": "N0_1791724501000_3",
  "timestamp": 1791724501000,
  "sequence": 3,
  "ph": 7.2,
  "tds": 240.0,
  "turbidity": 16.0,
  "rssi": -49,
  "quality_flags": []
}
```

All fields above except `rssi` are part of the intended normal packet.
`quality_flags` must be an array when **sending**. Empty `[]` may disappear
after storage by Firebase RTDB; the backend knows how to normalize this.

- `schema_version`: integer **2**
- `node_id`: `N0|N1|N2`
- `sample_id`: unique, stable per sample, prefix must match `node_id`
- `timestamp`: positive UTC milliseconds since epoch; >= 2024-01-01
- `sequence`: nonnegative integer, persistent across reboot
- `ph`: finite 0–14
- `tds`: finite 0–5000
- `turbidity`: finite 0–<3000
- `rssi`: optional finite number (normally negative dBm)
- `quality_flags`: array of unique uppercase codes (`[A-Z][A-Z0-9_]*`,
  max 12 elements by gateway); no duplicate flags
- No arbitrary additional keys; JSON body must be <= **2048 bytes**.
- When a sensor is invalid or unavailable, **omit that numerical field**
  and provide the matching quality flag: `PH_INVALID`, `TDS_INVALID`,
  `TURB_INVALID_OR_MISSING` or `TURB_SATURATED`.
- Never replace a missing/invalid reading with fabricated `0` or a stale
  last-good value. Diagnostic packets remain in history but are excluded
  from AI readiness.
- `quality_flags` may contain informational code
  `BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED`; range validation is not
  proof of field accuracy. Physical calibration logs are separate evidence.

## C. Backend path contract (ESP32 must not write Firebase directly in V2)

The **trusted backend** writes:

```text
/hardware_test/history/<slot_ms>/N0
/hardware_test/history/<slot_ms>/N1
/hardware_test/history/<slot_ms>/N2
/hardware_test/nodes/N0/latest
/hardware_test/nodes/N1/latest
/hardware_test/nodes/N2/latest
/hardware_test/history/<slot_ms>/analysis  [AI backend only]
/hardware_test/analysis/latest            [AI backend only]
/gateway_state/nonces/<node>/<nonce>      [backend only, private]
```

`slot_ms = (timestamp_ms // 300000) * 300000` (UTC).
No firmware write to `/analysis`, `/simulation`, `/real_test`, or `/field`.

Important: production Rules currently differ from the candidate Rules.
**Do not deploy draft Rules or redirect existing devices** before backend
availability, credentials, rollback and compatibility have been approved.

## D. Proposed signed HTTPS request contract

**Proposed URL**: `POST https://<approved-gateway-host>/v1/measurements`.
The real hostname has **not** been selected. In development, the existing
demo implementation listens only on `http://127.0.0.1:<port>` and writes
only to the RTDB emulator.

Headers (exact values, no extra whitespace):

```text
Content-Type: application/json
X-Tasnim-Node: N0
X-Tasnim-Time: <current UTC epoch ms (13 digits)>
X-Tasnim-Nonce: <16-80 char URL-safe random nonce>
X-Tasnim-Signature: <64 lowercase hexadecimal chars>
```

Use a **different secret per node**, at least 32 random bytes, supplied
securely outside source control. Protocol V1 HMAC-SHA256 input is:

```text
TASNIM-DEVICE-V1\n<node>\n<request_time_ms>\n<nonce>\n<raw JSON bytes>
```

Here `\n` is exactly one ASCII LF byte (0x0A). There are 4 newline
delimiters, including the one immediately before the raw body. HMAC
signs the actual UTF-8 bytes **as transmitted**, NOT a parsed/reformatted
JSON object. Compute signature *after* serializing JSON, then transmit
those exact bytes unchanged.

- If microSD contains an old measurement, preserve its original body
  including `timestamp`/`sequence`/`sample_id`, but use a **fresh**
  request timestamp, nonce and HMAC signature after clock sync.
- Request time must be within +/- 5 min of trusted server time.
- Identical signed retries during that window are allowed; if the signing
  window expires, re-sign with a fresh nonce but the **same measurement body**.
- Secret is never placed inside JSON, URL, source control, or logs.
- Do not assume the development HTTP server is an internet-accessible
  HTTPS endpoint. Firmware should keep transport endpoint configurable.

## E. Response and microSD acknowledgment semantics

The backend returns **200 only after both history and latest transactions
have completed**:

```json
{
  "ok": true,
  "code": "HISTORY_AND_LATEST_CONFIRMED",
  "node_id": "N0",
  "slot_ms": 1791724500000,
  "history": "CONFIRMED",
  "latest": "LATEST_CONFIRMED"
}
```

For a delayed replay, `latest` may instead be
`OLDER_REPLAY_PRESERVED`; this is still **success** because history is
durable and newer latest was protected.

Reject examples:

| HTTP | `code` | Firmware behavior |
| --- | --- | --- |
| 200 | `HISTORY_AND_LATEST_CONFIRMED` | Verify node+slot; mark local record ACKed; preserve data until durable queue bookkeeping |
| 401 | `UNAUTHORIZED` | Do NOT drop sample; diagnose key, timestamp, device ID |
| 409 | `CONFLICT_REVIEW_REQUIRED` | Quarantine and alert human; do NOT overwrite or discard |
| 413 | `PAYLOAD_TOO_LARGE` | Reject payload; investigate serialization/size |
| 422 | `INVALID_MEASUREMENT` | Quarantine invalid record; do not pretend it was accepted |
| 503 | `RETRY_LATER` | Keep microSD record and retry with backoff and jitter |
| transport timeout | no ACK | Keep record, retry; do not assume write failed |

Other conditions (`404`, malformed HTTP, TLS failure, or unexpected status)
also mean **no ACK**. Never erase queued samples merely on HTTP connection
success; only the confirmed semantic response counts.

The server may have committed history but crashed before sending HTTP 200.
This is why **idempotent retry of the same measurement** is required.

## F. microSD outbox and recovery contract

1. At each 5-min acquisition, persist a full packet with checksum and stable
   sample identity to microSD **before** attempting upload.
2. Use atomic/append-safe write and recovery from a truncated final record.
   Never overwrite prior unsent measurements with a new one.
3. Maintain a durable ACK cursor or per-record ACK state, with atomic updates.
4. Reconnect Wi-Fi using a tested multi-network failover schedule; do not
   block sensor acquisition while retrying uploads.
5. Replay **oldest pending measurement first**. Keep timestamp of each
   measurement; use a fresh signed request time after NTP sync.
6. If 200 + confirmed ack, advance durable ACK state. If 409/422, quarantine
   for inspection, with traceable sample_id; do not silently discard.
7. Rate-limit backlog replay, honor server 503, and use exponential backoff
   with jitter; protect flash/SD wear and power-loss integrity.
8. On reboot, reload last known sequence, queue, ACK ledger and node ID.
9. Record loss counters, SD failures, queue depth, firmware version and RTC
   confidence locally; never fabricate water measurements.

## G. Acceptance tests before V2 firmware approval

- N0/N1/N2 all independently publish an acknowledged measurement per slot.
- Clock synchronization and time source validated before online signing.
- 5-min scheduling without duplicate node+slot collisions, including reboot.
- microSD read/write verified across power cut and reboot.
- Three successive offline slots reappear in exact history locations after
  Wi-Fi recovery; `latest` remains newest timestamp.
- Repeating an acknowledged sample never creates extra history entries.
- Tampered signature / wrong node secret / timestamp skew are denied.
- Sensor invalid/missing is flagged, stored diagnostically and excluded AI.
- Queue ACK never advances for failed, ambiguous, or conflicting requests.
- Failover between configured Wi-Fi networks verified on **physical** ESP32.
- Calibration evidence and measurement uncertainty recorded independently.
- Factory/reset/reflashing procedures preserve or explicitly reconcile
  sample_id and sequence state.

## H. Items not yet frozen

Production gateway hostname, hosting and TLS, per-node key provisioning and
rotation, hardware model/pin mapping, microSD wiring and capacity, exact
outbox/ACK file format, device time source, 5-minute collision policy, field
session IDs and durations, nonce cleanup/rate limits, login permissions, and
approved Firebase LIVE migration. Claude must **ask or use placeholders**
for those, not silently invent values.

**Do not treat this DRAFT as permission to change the currently working
firmware or to deploy new Firebase Rules.**
