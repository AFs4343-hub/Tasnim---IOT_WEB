# TASNIM — Ingestion Architecture

Status: DRAFT — NOT APPROVED OR DEPLOYED

## Canonical paths

- /hardware_test/nodes/{node}/latest
- /hardware_test/history/{slot_ms}/{node}

Nodes: N0, N1, N2.

Legacy simulation, real_test and field roots remain untouched.

## Candidate architecture

ESP32 -> authenticated HTTPS gateway
      -> trusted Firebase backend
      -> hardware_test

ESP32 keeps a persistent microSD store-and-forward queue.

The gateway must eventually provide:
- Authenticated per-node requests
- Stable sample identity
- Payload validation
- Rate limiting and replay protection
- Server-side logging
- Safe history and latest transactions

Gateway hosting, uptime, cost, device credentials,
secret rotation and transport protocol remain OPEN.

This document does not authorize deploying a gateway.

## Current writer core

iot/hardware_test_ingestion_core.py is a
transport-neutral candidate.

It must be called ONLY AFTER authentication
and node authorization have succeeded.

The core uses:
- V2 contract validation
- Strict accepted field list
- Future-clock rejection
- Idempotent history transactions
- Monotonic latest transactions

Old backfill is allowed without a 120-second
freshness cutoff.

History is written before latest.

The two writes are NOT atomically grouped.
If latest fails, retry the identical sample.

History conflicts must be investigated,
not automatically overwritten.

## Research integrity

Invalid sensor readings may remain in diagnostic
history with explicit flags.

They must NOT pass AI quality validation.

AI output is not ground truth.

## Unresolved

- Firmware clock accuracy during disconnection
- Sample identity after ESP32 restart
- Multiple readings occupying one 5-minute slot
- Device authentication and authorization
- HTTPS ingestion gateway deployment
- Real Firebase transaction integration tests
- AI analysis backlog and durable checkpoints
- Final synchronization acknowledgement protocol
- Research duration amendment

## Safety

Do not deploy candidate Rules.
Do not connect this module to Firebase LIVE.
Do not modify firmware.
Do not activate writes without approval.


## Validation of newer latest pointers during delayed backfill (October 2026)

A strictly newer timestamp is **not** enough to trust an already stored
`/hardware_test/nodes/<node>/latest` value. Before allowing an older
packet to preserve a newer pointer, the ingestion core now validates the
stored pointer's complete V2 measurement schema, expected node identity,
allowed metadata fields, normalized RTDB empty quality-flags representation,
maximum payload size, and future clock bound against the **same** trusted
ingestion time. An invalid pointer is retained unchanged and the operation
raises `LatestConflict` for human review. The earlier history transaction
may already have committed: this is not a two-path atomic operation.

The AI analysis writer applies corresponding *canonical-record validation*
before accepting a newer `/hardware_test/analysis/latest` checkpoint.
Malformed model-stage/source/session metadata or extra fields now result in
`AnalysisLatestConflict` instead of being labeled an acceptable older
replay. Both code paths still preserve well-formed, strictly newer pointers
during legitimate delayed backfill.

This is **structural sanity**, not a cryptographic proof that a latest pointer
matches an archived slot or that real measurements are accurate. The V2 AI
worker separately verifies canonical source digests and archived checkpoints.
The new offline synthetic test `tests/test_backend_latest_integrity_v1.py`
and real localhost Emulator suites check corrupt newer pointers, replay
semantics, failure-before-overwrite, and allowed RTDB normalization.
No LIVE data is read or modified.
