# TASNIM /hardware_test AI Backlog V2 — DRAFT

Status: OFFLINE CANDIDATE; not deployed.

## Scope

`ai/hardware_test_history_v2.py` is a deterministic read-only adapter for data extracted from `/hardware_test/history`. The helper is not connected to `ai/realtime_inference.py`, a Firebase Admin app, a website listener, or any live deployment.

- It validates that each canonical 5-minute slot has **N0, N1 and N2**, including sensor ranges, timestamp-to-slot mapping and V2 packet metadata.
- It uses the existing `ai.check_ai_readiness.audit_slot` gate as well as the V2 contract validator. Invalid diagnostic measurements are **excluded from AI**, not silently fabricated.
- Firebase RTDB may omit `quality_flags: []` when persisted. The adapter treats a *missing* flag field as an empty array for validation of an otherwise complete packet, without modifying source data.
- It sorts by source slot time (UTC epoch milliseconds), even if offline replay arrives out of order.
- `session_id` **must be provided by the caller**. It is not inferred from gaps, nor is an observation session or ground truth invented.
- The first valid slot is used solely to warm up temporal features. Later complete, unanalyzed slots become pending candidates.
- The adapter creates a Pandas DataFrame compatible with the nine model-input sensor fields and legacy feature engineering, with `time_mode=ACTUAL_TIMESTAMP`.

## Analysis marker (provisional)

`/hardware_test/history/<slot_ms>/analysis` is treated as already analyzed when it contains a JSON object. This is a **candidate policy**, not a robust model-version checkpoint. A later backend must compare `model_version`, `data_version` and status, safely write each analysis and advance `/hardware_test/analysis/latest` monotonically. Late-arriving records can also change temporal context for later analyses; recomputation policy is not yet implemented.

## Running a read-only snapshot audit

Export **only the history subtree** into a local JSON file. Do not put credentials into it. Then run:

```bash
python3 -m scripts.audit_hardware_test_history_v2 --history-json local_history.json --session-id FIELD_SESSION_001
```

This command does not open Firebase and does not generate AI predictions. A candidate slot is not a calibrated measurement certificate, ground truth, or evidence that the prototype AI is scientifically validated.

## Open before production

Secure gateway and device identities, verified physical clocks and restart-safe sample IDs, same-slot collision decisions, session metadata and ground truth, persistent analysis checkpoint/versioning, late-data reanalysis, AI model validation, Firebase emulator end-to-end test, and authorized website access. `database.rules.json`, Firebase LIVE, production website, and firmware are unchanged by this stage.
