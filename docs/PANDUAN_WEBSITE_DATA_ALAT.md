# Panduan TAS[N]IM — Website menerima data alat dari Firebase

Panduan praktis supaya dashboard bekerja dengan **data alat ESP32 asli**
(`hardware_test`) persis seperti saat diuji dengan simulasi: kartu node,
grafik, statistik, delta antar-node, kinerja IoT, analisis AI dan riwayat.

```text
ESP32 N0/N1/N2 ──► hardware_test/nodes/Nx/latest      (firmware sekarang)
                         │
             [perekam history]  python3 -m iot.hardware_test_history_recorder --write
                         ▼
                 hardware_test/history/<slot 5 menit>/N0|N1|N2
microSD CSV ──[impor CSV]──┘      ▲
                         │        │
                   [AI realtime]  python3 -m ai.realtime_inference --root hardware_test
                         ▼
     hardware_test/history/<slot>/analysis  +  hardware_test/analysis/latest
                         │
                         ▼
          Website (tombol "Data Alat (Firebase)") — hanya membaca
```

Sama dengan simulasi: `iot/simulator.py` menulis `simulation/...`, AI menulis
analisis, website menampilkan. Data simulasi dan data alat **tidak pernah
tercampur**; pilih lewat tombol **Data Alat / Simulasi** di atas dashboard.

---

## 1. Persiapan (sekali saja)

1. **Konfigurasi website.** Salin `.env.example` menjadi `.env.local` lalu isi
   `VITE_FIREBASE_*` dari Firebase Console → Project settings → Your apps.
   (Jika `.env` lama dari mode simulasi sudah ada dan berfungsi, tidak perlu
   diubah.)
2. **Izinkan website membaca `hardware_test` tanpa form login.** Rules
   sekarang mensyaratkan `auth != null`. Website otomatis membuat **sesi
   anonim**, jadi cukup aktifkan:
   Firebase Console → Authentication → Sign-in method → **Anonymous → Enable**.
3. **(Sangat disarankan) kunci penulisan untuk tamu anonim.** Dengan Rules
   sekarang, akun anonim juga bisa *menulis* ke `hardware_test` (sudah diuji
   di Emulator). Ubah satu baris di Firebase Console → Realtime Database →
   Rules (lihat `database.rules.web-anonymous-read.candidate.json`):

   ```json
   "hardware_test": {
     ".read": "auth != null",
     ".write": "auth != null && auth.provider != 'anonymous'"
   }
   ```

   Hasil uji Emulator: website (anonim) tetap bisa membaca, firmware
   (email/password) tetap bisa menulis, perekam & AI (service account)
   tidak terpengaruh, tamu anonim **tidak** bisa menulis.
4. **Backend Python** (perekam history, impor CSV, AI):
   ```bash
   pip install -r ai/requirements.txt
   ```
   Simpan service account ke `iot/serviceAccountKey.json`
   (Firebase Console → Project settings → Service accounts → Generate new
   private key). File ini sudah di-`.gitignore`; **jangan di-commit**.
5. **Model AI prototipe.** Jika `ai/models/tasnim_ai_bundle.joblib` belum ada:
   ```bash
   python3 -m ai.generate_data && python3 -m ai.train_models
   ```

## 2. Menjalankan website

```bash
npm install
npm run dev          # buka http://localhost:5173
```

- **Data Alat (Firebase)** — default. Membaca `hardware_test` secara real-time.
- **Simulasi** — dashboard dummy lama (`simulation`), tetap bisa dipakai.
- **Buka CSV/JSON** — melihat file microSD (`tasnim_N0.csv`, `tasnim_N1.csv`,
  `tasnim_N2.csv`, boleh dipilih sekaligus) atau JSON hasil impor/ekspor
  Firebase. File **dibaca di browser saja, tidak diunggah**.

Semua waktu ditampilkan dalam **WITA**. Pilihan sumber data diingat browser.

Build untuk hosting: `npm run build` (folder `dist/`). Deploy Hosting tetap
keputusan tim (`firebase deploy --only hosting`).

## 3. Saat sesi pengukuran di lapangan

Firmware sekarang hanya mengirim `latest`, jadi **history dibuat oleh
perekam**. Jalankan di laptop/Codespaces selama sesi:

```bash
python3 scripts/run_hardware_test_stack.py --write
```

Perintah ini menjalankan dua proses sekaligus (bisa juga terpisah):

| Proses | Perintah terpisah | Fungsi |
|---|---|---|
| Perekam history | `python3 -m iot.hardware_test_history_recorder --write` | Tiap 15 detik membaca latest N0/N1/N2, menyimpan pengukuran ke slot 5 menit |
| AI realtime | `python3 -m ai.realtime_inference --root hardware_test` | Menganalisis setiap slot yang lengkap N0+N1+N2, menulis `analysis` |

Tanpa `--write` keduanya **dry-run** (hanya menampilkan, tidak menulis).

Aturan perekam: sampel **pertama** tiap node dalam satu slot 5 menit yang
dipakai, slot yang sudah terisi tidak pernah ditimpa, `nodes/latest` tidak
diubah, nilai di luar rentang (mis. pH 16.9) **tidak** dijadikan angka palsu
— field dihilangkan dan diberi flag `PH_INVALID`.

## 4. Data dari microSD (CSV)

Format firmware: `timestamp,node,sequence,ph,tds,turbidity,rssi`
(`NA` = tidak terbaca). Titik koma/desimal koma dari Excel juga diterima.

```bash
# 1) Cek dulu (tidak menulis apa pun)
python3 scripts/import_sd_csv.py tasnim_N0.csv tasnim_N1.csv tasnim_N2.csv

# 2a) Tanpa Firebase: buat JSON + analisis AI, lalu buka di website
python3 scripts/import_sd_csv.py tasnim_N*.csv --out-json sesi1.json --analyze

# 2b) Masukkan ke Firebase (hanya slot kosong), lalu AI menganalisis backlog
python3 scripts/import_sd_csv.py tasnim_N*.csv --write
python3 -m ai.realtime_inference --root hardware_test --once
```

Setelah 2b, website (Data Alat) langsung menampilkan grafik, riwayat dan AI
untuk seluruh sesi. CSV yang slot-nya sudah direkam perekam live **tidak**
menimpa data tersebut. Jika CSV tidak punya kolom `node`, nama file harus
memuat `N0`/`N1`/`N2` atau pakai `--node N1`.

## 5. Membaca dashboard

| Bagian | Isi |
|---|---|
| Ringkasan & Monitoring Node | Nilai terbaru tiap node, Online jika data ≤ 10 menit, peringatan kualitas (mis. *TDS = 0 (cek sensor / clamp)*) |
| Tren / Statistik | Dari history 5 menit; rentang 2 jam / 6 jam / semua yang dimuat |
| Analisis Spasial | Δ N0→N1 dan N0→N2 dari nilai terbaru |
| Kinerja IoT | RSSI, kelengkapan slot per node, *transmission success* & *data loss* per sesi (jeda > 15 menit = sesi baru) |
| Peta | Isi `VITE_TASNIM_NODE_COORDS` di `.env.local` atau kirim latitude/longitude dari GPS |
| AI | Hasil RF / Isolation Forest / Z-score per slot; peringatan bila model berbeda pendapat atau \|z\| ≥ 3 |
| Riwayat | Filter status/lokasi/tanggal (WITA), detail per slot, ekspor CSV |

## 6. Jika ada masalah

| Gejala | Penyebab & solusi |
|---|---|
| "Login anonim belum diaktifkan…" | Langkah 1.2 (aktifkan Anonymous) |
| "Firebase menolak akses hardware_test…" | Rules/sesi; cek langkah 1.2–1.3 |
| Kartu node tampil tetapi grafik kosong + kotak biru "history masih kosong" | Perekam belum jalan atau CSV belum diimpor (bagian 3/4) |
| AI "Analisis ditunda / data kritis belum lengkap" | Slot terbaru belum berisi N0+N1+N2 valid (mis. turbiditas `NA`, pH di luar 0–14) |
| Node "Waktu Tidak Valid" | Jam ESP32 (NTP/RTC) lebih dari 1 menit di depan |
| Perekam `PERIKSA … invalid_timestamp…` | Timestamp alat bukan epoch milidetik UTC atau jam alat salah |

## 7. Batasan yang perlu diketahui

- **Model AI masih prototipe yang dilatih dari data simulasi** (baseline
  TDS ≈ 210 ppm, turbiditas ≈ 8–10 NTU). Uji dengan CSV sintetis bergaya
  lapangan menunjukkan: jika baseline lapangan berbeda (mis. TDS ≈ 110,
  turbiditas ≈ 25–35), model menandai hampir semua slot sebagai anomali; pada
  data berbaseline simulasi hanya anomali yang disisipkan yang terdeteksi.
  Sebelum hasil AI dipakai untuk kesimpulan, model perlu dilatih ulang /
  dikalibrasi dengan data normal lapangan dan divalidasi dengan ground truth.
- Latency belum bisa dihitung karena paket alat hanya membawa waktu ukur.
- Perekam hanya mengarsipkan pengukuran yang terlihat **selama ia berjalan**;
  pengukuran saat perekam mati diambil dari CSV microSD.
- Website tidak menulis apa pun ke Firebase. Deploy Rules/Hosting tetap
  dilakukan manual oleh tim.

## 8. Uji tanpa Firebase LIVE (opsional, pengembang)

```bash
python3 -m unittest discover -s tests -p 'test_hardware_test_history_recorder.py'
python3 -m unittest discover -s tests -p 'test_hardware_test_csv_import.py'
python3 -m unittest discover -s tests -p 'test_realtime_inference_hardware_root.py'
node --test tests/test_web_data_pipeline.mjs tests/test_field_hardware_preview.mjs
npm run build
```

Untuk mencoba alur lengkap dengan Firebase Emulator lokal, arahkan
`VITE_FIREBASE_DATABASE_URL=http://127.0.0.1:9000/?ns=<nama>` dan
`VITE_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`; perekam history dan
impor CSV mengikuti `FIREBASE_DATABASE_EMULATOR_HOST` dan `TASNIM_DATABASE_URL`.
