# TAS[N]IM — Operasional harian (tanpa terminal)

Setelah persiapan sekali jalan di bawah, pemakaian sehari-hari cukup lewat
**browser (HP atau laptop)**:

| Kebutuhan | Caranya |
|---|---|
| Lihat website | Buka **https://omirisetmonitoring.web.app** |
| History live saat sesi | GitHub → **Actions → TASNIM sesi live → Run workflow** |
| Masukkan CSV microSD | Upload ke `data/sd/` → **Actions → TASNIM impor CSV microSD + AI → Run workflow** |
| Hapus data tak diperlukan | **Actions → TASNIM hapus data (cadangan otomatis) → Run workflow** |

Tidak ada langkah yang membuat, mengganti, atau menghapus API key. Website
memakai API key yang sama dengan ESP32, dan firmware tidak perlu diubah.

---

## A. Persiapan (sekali saja, di terminal Codespaces)

```bash
cd /workspaces/Tasnim---IOT_WEB
git pull --ff-only origin infra/field-data
```

1. **Pasang website online**
   ```bash
   bash scripts/deploy_website.sh
   ```
   Skrip memakai `.env.local` yang sudah ada dan **berhenti** jika API key
   kosong, jadi website online tidak mungkin tampil kosong. Login Firebase
   diminta sekali (buka link, login akun Google pemilik proyek, salin kode).
   Ketik `YA` untuk deploy. Hasilnya link tetap
   `https://omirisetmonitoring.web.app`. Versi website sebelumnya bisa
   dikembalikan di Firebase Console → Hosting → Release history.
   Ulangi skrip ini **hanya jika kode website berubah**.

2. **Simpan kunci service account sebagai secret GitHub**
   (dipakai tombol sesi live dan impor CSV):
   ```bash
   bash scripts/setup_github_actions.sh
   ```
   Login GitHub diminta sekali (pilih *Login with a web browser*, masukkan
   kode). Isi kunci tidak ditampilkan. Cara manual: github.com → repo →
   Settings → Secrets and variables → Actions → *New repository secret*,
   nama `FIREBASE_SERVICE_ACCOUNT`, isi = seluruh isi `iot/serviceAccountKey.json`.

3. **Munculkan tombol "Run workflow"**. GitHub hanya menampilkan tombol untuk
   workflow yang ada di branch utama `main`. Pilih salah satu:
   - Gabungkan `infra/field-data` ke `main` lewat Pull Request (disarankan;
     setelah itu semua tombol muncul di tab Actions), **atau**
   - sementara, jalankan dari terminal Codespaces:
     ```bash
     bash scripts/run_actions.sh live 3      # sesi live 3 jam
     bash scripts/run_actions.sh impor       # impor CSV di data/sd
     ```

## B. Setiap hari pengukuran

### Sebelum / saat sesi
1. Nyalakan N0, N1, N2 dan biarkan stabil ±10 menit (probe tercelup).
2. Buka github.com → repo **Tasnim---IOT_WEB** → tab **Actions** →
   **TASNIM sesi live (rekam history + AI)** → **Run workflow** → pilih branch
   (`main` atau `infra/field-data`) dan **durasi** (jam) → **Run workflow**.
3. Buka **https://omirisetmonitoring.web.app** di HP. Kartu node, grafik,
   Kinerja IoT, AI dan Riwayat ter-update otomatis setiap ada data baru.
4. Selesai lebih cepat? Buka run yang sedang berjalan → **Cancel run**.
   Kalau durasi habis, run berhenti sendiri.

### Setelah sesi (data CSV microSD)
1. Salin file CSV dari kartu microSD ke laptop/HP.
2. github.com → repo → folder **data/sd** → **Add file → Upload files** →
   seret file `tasnim_N0.csv`, `tasnim_N1.csv`, `tasnim_N2.csv`. Disarankan
   buat subfolder per tanggal: ketik `2026-10-14/` di depan nama file saat
   upload, atau upload ke `data/sd/2026-10-14/`. Lalu **Commit changes**.
3. Tab **Actions** → **TASNIM impor CSV microSD + AI** → **Run workflow** →
   folder (mis. `data/sd/2026-10-14`), mode **tulis** → **Run workflow**.
   Mode **cek** hanya memeriksa isi CSV tanpa menulis apa pun.
4. Setelah run hijau ✅, buka website → **Data Alat**. History dan hasil AI
   seluruh sesi sudah ada. Ringkasan impor ada di halaman run; file
   `hasil_impor` (Artifacts) bisa dibuka di website lewat **Buka CSV/JSON**.

Impor CSV hanya mengisi slot yang masih kosong, jadi aman dijalankan
setelah sesi live: data live tidak ditimpa, celahnya dilengkapi dari CSV.

### Menghapus data yang tidak diperlukan (cadangan otomatis)
Contoh: data uji coba sebelum penelitian, atau 10 menit saat sensor terangkat.

1. Tab **Actions** → **TASNIM hapus data (cadangan otomatis)** → **Run workflow**.
2. Isi **dari** dan **sampai** (WITA, format `2026-10-12 00:00`), pilih
   **node** (`semua` atau satu node), isi **alasan**, mode **cek** → jalankan.
   Lihat ringkasan run: daftar slot yang akan terhapus.
3. Jika benar, jalankan lagi dengan input yang sama tetapi mode **hapus**.
4. Yang terjadi otomatis:
   - data disalin dulu ke tempat sampah Firebase (`tasnim_trash`, tidak tampil
     di website) dan ke Artifacts **cadangan_hapus** (90 hari), baru dihapus;
   - rentangnya masuk **daftar hapus**: impor CSV dan sesi live otomatis
     melewati data di rentang itu, jadi CSV microSD tidak perlu diedit dan
     data tidak masuk lagi;
   - hasil AI terbaru di website diperbaiki bila ikut terhapus.
5. Salah hapus? mode **daftar** untuk melihat ID cadangan, lalu mode
   **pulihkan** + isi **id_cadangan**. Data kembali (tanpa menimpa slot yang
   sudah terisi) dan rentangnya dicabut dari daftar hapus.

Tips: rentang yang belum ada di Firebase pun boleh "dihapus" — gunanya
mencegah baris CSV di rentang itu ikut diimpor nanti.

Dari terminal Codespaces: `python3 scripts/hapus_data.py --help`.

## C. Kuota GitHub Actions (repo private)

Akun GitHub Free mendapat ±2.000 menit Actions per bulan untuk repo private.
Sesi live memakai menit selama berjalan (3 jam = ±180 menit); impor CSV
hanya ±2–3 menit. Contoh: 6 hari × 3 jam live ≈ 1.100 menit (aman); 6 hari
× 6 jam ≈ 2.200 menit (melebihi). Untuk hari panjang, andalkan CSV microSD
atau jalankan perekam di Codespaces:
`python3 scripts/run_hardware_test_stack.py --write`. Sisa kuota: github.com
→ Settings → Billing and plans.

## D. Jika ada masalah

| Gejala | Solusi |
|---|---|
| Run gagal: "Secret FIREBASE_SERVICE_ACCOUNT belum diisi" | Langkah A.2 |
| Tidak ada tombol Run workflow | Langkah A.3 (workflow belum ada di `main`) |
| Impor: "Tidak ada file .csv di …" | Cek nama folder di input sama dengan folder upload |
| Website online tidak berubah setelah kode diperbarui | Jalankan lagi `bash scripts/deploy_website.sh` |
| Website menampilkan "Konfigurasi Firebase belum lengkap" | Deploy dibuat dari `.env.local` yang kosong; perbaiki `.env.local`, deploy ulang |
| AI terus "Menunggu minimal 2 slot…" | Belum ada slot berisi N0+N1+N2 valid (cek alat dan sensor) |

Panduan teknis lengkap: [PANDUAN_WEBSITE_DATA_ALAT.md](PANDUAN_WEBSITE_DATA_ALAT.md).
