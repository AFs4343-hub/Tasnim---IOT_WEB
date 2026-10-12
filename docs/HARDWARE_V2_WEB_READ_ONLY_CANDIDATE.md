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


## Collapsible demo-only Supervisor and delayed-data monitor (October 2026)

The original website's `src/App.jsx` layout is **unchanged**.
Only `src/DemoHardwareV2.jsx` adds a collapsed
"Status AI Supervisor dan peringatan operasional" panel after login.
All monitoring logic is read-only and runs in the browser; it never writes
the Firebase database or sends notifications.

The demo Vite bridge's existing authenticated `/snapshot` response now
contains `operational_status`, read ONLY from
`/hardware_test/operations/supervisor/latest`. This path is a whitelisted,
strictly sanitized *copy* of the internal
`/worker_state/ai_v2_supervisor/latest`. Browsers do NOT gain Admin
access to worker_state; candidate RTDB Rules still deny browser writes.
If the supervisor hasn't run on the current demo Emulator, the panel says
no report has been recorded. **The demo seeder does not fake a successful
supervisor run.**

Alert policy is deliberately conservative: an uninitialized node is
unknown, not offline; a still-open 5-minute slot is exempt; an incomplete
slot receives an additional 5-minute grace period; *one* incomplete
closed slot does not trigger an alarm; and two incomplete closed slots among
the four latest considered slots become an engineering warning.
A node with last valid acquisition older than 15 minutes gets a warning
and older than 30 minutes requests review. Clock skew and invalid sensor
flags request review. A waiting lock is not an alarm; recent FAILED,
RETRY_EXHAUSTED or REVIEW_REQUIRED supervisor states request review,
while historical/old reports do not cause an ongoing false alarm.
No signal is a scientific claim that water is safe or unsafe.

Tests: `tests/test_operational_monitor_demo.mjs`,
`tests/test_demo_bridge_emulator.mjs`, and actual RTDB Emulator
supervisor status-publisher tests.


## Viewing an actual synthetic supervisor cycle

The demo's collapsible "Status AI Supervisor" panel starts without a fake
success entry. While the browser demo is running in Codespaces terminal A,
use terminal B and execute
`python3 scripts/run_supervisor_demo_once.py --preview`,
then the explicitly write-authorized
`python3 scripts/run_supervisor_demo_once.py --run`.
The panel refreshes from the browser's authenticated, read-only
Emulator snapshot (approximately every 30 seconds).
`python3 scripts/run_supervisor_demo_once.py --status` checks that the
private and browser-visible status summaries match.

No action button is added to the browser. The trained model is NOT invoked:
the one-shot predictor and initial checkpoint are synthetic fixtures.
Never give public access to the emulator forwarded ports or paste LIVE
Firebase credentials into the demo.


## Shared V2 web/backend contract regression (before final firmware)

The two read-only layers use the *same* synthetic, version-controlled
fixtures in `tests/fixtures/hardware_v2_cross_layer_cases.json`. The
backend test `tests/test_hardware_v2_cross_layer_contract.py` checks
`check_ingestion_packet`; the independent JavaScript test
`tests/test_hardware_v2_cross_layer_contract.mjs` checks website
`nodeMeasurement`, `latestNodes` and `historyRows`.

The website now refuses malformed `sample_id`, duplicate/invalid/too many
quality flags, unknown packet fields, and malformed RSSI metadata. It marks
incomplete or invalid sensor measurements for review and never substitutes
missing measurements with numeric zero. Empty `quality_flags: []` is a
**documented RTDB read exception only**: it may disappear after storage;
it is still **required** by the backend's incoming packet contract.

These tests are deliberately distinct from physical-calibration acceptance:
all test numbers are synthetic, and flags/missing measurements do not prove
the instrument is accurate. The existing `src/App.jsx` production website,
`tasnim.config.json`, LIVE rules, physical firmware and field namespace
remain unchanged. Run all offline web checks before any eventual device
handoff or LIVE activation.


## Fail-closed snapshot polling and offline/recovery states (October 2026)

The private Codespaces browser demo uses
`src/services/demoSnapshotPolling.js` for at-most-one in-flight snapshot
request per logged-in session. Polling stays at 30 seconds, with a 12-second
fetch timeout. Manual Refresh or logout stops the previous poller and aborts
its request; a late response from the previous session cannot update the
new dashboard. The client accepts only the four expected snapshot fields
(`nodes`, `history`, `analysis`, `operational_status`); an invalid,
partial, or unexpected extra payload is rejected rather than rendered.

Any failed fetch clears the previous readings and shows an explicit error
rather than silently reusing stale values. Unauthorized 401/403 responses
clear the demo session; transport outages retain the login so the next
successful 30-second refresh may recover. The injected dashboard placeholder
uses `firebaseStatus=connecting` during first load or logout and
`firebaseStatus=error` on a failed refresh, rather than claiming `online`;
the demo-only last-update display is cleared in these states. No path
falls back to Firebase LIVE or changes the original production listener
logic. The backend snapshot is composed of separate RTDB reads; this
does NOT create an atomic multi-path snapshot.

Unit coverage:
`tests/test_demo_snapshot_polling.mjs` checks overlapping requests,
network failure/recovery, invalid responses, stop/logout abort, and late
previous-session responses. The existing legacy-adapter tests also verify
the connecting/error/online presentation. The full Auth/RTDB Emulator
acceptance remains separate, and physical device and scientific validity
are not claimed by these tests.
