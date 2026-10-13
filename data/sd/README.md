# Tempat CSV microSD

Upload file CSV dari kartu microSD ke folder ini (GitHub → folder `data/sd` →
**Add file → Upload files** → Commit). Boleh dibuat subfolder per sesi,
misalnya `data/sd/2026-10-14/`.

Nama file harus memuat `N0`, `N1` atau `N2` (contoh `tasnim_N0.csv`) jika
CSV tidak punya kolom `node`. Format firmware:
`timestamp,node,sequence,ph,tds,turbidity,rssi`.

Setelah upload, jalankan workflow **TASNIM impor CSV microSD + AI**
(lihat `docs/OPERASIONAL_HARIAN.md`). Repo ini private; file di sini juga
menjadi cadangan data mentah.
