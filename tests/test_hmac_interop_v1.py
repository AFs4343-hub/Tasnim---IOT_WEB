"""Frozen deterministic firmware HMAC test vector; no network/real keys."""
import unittest
from hashlib import sha256

from scripts.signed_gateway_demo_client import sign_bytes
from iot.hardware_test_gateway_auth_v1 import (
    DeviceAuthError, verify_device_request,
)

RAW = (
    b'{"node_id":"N0","ph":7.2,"quality_flags":[],"rssi":-49,'
    b'"sample_id":"N0_1791724501000_3","schema_version":2,'
    b'"sequence":3,"tds":240.0,"timestamp":1791724501000,'
    b'"turbidity":16.0}'
)
KEY = bytes.fromhex("11" * 32)
TS = 1791724501000
NONCE = "testnonce000000001"
EXPECTED_SIG = "e1fa88237d22368249922eea3858c8108dd25c8f4d36d93af561cec8e526f90a"
EXPECTED_BODY_SHA = "4fcf78a973145a359f81abe7aba81ced8d0fe997ebe196484abb28a1b971bb29"


class HmacFirmwareInteroperabilityTests(unittest.TestCase):
    def test_vector_signature_matches_arduino_contract(self):
        self.assertEqual(sha256(RAW).hexdigest(), EXPECTED_BODY_SHA)
        headers = sign_bytes(RAW, "N0", KEY,
                             request_ts=TS, nonce=NONCE)
        self.assertEqual(headers["X-Tasnim-Signature"], EXPECTED_SIG)

    def test_vector_is_verified_by_gateway(self):
        headers = sign_bytes(RAW, "N0", KEY,
                             request_ts=TS, nonce=NONCE)
        result = verify_device_request(RAW, headers, {"N0": KEY},
                                       now_ms=TS)
        self.assertEqual(result["packet"]["sample_id"], "N0_1791724501000_3")

    def test_changed_whitespace_invalidates_signature(self):
        headers = sign_bytes(RAW, "N0", KEY,
                             request_ts=TS, nonce=NONCE)
        with self.assertRaises(DeviceAuthError):
            verify_device_request(RAW + b"\n", headers, {"N0": KEY},
                                  now_ms=TS)

    def test_refuse_short_secret_for_signing(self):
        with self.assertRaises(ValueError):
            sign_bytes(RAW, "N0", b"demo", request_ts=TS, nonce=NONCE)


if __name__ == "__main__":
    unittest.main()
