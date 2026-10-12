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
