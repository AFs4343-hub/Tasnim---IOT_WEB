#!/usr/bin/env python3
"""Setup proyek Firebase TAS[N]IM memakai service account (tanpa klik Console).

Langkah (masing-masing aman diulang):
1. Isi ``.env.local`` (VITE_FIREBASE_*) dari konfigurasi Web App proyek.
   Nilai yang sudah ada tidak ditimpa.
2. Aktifkan login **Anonymous** (agar website bisa membaca tanpa form login).
3. Opsional ``--apply-rules``: ubah HANYA ``hardware_test/.write`` di Rules
   LIVE menjadi ``auth != null && auth.provider != 'anonymous'``. Rules lama
   dicadangkan dulu ke ``backups/``. Ditolak jika Rules LIVE berbeda dari
   yang diharapkan.

Langkah yang gagal karena izin service account hanya dilaporkan, disertai
tautan Console untuk dilakukan manual. Tidak pernah mencetak kunci rahasia.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_URL = "https://omirisetmonitoring-default-rtdb.asia-southeast1.firebasedatabase.app"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/firebase",
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/userinfo.email",
]
ENV_KEYS = {
    "VITE_FIREBASE_API_KEY": "apiKey",
    "VITE_FIREBASE_AUTH_DOMAIN": "authDomain",
    "VITE_FIREBASE_DATABASE_URL": "databaseURL",
    "VITE_FIREBASE_PROJECT_ID": "projectId",
    "VITE_FIREBASE_STORAGE_BUCKET": "storageBucket",
    "VITE_FIREBASE_MESSAGING_SENDER_ID": "messagingSenderId",
    "VITE_FIREBASE_APP_ID": "appId",
}
OLD_WRITE = "auth != null"
NEW_WRITE = "auth != null && auth.provider != 'anonymous'"


class StepFailed(RuntimeError):
    pass


# ---------------------------------------------------------------- pure helpers

def read_env_file(path: Path) -> dict:
    values = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def merge_env_file(path: Path, web_config: dict) -> list:
    """Isi kunci VITE_FIREBASE_* yang kosong; baris lain dipertahankan."""
    existing = read_env_file(path)
    lines = path.read_text().splitlines() if path.is_file() else [
        "# Dibuat oleh scripts/firebase_project_setup.py — JANGAN di-commit"]
    filled = []
    for env_key, config_key in ENV_KEYS.items():
        value = str(web_config.get(config_key) or "").strip()
        if not value or existing.get(env_key):
            continue
        replaced = False
        for i, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == env_key:
                lines[i] = f"{env_key}={value}"
                replaced = True
        if not replaced:
            lines.append(f"{env_key}={value}")
        filled.append(env_key)
    if filled:
        path.write_text("\n".join(lines) + "\n")
    return filled


def tighten_rules(rules_text: str) -> tuple[str, str]:
    """Return (status, new_text). status: CHANGED | ALREADY | UNEXPECTED."""
    try:
        rules = json.loads(rules_text)
    except json.JSONDecodeError:
        return "UNEXPECTED", rules_text
    section = rules.get("rules", {}).get("hardware_test") if isinstance(rules, dict) else None
    if not isinstance(section, dict):
        return "UNEXPECTED", rules_text
    if section.get(".write") == NEW_WRITE:
        return "ALREADY", rules_text
    if section.get(".write") != OLD_WRITE or section.get(".read") != "auth != null":
        return "UNEXPECTED", rules_text
    section[".write"] = NEW_WRITE
    return "CHANGED", json.dumps(rules, indent=2) + "\n"


# ---------------------------------------------------------------- HTTP

def access_token(key_path: Path) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def http(method, url, token, body=None, project=None):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    if project:
        request.add_header("x-goog-user-project", project)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise StepFailed(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise StepFailed(f"jaringan: {exc.reason}") from exc


# ---------------------------------------------------------------- steps

def step_env(token, project, env_path):
    apps = json.loads(http("GET", f"https://firebase.googleapis.com/v1beta1/projects/{project}/webApps",
                           token, project=project) or "{}").get("apps", [])
    if not apps:
        raise StepFailed("proyek belum punya Web App (Console → Project settings → Add app → Web)")
    app_id = apps[0]["appId"]
    config = json.loads(http("GET", f"https://firebase.googleapis.com/v1beta1/projects/{project}/webApps/{app_id}/config",
                             token, project=project))
    filled = merge_env_file(env_path, config)
    return f"{len(filled)} nilai diisi" if filled else "sudah lengkap"


def step_anonymous(token, project):
    url = f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/config"
    current = json.loads(http("GET", url, token, project=project))
    if current.get("signIn", {}).get("anonymous", {}).get("enabled"):
        return "sudah aktif"
    http("PATCH", url + "?updateMask=signIn.anonymous.enabled", token,
         {"signIn": {"anonymous": {"enabled": True}}}, project=project)
    return "diaktifkan"


def step_rules(token, db_url, assume_yes):
    url = f"{db_url.rstrip('/')}/.settings/rules.json"
    live = http("GET", url, token)
    status, new_text = tighten_rules(live)
    if status == "ALREADY":
        return "sudah aman"
    if status == "UNEXPECTED":
        raise StepFailed("Rules LIVE berbeda dari yang diharapkan; tidak diubah. "
                         "Ubah manual sesuai docs/PANDUAN_WEBSITE_DATA_ALAT.md langkah 1.3")
    backup = ROOT / "backups" / f"database.rules.live.{time.strftime('%Y%m%d_%H%M%S')}.json"
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(live)
    if not assume_yes:
        answer = input("Terapkan Rules aman (tamu anonim hanya baca)? ketik YA: ").strip()
        if answer != "YA":
            return f"dilewati (cadangan tetap di {backup.relative_to(ROOT)})"
    http("PUT", url, token, new_text.encode())
    return f"diterapkan; cadangan Rules lama: {backup.relative_to(ROOT)}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Setup Firebase TAS[N]IM via service account")
    parser.add_argument("--key", type=Path, default=ROOT / "iot/serviceAccountKey.json")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.local")
    parser.add_argument("--database-url", default=DEFAULT_DB_URL)
    parser.add_argument("--apply-rules", action="store_true")
    parser.add_argument("--yes", action="store_true", help="tidak bertanya konfirmasi Rules")
    args = parser.parse_args(argv)

    if not args.key.is_file():
        print(f"[LEWATI] Service account tidak ada: {args.key}")
        return 2
    project = json.loads(args.key.read_text()).get("project_id")
    console = f"https://console.firebase.google.com/project/{project}"
    try:
        token = access_token(args.key)
    except Exception as exc:  # kunci rusak / jam sistem salah
        print(f"[GAGAL] Tidak bisa login dengan service account: {type(exc).__name__}")
        return 1

    steps = [
        (".env.local", lambda: step_env(token, project, args.env_file),
         f"{console}/settings/general"),
        ("Login Anonymous", lambda: step_anonymous(token, project),
         f"{console}/authentication/providers"),
    ]
    if args.apply_rules:
        steps.append(("Rules hardware_test", lambda: step_rules(token, args.database_url, args.yes),
                      f"{console}/database"))
    failed = 0
    for name, run, manual in steps:
        try:
            print(f"[OK]    {name}: {run()}")
        except StepFailed as exc:
            failed += 1
            print(f"[MANUAL] {name}: {exc}\n         Lakukan manual di: {manual}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
