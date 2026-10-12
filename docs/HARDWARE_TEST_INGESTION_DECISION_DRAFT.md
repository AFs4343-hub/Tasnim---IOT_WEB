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
