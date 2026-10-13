#!/usr/bin/env bash
# TAS[N]IM — jalankan workflow dari terminal Codespaces (tanpa tombol UI).
#
#   bash scripts/run_actions.sh live 3        # sesi live 3 jam
#   bash scripts/run_actions.sh impor         # impor CSV di data/sd (tulis)
#   bash scripts/run_actions.sh impor data/sd/2026-10-14 cek
#
# Berguna selama workflow belum ada di branch main (tombol Run workflow
# di GitHub baru muncul setelah workflow ada di main).
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH=$(git rev-parse --abbrev-ref HEAD)
GH=(env -u GITHUB_TOKEN -u GH_TOKEN gh)
"${GH[@]}" auth status -h github.com >/dev/null 2>&1 || "${GH[@]}" auth login -h github.com -p https -w -s repo,workflow
case "${1:-}" in
  live)
    "${GH[@]}" workflow run tasnim-sesi-live.yml --ref "$BRANCH" -f durasi_jam="${2:-3}" ;;
  impor)
    "${GH[@]}" workflow run tasnim-impor-csv.yml --ref "$BRANCH" -f folder="${2:-data/sd}" -f mode="${3:-tulis}" ;;
  hapus)
    echo "Untuk hapus data pakai langsung: python3 scripts/hapus_data.py --help"; exit 1 ;;
  *)
    echo "Pakai: bash scripts/run_actions.sh live <jam> | impor [folder] [tulis|cek]"; exit 1 ;;
esac
sleep 3
echo "[OK] Workflow dijalankan di branch $BRANCH. Pantau: github.com → Actions, atau:"
echo "     env -u GITHUB_TOKEN gh run watch"
