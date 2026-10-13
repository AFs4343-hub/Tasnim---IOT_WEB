# TAS[N]IM — Real device Firebase → Website → History (candidate)

> **Diperbarui:** langkah yang berlaku sekarang ada di
> [PANDUAN_WEBSITE_DATA_ALAT.md](PANDUAN_WEBSITE_DATA_ALAT.md). Website kini
> membaca `hardware_test` secara default (dev & build produksi) dengan sesi
> anonim otomatis, `VITE_TASNIM_FIELD_PREVIEW` tidak lagi diperlukan, dan
> perekam history LIVE (`iot/hardware_test_history_recorder.py`, dry-run
> default) serta impor CSV microSD sudah tersedia. Dokumen di bawah adalah
> catatan historis.

**Goal:** Show actual ESP32 N0/N1/N2 values from Firebase
`/hardware_test/nodes/<node>/latest`, read persistent history from
`/hardware_test/history`, and eventually present actual model output. Do
not invent missing data. This is the research prototype route, not a
production web service.

## What the field screenshots show

At 12 October 2026 the device records visible in Firebase contain
`ph`, `tds`, `turbidity`, `timestamp`, `sequence`, and `rssi` under
each `nodes/N0|N1|N2/latest`. They do NOT include strict V2
`schema_version`, `node_id`, `sample_id` and `quality_flags`.
Those omissions explain why the strict V2 preview had been unable to
display actual field values.

**Do not change the collaborator's working sender merely to display
values.** The new `src/services/fieldHardwarePreview.js` converts the
existing values for website display, preserving their acquisition time.
N1 pH 16.9 is outside the 0–14 range and is displayed as an invalid/missing
value with a warning; TDS 0 and turbidity 0 remain numeric but are flagged
for physical-sensor/clamp checks. No calibration accuracy is inferred.

## Viewing the actual Firebase data — read only

1. Keep `tasnim.config.json` set to SIMULATION (as currently required).
2. Configure the existing `VITE_FIREBASE_*` environment values locally
   so they point to the intended Firebase project. **Do not paste keys or
   login passwords in this chat, commit them, or put them in Git history.**
3. In a local, gitignored `.env.local` file, add:

   ```dotenv
   VITE_TASNIM_FIELD_PREVIEW=YES
   ```

4. Run `npm run dev`. **The dashboard opens immediately: no email,
   password, or separate application login page.**
5. The website subscribes directly (read-only) to
   `/hardware_test/nodes`, `/hardware_test/history`, and
   `/hardware_test/analysis/latest` with the existing Firebase
   `onValue` listeners. If the browser already has an authorized Firebase
   session, the live sensor values can be displayed as Rules allow.

**Important permission limitation:** the unchanged LIVE
`database.rules.json` currently says `hardware_test/.read = auth != null`.
Removing a website login form does **not** grant an anonymous Firebase
read. Without an existing permitted Firebase Auth session, Firebase
correctly denies access; the dashboard stays open and shows a clear
message instead of switching silently to dummy data.

**No-login visual fallback:** use the **Lihat ekspor JSON lokal** control
in the development preview. In Firebase Console, export **only the
`hardware_test` subtree** as JSON (not a full database with credentials).
Select the JSON file in the website. It is parsed on your own device,
not uploaded, and used for the existing monitoring cards, history
graph/table and available AI record. Maximum file size: 2 MB.
The summary explicitly says **Pratinjau JSON Lokal** and is **NOT**
a realtime Firebase connection. If history was missing in the export,
the graph and table correctly remain empty. Choose **Kembali ke Firebase
langsung** to retry actual live listeners.

This choice gets the research dashboard usable immediately without
changing Firebase Rules, credentials, device firmware, or production
mode. For **continuous real-time live data without a manual login**,
a Firebase-authorized read path must eventually be agreed with the
project owner. Do not make `hardware_test` public merely to hide the
permission error.

## How future history records will be stored

**Currently the screenshots show latest only.** Firebase cannot infer a
past time series from three newest values. The microSD CSV is another
possible source for historical samples, but its contents and schema have
not been inspected or imported.

`iot/hardware_test_legacy_history_capture_v1.py` contains a **local
Emulator-only, guarded prototype** that:

- reads only *observed* `nodes/N0|N1|N2/latest`;
- validates timestamp, sequence, node and sensor values;
- creates deterministic V2 metadata for the observed raw sample;
- places a record at `hardware_test/history/{floor(timestamp/300000)*300000}/{node}`;
- preserves the first sample in each slot, allows exact retries,
  refuses overwriting a conflicting sample, and **never changes latest**;
- omits invalid pH (such as N1 = 16.9) and records `PH_INVALID` instead
  of pretending it was within range;
- refuses LIVE databases, production credentials and non-demo projects.

The module does **not currently run against the friend's LIVE Firebase**.
No LIVE history has been created by this candidate commit.
Offline and local Auth/RTDB Emulator tests demonstrate the conversion
and immutability behavior using the screenshot records.

**Decision still needed before writing real history:** should the
collaborator firmware write `history` together with `latest`, or should
an explicitly authorized backend monitor new incoming measurements and
write an immutable 5-minute slot? Both are possible; do not activate
either without verifying writer credentials/Rules and retry behavior.
Only measurements captured going forward are available unless the
actual microSD CSV is reviewed and imported separately.

## AI status

The website will show only AI outputs that already exist at
`hardware_test/analysis/latest`. It will NOT generate model inference
from a `latest` sensor reading on its own. The AI worker requires enough
**complete, valid** 5-minute three-node history slots to form a temporal
context. The screenshot's three readings are from *different* slots,
and N1 pH is invalid; that evidence is **not** sufficient to declare
the AI input ready. The model remains `PROTOTYPE_SIMULATION` until field
validation is completed.

## Verifications without LIVE writes

```bash
node --test tests/test_field_hardware_preview.mjs
python3 -m unittest discover -s tests -p 'test_field_legacy_history_capture_v1.py' -v
python3 scripts/check_production_baseline_guard.py
npm run build
```

Both GitHub Actions workflows also run the candidate tests; the
Emulator workflow runs the localhost RTDB history-capture acceptance
test. These tests use mock/synthetic data, not real Firebase credentials.
