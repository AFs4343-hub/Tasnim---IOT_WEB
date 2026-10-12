"""Demo-only signed HTTP sender for ESP32 HMAC interoperability.

Signs the raw bytes from an existing measurement JSON file; never modifies
its contents. Does not contact any remote host unless --send-demo is given.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from iot.hardware_test_gateway_auth_v1 import signature_message
from iot.hardware_test_gateway_http_v1 import require_demo_environment

NODE_IDS = ("N0", "N1", "N2")


def sign_bytes(body, node, key, *, request_ts, nonce):
    if node not in NODE_IDS:
        raise ValueError("node:invalid")
    if type(body) is not bytes or not body or len(body) > 2048:
        raise ValueError("body:invalid")
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("key:invalid")
    stamp = str(request_ts)
    if not re.fullmatch(r"[1-9][0-9]{12}", stamp):
        raise ValueError("request_ts:invalid")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", nonce):
        raise ValueError("nonce:invalid")
    digest = hmac.new(key, signature_message(node, stamp, nonce, body),
                      hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Tasnim-Node": node,
        "X-Tasnim-Time": stamp,
        "X-Tasnim-Nonce": nonce,
        "X-Tasnim-Signature": digest,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True, choices=NODE_IDS)
    parser.add_argument("--packet", type=Path, required=True,
                        help="Existing JSON packet bytes, unchanged")
    parser.add_argument("--send-demo", action="store_true",
                        help="POST to 127.0.0.1:18080 only; never a remote host")
    args = parser.parse_args(argv)
    raw = args.packet.read_bytes()
    env_name = f"TASNIM_TEST_KEY_{args.node}_HEX"
    test_hex = os.environ.get(env_name, "")
    if not re.fullmatch(r"[a-fA-F0-9]{64,128}", test_hex):
        raise SystemExit("[STOP] 32+ byte synthetic demo key env required")
    key = bytes.fromhex(test_hex)
    headers = sign_bytes(raw, args.node, key,
                         request_ts=int(time.time()*1000),
                         nonce=secrets.token_urlsafe(18))
    print("Node:", args.node)
    print("Raw body SHA256:", hashlib.sha256(raw).hexdigest())
    print("Signature generated in memory; not printed")
    if not args.send_demo:
        print("[DRY-RUN] No network request sent")
        return
    require_demo_environment()
    req = Request("http://127.0.0.1:18080/v1/measurements",
                  data=raw, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=15) as response:
            status, payload = response.status, json.loads(response.read())
    except HTTPError as exc:
        status, payload = exc.code, json.loads(exc.read())
    print("Demo response HTTP:", status)
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
