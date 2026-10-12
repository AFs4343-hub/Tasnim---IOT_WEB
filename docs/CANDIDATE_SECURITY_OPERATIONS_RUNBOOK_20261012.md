# TAS[N]IM — Candidate Security & Operations Runbook

**Dated:** 2026-10-12  
**Scope:** `infra/field-data`, synthetic data, localhost Firebase Auth/RTDB
Emulators. **NO LIVE activation, production credentials, automatic cleanup,
device flashing, or merge to `main`.**

## 1. Trust boundaries and access

- Web research roles (admin/manager/viewer) may READ only authorized
  `hardware_test` views under candidate Emulator Rules. Browser writes,
  `gateway_state/nonces` and private `worker_state` remain inaccessible.
- N0/N1/N2 device requests are authenticated with distinct HMAC-SHA256
  secrets and fresh request timestamps by the trusted gateway. The
  measurement timestamp may be historical on microSD backlog replay.
- Current Python HTTP server binds **127.0.0.1 only**; it is **not** an HTTPS,
  rate-limited public service. No node firmware is currently integrated with
  this candidate gateway.
- Admin SDK transactions bypass RTDB Rules. Any future deployment must use
  server-only identity, least privilege, audited IAM, secret management and
  independent review of a real hosting design.

## 2. Candidate incident response: fail closed

| Symptom | Safe reaction | Forbidden automated shortcut |
|---|---|---|
| Bad signature / wrong node | Reject; collect anonymized counters | Reveal the secret or raw signed body |
| Same nonce, different body | 409 / review | Reuse nonce or delete registry to force acceptance |
| Partial nonce/history/latest write | Retry the *identical signed request* while valid | Modify immutable slot or invent a new reading |
| Corrupt newer latest | Conflict / human review | Replace with an older packet |
| AI hash/source mismatch | Stop worker; inspect source archive and digest | Re-run inference and overwrite archived result |
| Interrupted private/status/feed/audit | Inspect, then explicitly repair only valid partial report | Automatically wipe hash chain |
| Emulator/auth unavailable | Hide stale browser snapshot, report connection failure | Fall back to Firebase LIVE |

## 3. Nonce retention and bounded growth

`iot/hardware_test_nonce_audit_v1.py` provides a pure **read-only**
registry inspection helper: counts per node, invalid records and records
older than a configurable review horizon. The **48-hour default is only an
example for policy review**. The tool does **not** touch Firebase and does not
delete or export nonce keys, fingerprints or authentication secrets.

**Production decisions still required:** exact retention that covers device
retry/replay windows, safe time source, durable GC with transactions/race
protection, per-node request quotas and abuse throttling, key issuance,
rotation/revocation, compromise response, and alert thresholds. Never
delete nonce entries merely because this prototype audit flags them.

## 4. Backup, integrity and restoration

`iot/hardware_test_backup_rehearsal_v1.py` makes a bounded SHA-256
envelope for a **caller-supplied synthetic `hardware_test` fixture**, and
can reconstruct a verified COPY in memory. It deliberately has **no
database client or restore command**.

`tests/test_candidate_backup_restore_emulator.py` tests that envelope
with a round-trip into **only**
`/__tasnim_candidate_restore_drill_v1` on the local demo RTDB Emulator.
It rejects altered payloads before restoring, compares readbacks and
cleans up its own test-only namespace. The test does **not** back up a LIVE
dataset, does not test credentials, and does not restore any real node data.

**Production still needs:** immutable encrypted backups, scheduled snapshots,
off-site retention, credential escrow/rotation, scoped RBAC, restore into a
separately isolated project, recovery point/time targets, provenance checks,
and an operator-approved rollback plan. Never perform a LIVE restore based
on green synthetic tests.

## 5. Monitoring, HTTPS and rollback proposal (not implemented)

Before deployment approval, document and verify:

- TLS version, host ownership, certificate renewal, outbound egress limits,
  node authentication and revocation; reject plain HTTP at the public edge.
- Per-device quotas, body-size and timeout limits, authentication failures,
  nonce collisions, duplicate/backfill/conflict rates, history slot gaps,
  worker lease age, Supervisor audit integrity and snapshot age.
- Metrics must be aggregated. Do **not** log HMAC headers, tokens,
  private passwords, raw sensor data or request bodies.
- Define alert owner, severity, on-call escalation, emergency key rotation,
  maintenance mode, database backup/restore procedure, and rollback criteria.
- Never deploy candidate Rules or change `tasnim.config.json` automatically.
  Any LIVE change requires explicit owner approval and an independent
  rollback exercise.

## 6. Verification commands

On `infra/field-data`, without hardware or live credentials:

```bash
python3 scripts/check_production_baseline_guard.py
python3 -m unittest discover -s tests -p 'test_gateway_fault_matrix_v1.py' -v
python3 -m unittest discover -s tests -p 'test_candidate_operations_rehearsal.py' -v
python3 -m unittest discover -s tests -p 'test_candidate_release_evidence.py' -v
```

The two GitHub workflows run broader offline and localhost Emulator suites
and upload **scope-specific evidence JSON**. The evidence intentionally
states `LIVE_DEPLOYMENT_BLOCKED` even when tests pass.

The final firmware handoff is deferred until the tested software candidate
is stable. It must be evaluated against the actual collaborator firmware
later; no automatic firmware rewrite is authorized by this runbook.
