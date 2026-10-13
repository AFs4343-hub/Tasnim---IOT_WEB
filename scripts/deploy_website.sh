#!/usr/bin/env bash
# TAS[N]IM — pasang website ke Firebase Hosting (link tetap, buka dari HP/laptop).
#
#   bash scripts/deploy_website.sh
#
# - Memakai konfigurasi .env / .env.local yang SUDAH ADA. Skrip ini tidak
#   pernah membuat, mengganti, atau menghapus API key.
# - Menolak deploy jika konfigurasi Firebase belum lengkap, supaya website
#   online tidak jadi layar kosong.
# - Hanya Hosting (--only hosting): Rules database tidak disentuh.
# - Versi lama tetap bisa dikembalikan: Firebase Console → Hosting → Release history.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="omirisetmonitoring"

if command -v firebase >/dev/null 2>&1; then FB=(firebase); else FB=(npx -y firebase-tools@14); fi

echo "== 1/4 Cek konfigurasi website (.env / .env.local)"
missing=$(python3 - <<'PY'
import pathlib
vals = {}
for f in (".env", ".env.production", ".env.local", ".env.production.local"):
    p = pathlib.Path(f)
    if p.is_file():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    vals[k.strip()] = v.strip()
need = ["VITE_FIREBASE_API_KEY", "VITE_FIREBASE_AUTH_DOMAIN",
        "VITE_FIREBASE_DATABASE_URL", "VITE_FIREBASE_PROJECT_ID"]
print(" ".join(k for k in need if k not in vals))
if vals.get("VITE_FIREBASE_AUTH_EMULATOR_HOST"):
    print("VITE_FIREBASE_AUTH_EMULATOR_HOST(hapus-dulu)")
PY
)
if [[ -n "$missing" ]]; then
  echo "[STOP] Belum lengkap / tidak boleh ada: $missing"
  echo "       Jalankan: bash scripts/setup_tasnim.sh  (atau isi manual .env.local), lalu ulangi."
  exit 1
fi
echo "[OK] Konfigurasi lengkap (nilai tidak ditampilkan)"

echo "== 2/4 Build website"
npm install --no-audit --no-fund >/dev/null
npm run build >/dev/null
db_url=$(cat .env .env.production .env.local .env.production.local 2>/dev/null \
  | sed -n 's/^VITE_FIREBASE_DATABASE_URL=//p' | sed '/^[[:space:]]*$/d' | tail -1 || true)
if [[ -z "$db_url" ]] || ! grep -rqF "$db_url" dist/assets; then
  echo "[STOP] Hasil build tidak memuat konfigurasi Firebase; deploy dibatalkan."
  exit 1
fi
echo "[OK] Build siap di dist/"

echo "== 3/4 Login Firebase (akun Google pemilik proyek)"
if ! "${FB[@]}" login:list 2>/dev/null | grep -q "Logged in as"; then
  "${FB[@]}" login --no-localhost
fi

echo "== 4/4 Deploy ke Firebase Hosting"
echo "Website di https://$PROJECT.web.app akan diganti dengan versi ini."
echo "(Versi sebelumnya bisa dikembalikan di Firebase Console → Hosting → Release history.)"
read -r -p "Lanjutkan? ketik YA: " answer
if [[ "$answer" != "YA" ]]; then
  echo "Dibatalkan."
  exit 0
fi
"${FB[@]}" deploy --only hosting --project "$PROJECT" -m "TASNIM $(git rev-parse --short HEAD 2>/dev/null || echo manual)"

cat <<TXT

[SELESAI] Website online:
  https://$PROJECT.web.app
  https://$PROJECT.firebaseapp.com
Simpan link ini di HP. Ulangi skrip ini hanya jika kode website berubah.
TXT
