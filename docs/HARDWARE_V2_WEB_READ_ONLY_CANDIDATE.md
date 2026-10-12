# TASNIM — Candidate Read-only Hardware V2 Web View

**DRAFT / NOT DEPLOYED / NOT AN ACTIVATION OF FIREBASE LIVE RULES**

The website's default `tasnim.config.json` remains exactly
`{"activeDataRoot":"simulation","mode":"SIMULATION"}`.
This candidate adds an entirely separate `HardwareV2Candidate` view.
The existing simulation dashboard and its listeners are not modified.

## Explicit opt-in for local development only

With an authorized local developer environment and the existing private
`VITE_FIREBASE_*` values configured, run:

```bash
VITE_TASNIM_HARDWARE_V2_PREVIEW=YES npm run dev
```

Without that exact build-time value, **no switch is shown and the candidate
view is not mounted**. The mode starts on the existing simulation dashboard,
even when the switch is enabled. Never expose the opt-in in production
Hosting builds without separate approval, and never forward development
ports publicly as an alternative to approval.

The candidate view prompts for an account in Firebase Authentication.
After a fresh token check, the account must have a custom claim
`tasnim_role` equal to `admin`, `manager`, or `viewer`. Missing or
unexpected claims cause a fail-closed screen without any hardware listeners.
Assign roles **only from an authorized trusted backend** (never browser JS).
The UI role check is usability defense, not the security boundary: actual
Firebase Rules must enforce claims on the database side. The candidate
security Rules are not deployed, so preview operation against LIVE is NOT
an instruction to deploy them or change existing LIVE permissions.

Only reads are performed:
- `/hardware_test/nodes`
- `/hardware_test/history` (bounded newest-window query)
- `/hardware_test/analysis/latest`

No Firebase write API is imported. On permission denial, data is cleared
rather than silently falling back to simulation or claiming healthy telemetry.

## Presentation and limitations

- Use sensor acquisition UTC milliseconds and show WITA only for display.
- Treat missing RTDB `quality_flags: []` as empty while showing nonempty
  unexpected flags as data needing review. Invalid sensor values are shown
  as '—', not faked as zero.
- Require exact N0/N1/N2 contract metadata to display measurements.
- Mark AI as prototype only, with an explicit status when its slot is stale,
  missing or the three-node history is incomplete.
- Completeness is *structural*. It is not sensor calibration proof.
- The candidate uses a bounded recent-history window (60–240 records) and
  is not a full historical exporter or observation-session manager.
- Browser auth login, role provisioning, and Rules deployment remain
  unapproved; no physical ESP32 validation is claimed.

## Verification

```bash
node --test tests/test_hardware_v2_view.mjs
npm run build
bash scripts/check_ai_v2_candidate.sh
```

The last command includes current Python, Firebase Emulator, and build tests
and must continue to work without a LIVE Firebase deployment.
