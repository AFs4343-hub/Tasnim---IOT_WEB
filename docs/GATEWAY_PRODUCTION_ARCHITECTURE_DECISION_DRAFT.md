# TAS[N]IM — Gateway Production Architecture Decision Draft

**Stage:** candidate design review, 2026-10-12. No production release
approval. No public listeners, LIVE credentials, deploy or ESP32 changes.

## Architecture under consideration

```text
ESP32 N0/N1/N2 with provisioned per-node device key
       |
       | HTTPS TLS 1.2+ (prefer TLS 1.3); HMAC-SHA256 request signature
       v
Trusted managed HTTPS ingress / reverse proxy
  - source/network request budget BEFORE parsing body
  - strict content-length/size, timeout, request method/path
  - fixed trusted forwarded-header policy (never trust client XFF)
       |
       v
Stateless gateway worker behind private network identity
  - authenticate device node + signature + fresh request timestamp
  - bounded per-authenticated-node shared quota
  - atomic nonce claim/deduplication
  - immutable 5-minute slot and latest pointer semantics
  - aggregated metrics, no payload/secret logging
       |
       v
RTDB limited to dedicated server identity; browser only research reads
       |
       +--> AI Worker / Supervisor with lease and archived digest checks
       +--> read-only research dashboard
```

**This diagram is a target design, not a running service.** The existing
Python `iot/hardware_test_gateway_http_v1.py` remains loopback-only and
forbids a production Firebase endpoint. Its new
`DemoSlidingWindowLimiter` shares a fixed **120 POST requests/60 s**
budget among **all** loopback callers within one server process and
returns generic HTTP **429 / DEMO_RATE_LIMITED** *before body parsing,
authentication or RTDB writes*. This is an abuse-resilience regression
test, **NOT** production scale, per-device admission control, distributed
throttling, multi-worker protection, TLS or an edge firewall. Health checks
are excluded from this POST budget.

## Production decisions that require explicit owner approval

| Area | Approval required | Acceptance test required |
|---|---|---|
| HTTPS termination | Trustworthy ingress, certificates, renewals, TLS policy and private worker network | HTTP cannot enter the public edge; certificate and renewal tests |
| HMAC identities | Distinct secret store entries for N0/N1/N2, key IDs, least-privileged service identity, revocation path | Wrong/revoked node keys denied without logging payload |
| Key rotation | Manual staged activation and rollback, planned grace window, non-reusable key IDs, permission review | All three nodes tested separately, no insecure permanent overlap |
| Traffic quotas | Multi-instance shared pre-auth source budget **and** post-auth per-node budget | Concurrent requests across instances respect quotas; 429 preserves data |
| Nonces | Durable conditional claim, retention beyond maximum accepted retry window, clock safety, garbage-collection fencing | Concurrent claim-vs-cleanup test; no re-acceptance of replayed nonce |
| Multi-path RTDB | Formal accepted partial-commit semantics or transaction redesign | Crash at every checkpoint, deterministic idempotent repair |
| Observability | No raw HMAC headers/body, password, key IDs used as secrets, or real water measurements in logs | Scrub/redaction and retention tests; alerting drills |
| Recovery | Independent encrypted backup and isolated restore environment; emergency rollback owner | RPO/RTO evidence from a real staging exercise |

### Key rotation: proposed safe operator sequence (NOT implemented)

1. Inventory each physical node's deployed key identifier and last confirmed
   firmware/measurement version without printing the key bytes.
2. Provision a new key using the approved secret manager, distinct from
   all other nodes; record key ID and operator-approved activation window.
3. Coordinate gateway support for short dual-key acceptance **only** if
   explicitly implemented and independently tested. HMAC replay registry
   must remain coherent across old/new key IDs; key changes cannot reset
   replay protection.
4. Update a **single isolated device at a time** under a field test plan,
   verify successful signed requests and rollback, then revoke the old key.
5. Revoke compromised credentials immediately according to incident
   policy, without deleting nonce history to 'fix' authentication.

No existing module implements dual-key acceptance, actual revocation,
TLS deployment or cloud secret management. The future firmware integration
must establish how key IDs and timestamp sources are represented.

### Nonce retention policy gate

`iot/hardware_test_nonce_audit_v1.py` counts old entries without deleting
anything. Its default 48-hour horizon is **illustrative, not permission**
to delete: a valid signed retry could outlive it if the actual physical
outbox behavior or gateway timestamp constraints differ. A robust policy
must account for exact signed request timestamp expiry, microSD retry logic,
offline clock resets, replay response behavior, key rotation and
transactional claim-vs-GC races. Design/test a safe retention+fencing
algorithm separately before enabling ANY cleanup.

### Operational gating

Before launch, the operator must verify branch protection, least-privilege
deployment identities, signed artifact provenance, resource limits,
monitoring/alarms, backup/rollback, test results on staging with realistic
concurrency, physical firmware integration and field validation. Mark
`LIVE_DEPLOYMENT_BLOCKED` until each gate has evidence and explicit approval.

**Scope of current automatic evidence:**
`tests/test_gateway_demo_rate_limit_v1.py` and
`tests/test_hardware_test_gateway_http_v1.py` exercise the single-process
demo limiter and its HTTP/RTDB no-write denial boundary. Existing
`tests/test_gateway_fault_matrix_v1.py` and real Emulator suites cover
transaction failure/idempotency, but not distributed production quotas
or a real nonce garbage collector.
