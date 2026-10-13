#!/usr/bin/env bash
# TAS[N]IM — simpan iot/serviceAccountKey.json sebagai secret GitHub Actions
# FIREBASE_SERVICE_ACCOUNT (dipakai workflow impor CSV & sesi live).
#
#   bash scripts/setup_github_actions.sh
#
# Isi kunci tidak pernah ditampilkan. Token bawaan Codespaces tidak boleh
# mengatur secret, jadi skrip meminta login GitHub sekali (kode di browser).
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="iot/serviceAccountKey.json"
if ! python3 -c "import json,sys; d=json.load(open('$KEY')); sys.exit(0 if d.get('type')=='service_account' else 1)" 2>/dev/null; then
  echo "[STOP] $KEY tidak ada / bukan service account. Jalankan dulu: bash scripts/setup_tasnim.sh"
  exit 1
fi
REPO=$(git remote get-url origin | sed -E 's#(https://github.com/|git@github.com:)##; s#\.git$##')
GH=(env -u GITHUB_TOKEN -u GH_TOKEN gh)
if ! "${GH[@]}" auth status -h github.com >/dev/null 2>&1; then
  echo "Login GitHub: pilih 'Login with a web browser', buka link, masukkan kode yang tampil."
  "${GH[@]}" auth login -h github.com -p https -w -s repo,workflow
fi
"${GH[@]}" secret set FIREBASE_SERVICE_ACCOUNT --repo "$REPO" < "$KEY"
echo "[OK] Secret FIREBASE_SERVICE_ACCOUNT tersimpan di $REPO (isi tidak ditampilkan)."
echo "Cek: github.com/$REPO → Settings → Secrets and variables → Actions."
