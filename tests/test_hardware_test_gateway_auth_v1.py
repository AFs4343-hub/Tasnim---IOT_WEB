"""HMAC gateway core tests: offline; synthetic secrets only; no HTTP/Firebase."""
import hashlib
import hmac
import json
import unittest

from iot.hardware_test_gateway_auth_v1 import (
    DeviceAuthError, NonceConflict, signature_message,
    verify_device_request, accept_signed_measurement,
)
from iot.hardware_test_contract_v2 import ContractError
from test_hardware_test_ingestion_core import FakeDB, sample, TS

NOW = TS + 3_600_000
KEYS = {"N0": b"A" * 32, "N1": b"B" * 32, "N2": b"C" * 32}


def signed(packet, *, node=None, nonce="testnonce000000001", stamp=NOW, secret=None):
    node = node or packet["node_id"]
    body = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    headers = headers_for(body, node=node, nonce=nonce, stamp=stamp, secret=secret)
    return body, headers


def headers_for(body, *, node="N0", nonce="testnonce000000001",
                stamp=NOW, secret=None):
    key = secret if secret is not None else KEYS[node]
    signature = hmac.new(
        key, signature_message(node, str(stamp), nonce, body),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Tasnim-Node": node,
        "X-Tasnim-Time": str(stamp),
        "X-Tasnim-Nonce": nonce,
        "X-Tasnim-Signature": signature,
    }


class GatewayAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()

    def receive(self, body, headers):
        return accept_signed_measurement(
            self.db, body, headers, KEYS, now_ms=NOW,
        )

    def test_valid_signed_packet_writes_history_and_latest(self):
        body, headers = signed(sample())
        result = self.receive(body, headers)
        self.assertEqual(result["history"], "CONFIRMED")
        self.assertEqual(len(self.db.values), 3)

    def test_same_request_nonce_retry_is_idempotent(self):
        body, headers = signed(sample())
        self.receive(body, headers)
        self.receive(body, headers)
        self.assertEqual(len(self.db.values), 3)

    def test_latest_failure_retries_same_nonce(self):
        body, headers = signed(sample())
        self.db.fail_once_path = "hardware_test/nodes/N0/latest"
        with self.assertRaises(ConnectionError):
            self.receive(body, headers)
        self.assertEqual(len(self.db.values), 2)
        result = self.receive(body, headers)
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")

    def test_changed_body_with_reused_nonce_rejected(self):
        body, headers = signed(sample())
        self.receive(body, headers)
        altered, other_headers = signed(sample(ph=8.2))
        with self.assertRaises(NonceConflict):
            self.receive(altered, other_headers)
        self.assertEqual(len(self.db.values), 3)

    def test_tampered_body_rejected_without_writes(self):
        body, headers = signed(sample())
        with self.assertRaises(DeviceAuthError):
            self.receive(body.replace(b"240.0", b"800.0"), headers)
        self.assertEqual(self.db.values, {})

    def test_other_nodes_secret_cannot_impersonate_n0(self):
        body, headers = signed(sample(), secret=KEYS["N1"])
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)
        self.assertEqual(self.db.values, {})

    def test_signed_node_header_cannot_override_packet_identity(self):
        body, headers = signed(sample(node="N1"), node="N0")
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)
        self.assertEqual(self.db.values, {})

    def test_expired_request_time_rejected(self):
        body, headers = signed(sample(), stamp=NOW - 600_000)
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)

    def test_future_request_time_rejected(self):
        body, headers = signed(sample(), stamp=NOW + 600_000)
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)

    def test_old_measurement_with_fresh_request_is_accepted(self):
        body, headers = signed(sample(ts=TS - 1_200_000, seq=2))
        result = self.receive(body, headers)
        self.assertEqual(result["history"], "CONFIRMED")

    def test_missing_or_short_device_secret_rejected(self):
        body, headers = signed(sample())
        with self.assertRaises(DeviceAuthError):
            verify_device_request(body, headers, {"N0": b"small"}, now_ms=NOW)

    def test_duplicate_json_keys_rejected(self):
        body = b'{"node_id":"N0","node_id":"N1"}'
        headers = headers_for(body)
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)

    def test_nonfinite_json_rejected(self):
        packet = sample()
        body = json.dumps({**packet, "tds": float("nan")}).encode()
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers_for(body))

    def test_unsigned_invalid_sensor_rejected_before_nonce_write(self):
        body, headers = signed(sample(ph=-5))
        with self.assertRaises(ContractError):
            self.receive(body, headers)
        self.assertEqual(self.db.values, {})

    def test_bad_nonce_format_rejected(self):
        body, headers = signed(sample(), nonce="short")
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)

    def test_missing_content_type_rejected(self):
        body, headers = signed(sample())
        del headers["Content-Type"]
        with self.assertRaises(DeviceAuthError):
            self.receive(body, headers)


if __name__ == "__main__":
    unittest.main()
