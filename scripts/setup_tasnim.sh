#!/usr/bin/env bash
# TAS[N]IM — setup sekali jalan untuk GitHub Codespaces.
#
#   bash scripts/setup_tasnim.sh            # siapkan semuanya
#   bash scripts/setup_tasnim.sh --run      # siapkan lalu langsung buka website
#
# Yang dilakukan:
#  1. npm install + pip install (website, perekam, AI)
#  2. Service account: dari Codespaces secret FIREBASE_SERVICE_ACCOUNT* bila ada
#  3. .env.local otomatis dari proyek Firebase (service account, atau login
#     Firebase CLI sebagai cadangan)
#  4. Aktifkan login Anonymous; tawarkan Rules aman (perlu ketik YA)
#  5. Siapkan model AI prototipe bila belum ada
# Aman diulang. Tidak meng-commit atau mencetak kunci rahasia.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PROJECT="omirisetmonitoring"
KEY="iot/serviceAccountKey.json"
ENV_FILE=".env.local"
RUN_AFTER=0
[[ "${1:-}" == "--run" ]] && RUN_AFTER=1

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m[OK]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[PERLU]\033[0m %s\n' "$*"; }

step "1/5 Dependensi website & Python"
npm install --no-audit --no-fund >/dev/null && ok "npm install" || warn "npm install gagal"
python3 -m pip install -q -r ai/requirements.txt 2>/dev/null && ok "pip install" || warn "pip install gagal"

step "2/5 Service account Firebase"
if [[ ! -f "$KEY" ]]; then
  for var in $(compgen -e | grep -E '^FIREBASE_SERVICE_ACCOUNT' || true); do
    if printf '%s' "${!var}" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("type")=="service_account"' 2>/dev/null; then
      printf '%s' "${!var}" > "$KEY" && chmod 600 "$KEY"
      ok "diambil dari secret \$$var → $KEY"
      break
    fi
  done
fi
if [[ -f "$KEY" ]]; then
  ok "$KEY tersedia (di-.gitignore)"
else
  warn "Belum ada $KEY. Perekam history & AI butuh file ini."
  echo "       Firebase Console → Project settings → Service accounts → Generate new private key,"
  echo "       lalu upload/ubah nama menjadi $KEY (atau simpan isinya sebagai Codespaces secret"
  echo "       FIREBASE_SERVICE_ACCOUNT dan jalankan skrip ini lagi)."
fi

step "3/5 Konfigurasi website (.env.local) + 4/5 Login Anonymous & Rules"
if [[ -f "$KEY" ]]; then
  python3 scripts/firebase_project_setup.py --apply-rules
fi
missing=$(python3 - "$ENV_FILE" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); vals = {}
for f in (pathlib.Path(".env"), p):
    if f.is_file():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip(): vals[k.strip()] = v.strip()
need = ["VITE_FIREBASE_API_KEY", "VITE_FIREBASE_DATABASE_URL", "VITE_FIREBASE_PROJECT_ID"]
print(" ".join(k for k in need if k not in vals))
PY
)
if [[ -n "$missing" ]]; then
  warn "Masih kosong: $missing — mencoba lewat login Firebase CLI"
  FB="npx -y firebase-tools@14"
  $FB login:list 2>/dev/null | grep -q "Logged in as" || $FB login --no-localhost
  json=$($FB apps:sdkconfig WEB --project "$PROJECT" --json 2>/dev/null || true)
  python3 - "$ENV_FILE" "$json" <<'PY'
import json, sys, pathlib
sys.path.insert(0, "scripts")
from firebase_project_setup import merge_env_file
try:
    result = json.loads(sys.argv[2]).get("result", {})
    cfg = result.get("sdkConfig") or json.loads(result.get("fileContents", "{}"))
except Exception:
    cfg = {}
if cfg:
    print("[OK] .env.local:", ", ".join(merge_env_file(pathlib.Path(sys.argv[1]), cfg)) or "sudah lengkap")
else:
    print("[PERLU] Tidak bisa mengambil konfigurasi web. Salin manual dari Firebase Console →")
    print("        Project settings → Your apps → SDK setup and configuration → Config, ke .env.local")
PY
else
  ok ".env / .env.local lengkap"
fi
echo "       Jika langkah Anonymous ditandai [MANUAL]: buka"
echo "       https://console.firebase.google.com/project/$PROJECT/authentication/providers → Anonymous → Enable"

step "5/5 Model AI prototipe"
if [[ -f ai/models/tasnim_ai_bundle.joblib ]]; then
  ok "model sudah ada"
else
  python3 -m ai.generate_data >/dev/null && python3 -m ai.train_models >/dev/null \
    && ok "model dilatih (prototipe dari data simulasi)" || warn "gagal melatih model"
fi

step "Selesai"
cat <<'TXT'
Buka website     : npm run dev -- --host 0.0.0.0   → tab PORTS → port 5173 (ikon globe)
Rekam data alat  : python3 scripts/run_hardware_test_stack.py --write
Impor CSV SD     : python3 scripts/import_sd_csv.py tasnim_N0.csv tasnim_N1.csv tasnim_N2.csv --write
                   python3 -m ai.realtime_inference --root hardware_test --once
Panduan          : docs/PANDUAN_WEBSITE_DATA_ALAT.md
PENTING: jika npm run dev sedang berjalan, hentikan (Ctrl+C) lalu jalankan lagi agar .env.local terbaca.
TXT
if [[ $RUN_AFTER == 1 ]]; then
  exec npm run dev -- --host 0.0.0.0
fi
