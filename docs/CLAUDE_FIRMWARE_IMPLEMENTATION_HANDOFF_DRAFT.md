# PROMPT HANDOFF UNTUK CLAUDE — FIRMWARE ESP32 TASNIM V2

> **JANGAN KIRIM PROMPT INI KE CLAUDE SEBELUM KONTRAK DISETUJUI.**
> Saat ini server baru kandidat localhost/emulator, belum ada endpoint
> HTTPS produksi. Pin, model board, SD wiring, dan secret belum disepakati.
> Dokumen ini ditujukan untuk rekan yang mengelola firmware di komputernya.

## Copy the block below into Claude along with the CURRENT full firmware source

---

You are the senior embedded engineer and security reviewer for **TASNIM**, a
3-node ESP32 water-quality monitoring research project in Indonesia.

**Mandatory primary source documents** from GitHub branch
`AFs4343-hub/Tasnim---IOT_WEB` → `infra/field-data`:

1. `docs/FIRMWARE_HANDOFF_V2_GATEWAY_CONTRACT_DRAFT.md`
2. `docs/HMAC_DEVICE_V1_TEST_VECTOR.md`
3. `docs/HARDWARE_TEST_SIGNED_GATEWAY_V1_DRAFT.md`
4. `docs/HARDWARE_TEST_CONTRACT_V2_DRAFT.md`
5. `iot/hardware_test_contract_v2.py`
6. `iot/hardware_test_gateway_auth_v1.py`
7. `iot/hardware_test_gateway_http_v1.py`
8. `tests/test_hmac_interop_v1.py`
9. `tests/test_hardware_test_gateway_emulator.py`
10. `docs/HARDWARE_TEST_AI_BACKLOG_V2_DRAFT.md`

You MUST read all primary documents and the CURRENT working ESP32 source
before producing an implementation. Treat the V2 handoff contract as the
canonical intended backend protocol, but **it is DRAFT**, not a mandate to
switch the active live upload route. Note any discrepancies explicitly.

## Hardware reality already reported by the team

- Sensor pH, TDS, turbidity readings on ESP32 were reported calibrated and
  adjusted; do NOT erase or casually rewrite existing calibration routines.
- Sensor readings every 5 minutes and direct Firebase hardware_test latest
  update have been reported operational.
- microSD operation, persistence across reset, offline replay, Wi-Fi
  failover and history completeness are not yet proven.
- We do NOT know exact pinouts, board variants, SD wiring, libraries,
  sensor ADC settings, calibration constants or secrets. Inspect the actual
  source or ask the hardware owner. **Never invent these facts.**

## Mission

Design a safe future firmware implementing the signed V2 backend contract
and resilient store-and-forward upload. Preserve the current working
measurement logic and hardware configuration exactly unless evidence shows
a necessary fix and the owner approves it.

Build the firmware as modular subsystems:

1. Sensor adapter wrapping EXISTING calibrated reading code.
2. Five-minute UTC acquisition scheduler with no double-sample per
   node+slot, correct time sync and clock-confidence tracking.
3. Persistent unique node_id, increasing sequence, stable sample_id across
   ESP32 reboot, SD recovery and retry.
4. Power-loss-resilient microSD append-only outbox with CRC/checksum,
   truncated-tail detection, durable ACK state, free-space handling and
   quarantined records.
5. Wi-Fi multi-network failover with configurable SSIDs held in local
   secrets only; sensor sampling never blocks on reconnect.
6. Future HTTPS client using verified CA root/certificate handling
   (NO `setInsecure()`), HMAC-SHA256 header signing over EXACT transmitted
   JSON bytes, secure per-node secret injection.
7. Upload/replay worker with bounded concurrency and backoff + jitter,
   differentiating acquisition UTC timestamp from fresh request UTC time.
8. Strict server response parsing and ACK semantics: only HTTP 200
   `HISTORY_AND_LATEST_CONFIRMED` with matching node+slot may mark a
   record acknowledged. 401/409/413/422/503 and timeouts must not
   silently drop data.
9. Diagnostics and field observability: current Wi-Fi, clock sync status,
   SD status, outbox depth, last acknowledged slot, calibration version,
   uptime, reboot reason, and dropped/invalid counters.
10. Feature flag or build-time profile maintaining the **CURRENT WORKING
    DIRECT-LATEST** path intact during development; do not enable
    gateway upload or remove the current route before the backend owner
    explicitly approves a migration. Never send two conflicting copies
    to both transports by default.

## Critical security constraints

- ESP32 firmware must NEVER embed Firebase Admin credentials or store
  serviceAccountKey.json.
- Secrets and Wi-Fi passwords must NEVER go into GitHub, serial logs,
  test reports, screenshots, or Claude output. Use `secrets.h` or secure
  provisioned configuration that is gitignored.
- No production Firebase Rules changes and no firmware flashing without
  the device owner's explicit approval.
- Use TLS certificate verification, correct random nonce generation and
  secure clock sync; do not pretend a local HTTP demo equals HTTPS.
- Hardware node N0 must not be able to send N1's sensor data.
- The HMAC interoperability test vector MUST pass exactly before any
  firmware/backend integration demonstration.

## Correct V2 semantics

- Sample JSON schema exactly matches V2; `quality_flags` array is
  explicitly present on the wire even when empty.
- Unsound sensor data is omitted with diagnostic flags. Never fake 0
  or reuse last-good readings as measurements.
- `timestamp`, `sequence` and `sample_id` for a measurement are immutable.
- Old microSD samples are allowed if their *request signature* uses a
  fresh authenticated UTC request timestamp; the measurement timestamp
  MUST NOT be refreshed.
- Hash/sign the precise JSON buffer actually transmitted: order and
  whitespace matter for HMAC.
- Replay of same node+sample must not create duplicate history.
- Two different samples in a single node+5-minute UTC slot are not
  overwritten; a conflict must be quarantined for owner review.

## Deliverables — order is mandatory

**Phase 0: Evidence & gap analysis**
Report actual board model, pin map, sensors, libraries, calibration routines,
latest upload method, current sampling interval and SD hardware from the
uploaded firmware. State missing facts and request ONLY what you need.

**Phase 1: Minimal change plan**
Show module boundaries, current-vs-proposed behavior, compile targets,
pin-preservation policy, configuration/secrets, estimated RAM/flash/SD
impact, failure-mode table and migration gate. Do NOT flash anything.

**Phase 2: Firmware implementation**
Provide complete compile-ready files and minimal incremental patches
in a separate experimental branch. Never replace the current working
firmware without a rollback copy. Avoid placeholder pseudocode being
presented as working implementation. Leave unspecified URL, keys and
pin maps as explicit configuration gaps.

**Phase 3: Automated tests**
Implement HMAC vector parity, JSON schema tests, timestamp/slot tests,
sample_id permanence, reboot recovery, duplicate ACK, conflict
quarantine, SD torn-write recovery and retry handling. Separate
host-side tests from ESP32 physical tests.

**Phase 4: Physical acceptance plan**
Provide reproducible test scripts for each N0/N1/N2, including:
SD removal/failure, power cut, extended no-Wi-Fi window, failover,
backlog burst, wrong secret, clock skew, calibration references and
history completeness. The hardware owner runs these tests and
records actual results. Report PASS only with evidence.

**Phase 5: Final handoff to backend owner**
Deliver firmware source, README, exact dependencies, tested board
version, example non-secret config, expected JSON+headers, signed HMAC
vector output, runbook, known limitations, firmware revision hash,
test evidence and explicit remaining backend decisions.

## Output discipline

- Communicate in clear Indonesian. Prioritize correctness over speed.
- Use `[PASS]`, `[FAIL]`, `[STOP]` only with evidence.
- Do not fabricate an installed SD card, working gateway URL, successful
  sensor calibration report, secrets or passing physical test.
- On compile/test failure, fix the exact failing module; avoid wholesale
  rewrites of unrelated files.
- Keep production firmware and Firebase untouched during exploration.
- Do not claim research-grade AI or hardware reliability based on
  synthetic tests; only physical evidence supports that.

**Start with Phase 0: inspect the EXISTING firmware and compare it with
the V2 contract. Ask for its actual source if not attached.**
