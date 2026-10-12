# TASNIM — HARDWARE_TEST DATA CONTRACT V2

Status: DRAFT — NOT DEPLOYED
Owner: TASNIM Web / Backend / AI Team

## 1. Purpose

Defines the proposed shared data interface between:

- ESP32 nodes N0, N1, N2
- Firebase Realtime Database
- AI inference backend
- TASNIM Web dashboard
- Offline microSD synchronization

This document is NOT yet approved as a firmware
handoff specification.

## 2. Data Roots

Primary measurement root:

/hardware_test

Expected structure:

hardware_test/
  nodes/
    N0/latest
    N1/latest
    N2/latest
  history/
    <slot_ms>/
      N0
      N1
      N2
      analysis
  analysis/
    latest

Legacy namespaces:

- /simulation: synthetic testing only
- /real_test: existing testing namespace
- /field: previous field-data contract

Do not automatically delete or migrate legacy data.

## 3. Measurement Interval

Planned interval: 300000 ms (5 minutes).

The slot key is:

slot_ms = floor(timestamp_ms / 300000) * 300000

The measurement timestamp must be the actual
capture time in Unix epoch milliseconds.

Do not add UTC+8 to epoch values.
WITA is a display timezone only.

## 4. Node Identity

Supported node IDs:

N0 = upstream baseline
N1 = downstream branch 1
N2 = downstream branch 2

Each measurement needs a stable identity.

The exact sample_id generation and reboot
collision policy must be approved before
firmware handoff.

## 5. Proposed Payload V2

Example:

{
  "schema_version": 2,
  "node_id": "N0",
  "sample_id": "N0_1791724501000_3",
  "timestamp": 1791724501000,
  "sequence": 3,
  "ph": 7.51,
  "tds": 109.6,
  "turbidity": 24.6,
  "rssi": -54,
  "quality_flags": []
}

Values in this example are illustrative.

Units:
- ph: pH
- tds: ppm, subject to sensor calibration
- turbidity: NTU, subject to sensor calibration
- rssi: dBm

## 6. Invalid Measurements

Never fabricate missing sensor values.

If a sensor is invalid:
- Preserve the measurement identity.
- Preserve valid remaining measurements.
- Omit the invalid normalized sensor field.
- Add an explicit quality flag.
- Keep original diagnostic readings on microSD.

Examples:
PH_INVALID
TDS_INVALID
TURB_INVALID_OR_MISSING
TIME_INVALID

Invalid packets may be retained as diagnostic
history but must NOT pass AI quality validation.

## 7. Offline microSD Contract

Each measurement must be recorded persistently
before being marked as uploaded.

Required properties:

- Local record identity remains stable.
- Data survives Wi-Fi interruption.
- Data survives ESP32 restart.
- Unacknowledged records remain pending.
- Successful server ACK is recorded persistently.
- Retry does not create duplicate measurements.
- Replay retains original capture timestamp.
- Wi-Fi failover does not reset the data queue.

Firmware implementation will be handled by
the hardware team after contract approval.

## 8. History Rules

Proposed destination:

/hardware_test/history/<slot_ms>/<node_id>

Target behavior:

- One canonical measurement per node per slot.
- Retrying an identical sample is idempotent.
- An unexpected different sample in an occupied
  node/slot must be reported as a conflict.
- Do not silently overwrite existing history.
- Out-of-order replay must be supported.

Final conflict and clock-skew policies still
require explicit testing and approval.

## 9. Latest Rules

Proposed destination:

/hardware_test/nodes/<node_id>/latest

The latest record must never move backward
to an older measurement during offline replay.

A monotonic timestamp/identity update strategy
must be verified before enabling live writes.

## 10. AI Responsibility

ESP32 does not write AI analysis.

Backend responsibilities:

- Read hardware_test history.
- Wait for valid N0, N1, N2 samples.
- Validate timestamp, fields and flags.
- Handle delayed/backfilled measurements.
- Avoid duplicate effective analysis.
- Keep AI predictions separate from ground truth.
- Write analysis using backend authority only.

Proposed analysis destinations:

/hardware_test/history/<slot_ms>/analysis
/hardware_test/analysis/latest

RF, IF and Z-score outputs must retain
model provenance and prototype warnings.

## 11. Website Responsibility

Dashboard requirements:

- Authorized users only.
- Read-only access to measurements and analysis.
- Latest data per node.
- Historical readings.
- N0-to-N1 and N0-to-N2 comparisons.
- Offline, missing, invalid and delayed states.
- AI predictions and warnings.
- Preserve simulation testing mode.

## 12. Access Control

Proposed responsibilities:

ESP32:
- Write measurements for its own node only.

Backend:
- Read measurements.
- Write AI analysis.

Authorized dashboard users:
- Read permitted monitoring data.
- No direct sensor or AI writes.

Unauthenticated visitors:
- No access to protected measurement data.

Firebase Authentication alone is insufficient.
Authorization must be enforced by Rules or a
controlled backend.

Existing live Rules must not be replaced
without emulator tests and approval.

## 13. Research Data Integrity

Measurement, diagnostic flags, AI prediction,
and ground-truth labels are different concepts.

Do not mix simulated records with field records.

Data completeness must be evaluated using
actual observation sessions defined by the team.

## 14. Required Acceptance Tests

Before firmware handoff:

1. Valid packet accepted.
2. Missing/invalid sensors handled safely.
3. Three nodes mapped into intended slots.
4. Duplicate retry causes no duplicate history.
5. Offline replay restores missing records.
6. Old replay cannot overwrite newer latest.
7. AI resumes valid backlog.
8. Unauthorized writes are rejected.
9. Authorized dashboard can read data.
10. Simulation remains isolated.

## 15. Open Decisions

Must be resolved before V2 becomes FINAL:

- Stable sample_id across restart.
- Clock synchronization and skew tolerance.
- Collision policy for two samples in one slot.
- Authorized ESP32 authentication mechanism.
- Diagnostic raw data retention strategy.
- Backend runtime for field sessions.
- Firebase Rules and browser authorization.
- Migration behavior for existing namespaces.

## 16. Change Policy

No direct Firebase LIVE deployment.
No automatic migration or deletion.
No firmware changes from this draft.

Review, test, approve, then freeze the contract.
