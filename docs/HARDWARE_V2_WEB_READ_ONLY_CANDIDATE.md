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
The app also watches Firebase ID-token changes, so refreshed roles are
rechecked and stale asynchronous checks cannot unlock a later session.
The first signed-in token is force-refreshed only once; subsequent refresh
events are checked without recursively forcing another refresh.
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
  missing or the three-node history is incomplete. A matching timestamp
  proves only **time alignment**, not a source digest verification.
- Treat missing model version, session ID, valid status, or model disagreement
  metadata as an untrusted AI record rather than presenting a green status.
- Completeness is *structural*. It is not sensor calibration proof.
- The candidate uses a bounded recent-history window (60–240 records) and
  is not a full historical exporter or observation-session manager.
- An Auth Emulator + RTDB Emulator automated integration check now exercises
  actual email/password sign-in, token claims, and database permissions
  through Firebase's web SDK. This is not a visual browser acceptance test:
  UI rendering and refresh behavior with a real browser still require
  a separate authorized staging/local check.
- Browser auth login, role provisioning, and Rules deployment remain
  unapproved; no physical ESP32 validation is claimed.

### Auth Emulator integration acceptance (new)

The full Codespaces check now starts **both** Firebase Auth at
`127.0.0.1:19004` and RTDB at `127.0.0.1:19003` with
`GCLOUD_PROJECT=demo-tasnim-security`. A guarded Python script provisions
synthetic email/password users and `tasnim_role` claims *only* in the Auth
Emulator. A Node test uses the real Firebase Web Auth SDK to sign in, obtains
actual emulator ID tokens, then reads/denies the same paths used by the
hardware dashboard via the RTDB client SDK. A forced token refresh also
checks that a revoked `viewer` claim disappears.

This is **not** a real browser rendering test, not production account
provisioning, and not a Firebase LIVE migration. Only a trusted backend may
grant real custom claims. Test credentials are deterministic fakes valid only
inside the emulator; never reuse them on production accounts.

## Verification

```bash
node --test tests/test_hardware_v2_view.mjs
npm run build
bash scripts/check_ai_v2_candidate.sh
```

The last command includes current Python, Firebase Emulator, and build tests
and must continue to work without a LIVE Firebase deployment.

## Codespaces browser login with synthetic Emulator accounts

Stop the earlier Vite terminal with Ctrl+C. Run the one-command demo:

```bash
bash scripts/run_hardware_demo_codespaces.sh
```

This checks the current branch and production config, starts Auth on
`127.0.0.1:19004` and RTDB on `127.0.0.1:19003`, creates **synthetic**
test-only accounts, seeds recent sensor data with one incomplete slot,
and launches Vite on port `5173`. Keep this terminal running.
In Codespaces PORTS set `5173` to **PRIVATE**, then click Open in Browser.
Only port 5173 needs forwarding; the Emulators stay on loopback.

Select `viewer@tasnim-auth-demo.invalid`, `manager@...` or
`admin@...` on the demo login form. Password for all three is
`EmulatorOnly_2026_Test!`.

**Security:** The development-only `/__tasnim_demo__` route forwards
same-origin browser login to the Auth Emulator and performs only three
whitelisted RTDB reads with that token. The Firebase RTDB Emulator enforces
candidate Rules. Tokens stay in browser memory and vanish on logout/reload.
No LIVE Firebase credentials are used, no live dashboard is mounted,
and this demo endpoint does not exist in the production build.
Stop with Ctrl+C before resuming the normal website.

The browser demo is a real Emulator login, but NOT a production release,
an actual ESP32 measurement, or model scientific validation. Dashboard
freshness/completeness indicators are engineering checks only.

## Original-dashboard preservation (October 2026)

The earlier Codespaces demo rendered a **separate** dashboard with different
styling. The corrected demo now shows the **same preexisting** `src/App.jsx`
and sections: Monitoring, Grafik, Statistik, Spasial, Kinerja IoT, Peta,
AI, Riwayat. Login is an overlay on top of the original website, not a
replacement dashboard.

After login, a read-only adapter converts Emulator V2 measurements into
the existing dashboard's node/history shape. All three Firebase LIVE
`onValue` effects in App return before subscribing whenever `demoSnapshot`
is provided, including before sign-in. The production website without that
prop runs the original simulation subscriptions unchanged.

Emulated latest/history values remain synthetic. Invalid/missing sensors
stay null, and synthetic model decisions are deliberately *not* presented
as validated RF/IF analysis. Only a compact "Emulator" banner and an optional
expandable data-readiness panel are added; all original dashboard components
and section markup remain in place.

Verification: `node --test tests/test_demo_legacy_adapter.mjs`,
`npm run build`, and the complete Codespaces demo/CI checks.
