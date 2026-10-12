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


## Cooperative single-flight gate for supervised Emulator runs

A new, **opt-in** module
`ai/hardware_test_worker_lease_v2.py` supplies
`run_exclusive_emulator_cycle(db, **worker_kwargs)`.
Callers must satisfy the existing emulator-only worker guard **and** set
`TASNIM_AI_COORDINATION_EMULATOR_ONLY=YES`; all checks occur before a
Firebase operation. The adapter must be the demo project on the exact
localhost RTDB Emulator. Browser RTDB Rules deny the `worker_state` tree;
the trusted Emulator Admin SDK adapter manages it.

The cooperative lock lives exclusively at
`/worker_state/ai_v2_exclusive`. A Firebase RTDB transaction claims it
only when absent, with a random 128-bit owner token. A second cooperating
worker receives `WorkerLeaseBusy` and **does not infer or commit**.
After normal completion or a Python exception, a transaction writes an
owner-free `{"state":"RELEASED"}` tombstone **only when the original
owner matches** (Firebase Admin SDK rejects `None` as a transaction value).
Only an absent slot or exactly this tombstone can be claimed again.
A wrong owner receives
`WorkerLeaseOwnershipLost`; a stale lock is never expired or stolen.
A dry run bypasses lock writes and preserves the zero-write guarantee.

**Important limits:** This is *not* a production distributed lease,
fencing token, or guarantee against manually invoking the underlying
uncoordinated `run_emulator_cycle`. A hard crash strands a lock, requiring
explicit human review/reset of **only the demo Emulator**. No unattended
cron loop, stale-lock auto-takeover, LIVE deployment or worker hosting was
introduced. The RTDB history read/analysis writes remain non-atomic and
production scheduling is still prohibited.

CI now exercises the cooperative lock both in offline tests and against
the real localhost RTDB Emulator. Any continuation toward production needs
lease fencing, monitored expiration/recovery, source revisions, limited
database pagination, idempotence across restarts, and signed-off staging.


## Supervisor V1 + operational status V1 (demo-only)

Two independently tested modules are available:

- `ai/hardware_test_supervisor_v1.py`: one supervised cycle via
  `run_supervised_emulator_cycle(...)`, or explicit bounded
  `run_bounded_demo_schedule(..., cycles=1..3, interval_seconds=1..3600)`.
  It ALWAYS uses the cooperative single-flight lock (except preview).
  Retry is only for `ConnectionError`, `TimeoutError`, and changed
  source snapshots, with `max_attempts=2` by default (hard cap 3).
  Lock collisions, corrupt checkpoints, and review-required sources are
  NEVER silently retried or auto-reset. A bounded schedule STOPS on any
  unsuccessful state. The scheduler is a caller-invoked, synchronous
  helper, **not** a cron daemon or permanently running process.
- `ai/hardware_test_supervisor_status_v1.py`: persist exactly one
  bounded `/worker_state/ai_v2_supervisor/latest` status, guarded by
  the same localhost-demo authorization. It stores only `state`,
  `error_code`, timestamp, attempts, and **counts**, with no password,
  model inference arrays, raw exception, device secrets or sensor data.
  A database transaction prevents an older timestamp overwriting newer
  status. A tied timestamp with different content is also preserved,
  not overwritten by another concurrent status reporter.

Statuses are `PROCESSED`, `IDLE`, `PREVIEW`, `WAITING_LOCK`,
`REVIEW_REQUIRED`, `RETRY_EXHAUSTED`, and `FAILED`.
For `dry_run=True`, the supervisor returns `PREVIEW` but creates
NO lock, telemetry or analysis writes. A failed status-persistence
transaction is surfaced to the caller instead of being hidden.

**Developer usage** (only from a separately guarded emulator caller
which injects a local adapter, session, model bundle and predictor):

```python
from ai.hardware_test_supervisor_v1 import run_supervised_emulator_cycle
result = run_supervised_emulator_cycle(
    db=demo_emulator_adapter,
    session_id="LOCAL_DEMO",
    model_version="prototype-v1",
    model_bundle=demo_model,
    predict_fn=demo_predictor,
    dry_run=True,
)
```

There is **no automatic startup** and **no Firebase LIVE support**.
Supervisors cannot fix the underlying uncoordinated worker calls, race
windows between source validation and write, or unsafe automatic takeover
after a hard crash. Monitoring alerts, a trusted staging model,
fenced leases, database pagination and deployment approval remain pending.

CI and Codespaces suites now test both modules offline and in the real
localhost Firebase Emulator. The production website retains `SIMULATION`
by default and remains unchanged.


## Sanitized browser-readable status mirror (demo only)

The authoritative operational status remains
`/worker_state/ai_v2_supervisor/latest` and is inaccessible through browser
candidate Rules. After a supervisor successfully persists an authoritative
record, `ai/hardware_test_supervisor_feed_v1.py` publishes its strictly
validated, bounded status to
`/hardware_test/operations/supervisor/latest`. The mirror has exactly the
same allowlisted fields and no device measurements, credentials, model
output or exception messages. An older or tied-timestamp status cannot
overwrite a newer one. The duplicate writes are **not atomic together**;
failures are surfaced through `feed_persisted` or an exception, never
quietly treated as a successfully published state.

The web display is opt-in, demo-only and read-only. It does NOT start a
supervisor or seed fake successes. The actual demo workflow can therefore
correctly show "Belum ada catatan Supervisor" until a trusted Emulator
worker has explicitly run. No Firebase LIVE path or rule is altered.


## Trusted one-shot terminal trigger for local browser demo

A command-line entrypoint `scripts/run_supervisor_demo_once.py` connects
**only** to an already-running, pre-seeded local Firebase Auth + RTDB Emulator
at `127.0.0.1:19004/19003`. It refuses wrong branches, modified production
configuration, service-account credentials, wrong emulator endpoints,
non-demo project values, or absent emulator ports before Firebase init.

Run in a **second Codespaces terminal** after starting
`bash scripts/run_hardware_demo_codespaces.sh` in the first one:

```bash
cd /workspaces/Tasnim---IOT_WEB
python3 scripts/run_supervisor_demo_once.py --preview
python3 scripts/run_supervisor_demo_once.py --run
python3 scripts/run_supervisor_demo_once.py --status
```

`--preview` performs a true supervisor dry-run: no lock, analysis or
status writes. `--run` explicitly runs **one** bounded, coordinated
supervisor cycle, with at most three work actions and two retry attempts,
and writes a sanitized private operational status and browser-facing
read-only mirror. `--status` reads both status copies and reports whether
they agree, without writing. There is NO web control or scheduled process
that triggers computation.

The seed has been corrected: the browser's synthesized
`analysis/latest` now has a matching canonical archived history
checkpoint and SHA-256 context digest, so the worker can validate its
provenance and process other pending demo history without deleting any
analysis record. All model labels and pseudo-confidence scores in the
example remain a **deterministic synthetic test fixture** rather than
outputs from a trained Random Forest or Isolation Forest model. This
workflow does not scientifically validate the model or ESP32 sensors.

Do NOT run the full `check_ai_v2_candidate.sh` pack while the browser
demo is running: both suites use the same localhost Emulator ports.
Tests cover `--preview`, one actual `--run`, `--status`, and a
browser-role read of the sanitized feed, while browser reads of the
privileged `worker_state` tree remain denied by candidate Rules.
