"""Loopback-only HTTP adapter for TASNIM signed ingestion — demo emulator ONLY.

NOT a production HTTP/TLS deployment. Requires demo-project, local emulator,
explicit opt-in, and local-only bind. Future HTTPS reverse proxy and secret
management must be reviewed separately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from iot.hardware_test_contract_v2 import ContractError
from iot.hardware_test_gateway_auth_v1 import (
    DeviceAuthError, NonceConflict, accept_signed_measurement,
)
from iot.hardware_test_ingestion_core import (
    HistoryConflict, LatestConflict, MAX_PAYLOAD_BYTES,
)

HOST = "127.0.0.1"
EMULATOR_HOST = "127.0.0.1:19003"
DEMO_PROJECT = "demo-tasnim-security"
POST_PATH = "/v1/measurements"


def ingest_response(db, body, headers, secrets, *, now_ms=None):
    """Return (HTTP status, JSON object). No request body or secrets in errors."""
    try:
        result = accept_signed_measurement(
            db, body, headers, secrets, now_ms=now_ms
        )
    except DeviceAuthError:
        return 401, {"ok": False, "code": "UNAUTHORIZED"}
    except ContractError:
        return 422, {"ok": False, "code": "INVALID_MEASUREMENT"}
    except (NonceConflict, HistoryConflict, LatestConflict):
        return 409, {"ok": False, "code": "CONFLICT_REVIEW_REQUIRED"}
    except Exception:
        # This is a prototype boundary; never return database exceptions.
        return 503, {"ok": False, "code": "RETRY_LATER"}

    return 200, {
        "ok": True,
        "code": "HISTORY_AND_LATEST_CONFIRMED",
        "node_id": result["node_id"],
        "slot_ms": result["slot"],
        "history": result["history"],
        "latest": result["latest"],
    }


def make_handler(db, secrets, *, clock_ms=None):
    """Create a handler with a trusted database adapter and secret mapping."""
    def now():
        return int(time.time() * 1000) if clock_ms is None else clock_ms()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "TASNIM-Gateway-Demo"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Do not log signatures, query strings or sensor values.
            return

        def respond(self, status, payload):
            body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_GET(self):
            if self.path == "/healthz":
                self.respond(200, {"ok": True, "service": "tasnim-gateway-demo"})
            else:
                self.respond(404, {"ok": False, "code": "NOT_FOUND"})

        def do_POST(self):
            parsed = urlsplit(self.path)
            if (parsed.path != POST_PATH or parsed.query or parsed.fragment):
                self.respond(404, {"ok": False, "code": "NOT_FOUND"})
                return

            # No chunked transfer, multiple CL headers, or ambiguous headers.
            headers = list(self.headers.raw_items())
            names = [key.lower() for key, _ in headers]
            if len(names) != len(set(names)) or "transfer-encoding" in names:
                self.respond(400, {"ok": False, "code": "INVALID_HEADERS"})
                return
            length = self.headers.get("Content-Length")
            if length is None:
                self.respond(411, {"ok": False, "code": "LENGTH_REQUIRED"})
                return
            if not re.fullmatch(r"[0-9]{1,8}", length):
                self.respond(400, {"ok": False, "code": "INVALID_LENGTH"})
                return
            count = int(length)
            if not 0 < count <= MAX_PAYLOAD_BYTES:
                self.respond(413, {"ok": False, "code": "PAYLOAD_TOO_LARGE"})
                return
            try:
                data = self.rfile.read(count)
            except (TimeoutError, OSError):
                self.respond(400, {"ok": False, "code": "BODY_INCOMPLETE"})
                return
            if len(data) != count:
                self.respond(400, {"ok": False, "code": "BODY_INCOMPLETE"})
                return
            status, result = ingest_response(
                db, data, dict(headers), secrets, now_ms=now()
            )
            self.respond(status, result)

    return Handler


def create_demo_server(db, secrets, *, port=0, clock_ms=None):
    """Testable localhost HTTP server. Cannot bind a public interface."""
    if type(port) is not int or port < 0 or port > 65535:
        raise ValueError("port:invalid")
    return ThreadingHTTPServer(
        (HOST, port), make_handler(db, secrets, clock_ms=clock_ms)
    )


def require_demo_environment():
    """Fail closed; never initialize production Firebase by fallback."""
    if os.getenv("TASNIM_GATEWAY_EMULATOR_ONLY") != "YES":
        raise RuntimeError("REFUSED: explicit demo-only opt-in missing")
    if os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != EMULATOR_HOST:
        raise RuntimeError("REFUSED: emulator host mismatch")
    if os.getenv("GCLOUD_PROJECT") != DEMO_PROJECT:
        raise RuntimeError("REFUSED: demo project mismatch")


def read_demo_secrets():
    """Local environment secrets only; never commit real node keys."""
    results = {}
    for node in ("N0", "N1", "N2"):
        raw = os.getenv(f"TASNIM_TEST_KEY_{node}_HEX", "")
        if not re.fullmatch(r"[0-9a-fA-F]{64,128}", raw) or len(raw) % 2:
            raise RuntimeError(f"REFUSED: missing/invalid demo key for {node}")
        results[node] = bytes.fromhex(raw)
    if len(set(results.values())) != 3:
        raise RuntimeError("REFUSED: each node requires a distinct demo secret")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASNIM localhost demo gateway")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args(argv)
    require_demo_environment()
    keys = read_demo_secrets()

    import firebase_admin
    from firebase_admin import db

    app = firebase_admin.initialize_app(
        options={
            "projectId": DEMO_PROJECT,
            "databaseURL": f"http://{EMULATOR_HOST}/?ns={DEMO_PROJECT}-default-rtdb",
            "httpTimeout": 10,
        },
        name="tasnim-demo-http-gateway",
    )

    class DatabaseAdapter:
        def reference(self, path):
            return db.reference(path, app=app)

    try:
        with create_demo_server(DatabaseAdapter(), keys, port=args.port) as server:
            print(f"[SAFE] TASNIM demo gateway listening at http://{HOST}:{server.server_port}")
            print("[SAFE] Firebase RTDB emulator ONLY — not internet exposed")
            server.serve_forever(poll_interval=0.2)
    finally:
        firebase_admin.delete_app(app)


if __name__ == "__main__":
    main()
