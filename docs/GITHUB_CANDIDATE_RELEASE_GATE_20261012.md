# TASNIM — Candidate GitHub Release Gate (12 October 2026)

**Scope:** `infra/field-data` only; synthetic V2 and localhost Auth/RTDB
Emulators. **Not authorization to deploy, merge to `main`, flash ESP32,
alter Firebase LIVE, or claim field-quality measurements.**

## Milestones covered by CI

| Area | Evidence type | Candidate state |
|---|---|---|
| V2 packets & Python/JS contract | Shared synthetic offline fixtures | Implemented, regression-tested |
| Signed device ingestion | HMAC, nonce, immutable slots, pointer validation | Local-only prototype |
| N0/N1/N2 read-only dashboard | Polling, state recovery, slot continuity | Demo-ready candidate |
| AI worker and supervisor | Leases, checkpoint hash, crash recovery, audit | Synthetic Emulator candidate |
| Auth and RTDB Rules | Real local Auth/RTDB Emulator | Tested only in Emulator |
| Production gateway | TLS, keys, quotas, nonce lifecycle | **BLOCKED / not implemented** |
| Field sensor calibration, runtime, and firmware handoff | Physical evidence required | **DEFERRED to last stage** |

## Automated protection

`scripts/check_production_baseline_guard.py` checks **Git blob content
hashes**, not merely filenames, for the currently reviewed baseline of
`database.rules.json`, `firebase.json`, `tasnim.config.json`, and
`src/services/firebase.js`. CI offline and CI Emulator now run it before
their principal tests. Missing, symlinked or unexpectedly modified baseline
files fail the candidate build. This is an **accidental-change guard**, not
a replacement for branch protection or human review. Changes to the guard
itself must be reviewed independently.

`scripts/check_ai_v2_candidate.sh` performs the same check when run
explicitly in Codespaces. It also requires a trusted local prototype model
bundle, which is **not present in GitHub CI**; passing CI does not prove the
`joblib` file exists or is scientifically accurate in field conditions.

## Required gates before ANY deployment approval

1. Review final browser/worker/device **data schema and trust boundaries**.
   Preserve `simulation` defaults until deployment is explicitly approved.
2. Specify the actual authenticated **HTTPS** gateway architecture, physical
   device key lifecycle and revocation, rate limiting, nonce retention/GC,
   network isolation, incident logging and least-privilege access.
3. Validate database and AI **provenance under concurrent ingestion**, not
   just locally serialized demo transactions. Establish atomicity/fencing or
   formal limits for cross-path transactions.
4. Create reproducible backups, restore tests, rollback procedure, data
   retention plan, monitoring and operator runbook.
5. Verify the AI model with properly labelled field/reference datasets;
   **prototype simulation tests are not ground-truth accuracy evidence**.
6. At the **last stage**, reconcile the *actual final firmware* supplied by
   the collaborator with the signed gateway contract, including stable sample
   IDs, NTP/request clocks, microSD outbox, retry behavior and per-node sensor
   calibration. Perform compile, hardware and field trials separately.
7. Obtain explicit project-owner approval for any LIVE Rules change,
   credentials, deployment, or merge to `main`.

## Candidate verification commands

From the Codespaces repository on `infra/field-data`:

```bash
python3 scripts/check_production_baseline_guard.py
python3 -m unittest discover -s tests -p 'test_production_baseline_guard.py' -v
python3 -m unittest discover -s tests -p 'test_backend_latest_integrity_v1.py' -v
```

These three commands are read-only with respect to the repository and
Firebase. The complete test pack may require locally installed Node,
Python packages and an explicitly started **localhost** Emulator. Never
substitute a production Firebase URL or credentials for missing test tools.

## Status interpretation

- **CI PASS:** candidate software checks passed on synthetic/local fixtures.
- **REVIEW REQUIRED:** a conflicting stored pointer, source digest, hash
  chain, or privacy boundary needs a human decision; do not overwrite it.
- **DEPLOYMENT BLOCKED:** production/network/hardware gates above remain
  unmet. A green CI must not be treated as permission to deploy.


## Four-track GitHub candidate completion (scope: synthetic/local only)

The four requested GitHub-preparation tracks are now covered by explicit
tests and documents, **without** changing field/production resources:

| Track | New verification evidence | Operational limits |
|---|---|---|
| Full-stack chain | `tests/test_full_stack_candidate_emulator.py` sends signed HTTP packets for N0/N1/N2 to actual localhost RTDB; invokes guarded synthetic Supervisor, checks archived AI/latest/status/audit and source digests. Then `tests/test_full_stack_browser_emulator.mjs` logs into real Auth Emulator and verifies the read-only Vite dashboard, 3 history slots and prototype result. | No physical ESP32, no actual trained-model field evaluation, no HTTPS production |
| Fault matrix | `tests/test_gateway_fault_matrix_v1.py` injects failures at nonce/history/latest writes, identical replay, conflicting nonce, concurrent collisions and delayed backfill. | Independent transactions can still partially commit; production fencing/concurrency design remains open |
| Security/operations | `tests/test_candidate_operations_rehearsal.py` inspects nonce-retention diagnostics without cleanup, and validates tamper-evident synthetic backup-copy checks; `tests/test_candidate_backup_restore_emulator.py` tests a restore in isolated localhost Emulator namespace. | No actual nonce GC, public rate limit/TLS, key rotation, real backup or LIVE rollback implemented |
| GitHub release audit | `tests/test_candidate_release_gate_static.py`, refreshed README, dedicated candidate security runbook, and two GitHub Actions artifact reports generated **only after corresponding checks pass**. | Evidence is per workflow and always explicitly says `LIVE_DEPLOYMENT_BLOCKED` |

The CI artifacts `tasnim-candidate-offline-evidence` and
`tasnim-candidate-emulator-evidence` contain no credentials or sensor
readings and identify commit SHA, test scope, baseline guard, remaining
production blockers and the unintegrated firmware stage. Both workflow
runs must report **success** before the candidate integration track can
be called complete. A successful offline job alone does not imply the
Emulator job passed, and vice versa.

## Operator handoff (GitHub candidate only)

1. Review both CI runs and obtain both scope-specific evidence artifacts.
2. Run the frozen production baseline guard and targeted offline tests
   on the local `infra/field-data` branch.
3. Check `git status -sb`; preserve all collaborator-owned untracked
   calibration ZIPs and firmware directories. NEVER use broad `git add .`,
   `git clean`, reset, or deletion.
4. Keep production changes blocked until the independent infrastructure,
   field validation, actual backup/rollback and owner-approval gates pass.
5. **Last software stage:** compare the actual latest collaborator ESP32
   firmware against the contract and generate a targeted integration plan;
   do not invent an active firmware version from candidate sources.


## Local candidate rate-limit guard and production decision

On localhost Emulator, the signed HTTP demo gateway additionally enforces
a shared, bounded, **120 POST / 60 s per-process** budget before
body decoding or RTDB transactions. A 429 is a transient admission
response; it is not an ingestion acknowledgement. The guard does NOT
authenticate clients, rate-limit by physical node, protect a distributed
deployment, implement actual key rotation or delete nonce records.
See `docs/GATEWAY_PRODUCTION_ARCHITECTURE_DECISION_DRAFT.md` for the
proposed HTTPS/HMAC/nonce/backup acceptance matrix. Production activation
remains **BLOCKED**.
