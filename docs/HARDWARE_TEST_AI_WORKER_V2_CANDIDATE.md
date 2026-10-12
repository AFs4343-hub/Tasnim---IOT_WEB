# TASNIM — AI Worker V2 (Emulator-only candidate)

**Status: development only. NOT a production worker.**

The new module `ai/hardware_test_worker_v2.py` performs one explicit pass over
`/hardware_test/history`. It neither initializes Firebase nor runs as a daemon.
Callers supply an authenticated, local-demo adapter, a model bundle and predictor.

## Safety guard

The worker refuses to start unless all conditions hold:

- Environment: `TASNIM_AI_WORKER_EMULATOR_ONLY=YES`.
- Project: `GCLOUD_PROJECT=demo-tasnim-security`.
- Database host: `FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:19003`.
- Adapter declares `emulator_only=True`, `emulator_project=demo-tasnim-security`,
  and `emulator_host=127.0.0.1:19003`.

Do not pass a production adapter, deploy the candidate to hosting, or point the
worker at any LIVE Firebase namespace.

## Behavior

1. Read and validate an entire synthetic/demo history snapshot.
2. Skip incomplete slots and warm up temporal context from the first valid slot.
3. Compute a cumulative SHA-256 provenance fingerprint of valid N0/N1/N2 source
   records and stable source metadata. The analysis itself is excluded.
4. Validate canonical model/session/slot checkpoints and exact fingerprints.
   Any suspicious or mismatched checkpoint blocks the cycle for review.
5. Predict only absent-analysis slots using the injected prototype model.
6. Re-read history and verify the exact source prefix before writing.
7. Persist analysis history and advance latest through separate transactions.
8. After an interrupted latest update, recover by retrying the *identical*
   previously archived analysis record rather than recalculating inference.

The analysis writer now accepts the optional `source_digest_sha256` field
(64 lowercase hexadecimal digits); new worker records always include it.
Existing V2 records without this field remain usable by legacy code, but are
**not automatically trusted** as worker checkpoints.

## How to test

CI runs `test_hardware_test_worker_v2.py` without any database connection,
and the separate demo-Emulator workflow also runs
`test_hardware_test_worker_emulator.py` against localhost RTDB after
the Auth integration checks. Codespaces can run the full script:

```bash
bash scripts/check_ai_v2_candidate.sh
```

Do not commit synthetic demonstration values as if they were field data.

## Pending production decisions

- The re-read and individual history/latest transactions are **not one atomic
  snapshot-write lock**. Concurrent changes can occur after verification.
- Late-backfill invalidates previous temporal context and currently requires
  review, not automatic overwriting or silent recomputation.
- A fully managed worker still needs leasing, monitoring, bounded reads,
  source revision/version control, long-running orchestration, model version
  rollout, retry policy, and an approved field-session lifecycle.
- The model remains `PROTOTYPE_SIMULATION`, not scientifically validated
  with field ground truth.

Rules LIVE, firmware, website SIMULATION mode, and branch `main` remain untouched.


## Bounded candidate worker cycles — October 2026

The worker now executes at most `max_actions_per_cycle=3` action slots per
invocation by default (configurable 1–50). It validates a *whole* source
snapshot with at most `max_source_slots=500` slot objects by default
(configurable 2–5000) and **refuses** oversized snapshots before writing.
This is a safety ceiling **after the database read**, not production
pagination or a solution to large-database memory pressure.

Preflight `run_emulator_cycle(..., dry_run=True)` performs the same
candidate source/digest/checkpoint verification and returns
`would_process_slots`, `would_recover_slots`, and `deferred_slots`.
It never calls the AI model or writes to Firebase. Normal mode returns
`processed_slots`, `recovered_slots`, and `deferred_slots`.

Verified history checkpoints are no longer needlessly replayed on every
cycle. An absent or behind `analysis/latest` is repaired using only the
highest verified archived checkpoint; a corrupted or unrecognized latest
pointer blocks all writes and requires human review. Pending analyses are
processed oldest-first across successive calls, with a bounded action
budget. Invalid numeric budgets and dry-run inputs fail closed.

**Still NOT production scheduling**: source snapshots and writes remain
non-atomic, no leasing or concurrency control, no paginated source cursor,
no alerting/metrics service, no field-session lifecycle or verified model.
The worker must not run against Firebase LIVE.
