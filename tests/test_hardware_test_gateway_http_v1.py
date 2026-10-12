"""Real localhost HTTP smoke tests. FakeDB only; zero Firebase connections."""
import http.client
import json
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from iot.hardware_test_gateway_http_v1 import (
    create_demo_server, read_demo_secrets, require_demo_environment,
)
from test_hardware_test_gateway_auth_v1 import KEYS, NOW, signed
from test_hardware_test_ingestion_core import FakeDB, sample


class DemoGatewayHTTPTests(unittest.TestCase):
    def setUp(self):
        self.demo_env = patch.dict("os.environ", {
            "TASNIM_GATEWAY_EMULATOR_ONLY": "YES",
            "FIREBASE_DATABASE_EMULATOR_HOST": "127.0.0.1:19003",
            "GCLOUD_PROJECT": "demo-tasnim-security",
        }, clear=True)
        self.demo_env.start()
        self.addCleanup(self.demo_env.stop)

        class FakeDemoAdapter(FakeDB):
            emulator_only = True
            emulator_project = "demo-tasnim-security"
            emulator_host = "127.0.0.1:19003"

        self.db = FakeDemoAdapter()
        self.server = create_demo_server(
            self.db, KEYS, port=0, clock_ms=lambda: NOW
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True,
        )
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path="/v1/measurements", *, body=None, headers=None,
                method="POST"):
        req = Request(
            self.base + path, data=body, headers=headers or {}, method=method,
        )
        try:
            with urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            finally:
                exc.close()

    def test_00_server_creation_refuses_live_like_adapter_before_bind(self):
        # Test direct create_demo_server callers, NOT only the CLI main.
        for kwargs in (
            {"emulator_only": False},
            {"emulator_project": "production"},
            {"emulator_host": "live-db.example.invalid"},
        ):
            class WrongAdapter:
                emulator_only = kwargs.get("emulator_only", True)
                emulator_project = kwargs.get("emulator_project", "demo-tasnim-security")
                emulator_host = kwargs.get("emulator_host", "127.0.0.1:19003")
                def reference(self, path):
                    self.fail("no database should be accessed")
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(RuntimeError, "REFUSED"):
                create_demo_server(WrongAdapter(), KEYS, port=0)

    def test_00_server_creation_refuses_bad_keys_before_bind(self):
        for keys in (
            {"N0": KEYS["N0"], "N1": KEYS["N0"], "N2": KEYS["N2"]},
            {"N0": b"short", "N1": KEYS["N1"], "N2": KEYS["N2"]},
            {"N0": KEYS["N0"], "N1": KEYS["N1"]},
        ):
            with self.subTest(keys=tuple(keys)), self.assertRaisesRegex(RuntimeError, "REFUSED"):
                create_demo_server(self.db, keys, port=0)

    def test_00_server_creation_refuses_wrong_env_and_service_account(self):
        for wrong in (
            {"GCLOUD_PROJECT": "production"},
            {"FIREBASE_DATABASE_EMULATOR_HOST": "db.example.invalid"},
            {"TASNIM_GATEWAY_EMULATOR_ONLY": "NO"},
            {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/prod.json"},
        ):
            with self.subTest(wrong=wrong), patch.dict("os.environ", wrong):
                with self.assertRaisesRegex(RuntimeError, "REFUSED"):
                    create_demo_server(self.db, KEYS, port=0)

    def test_01_health_and_unknown_path(self):
        status, result = self.request("/healthz", method="GET")
        self.assertEqual((status, result["ok"]), (200, True))
        self.assertEqual(self.request("/unknown", method="GET")[0], 404)

    def test_02_signed_measurement_ack_is_after_both_writes(self):
        body, headers = signed(sample())
        status, result = self.request(body=body, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(result["code"], "HISTORY_AND_LATEST_CONFIRMED")
        self.assertEqual(result["history"], "CONFIRMED")
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")
        self.assertEqual(len(self.db.values), 3)

    def test_03_replay_identical_signed_request(self):
        body, headers = signed(sample())
        first = self.request(body=body, headers=headers)
        second = self.request(body=body, headers=headers)
        self.assertEqual(first, second)
        self.assertEqual(len(self.db.values), 3)

    def test_04_wrong_node_secret_rejected(self):
        body, headers = signed(sample(), secret=KEYS["N1"])
        status, result = self.request(body=body, headers=headers)
        self.assertEqual((status, result["code"]), (401, "UNAUTHORIZED"))
        self.assertFalse(self.db.values)

    def test_05_conflicting_same_slot_returns_409(self):
        body, headers = signed(sample())
        self.assertEqual(self.request(body=body, headers=headers)[0], 200)
        conflicting, newer = signed(sample(ph=8.3), nonce="anothernonce0000001")
        status, result = self.request(body=conflicting, headers=newer)
        self.assertEqual((status, result["code"]), (409, "CONFLICT_REVIEW_REQUIRED"))

    def test_06_bad_packet_returns_422_without_nonce(self):
        body, headers = signed(sample(ph=-1))
        status, result = self.request(body=body, headers=headers)
        self.assertEqual((status, result["code"]), (422, "INVALID_MEASUREMENT"))
        self.assertFalse(self.db.values)

    def test_07_request_fails_503_then_same_signed_retry_200(self):
        body, headers = signed(sample())
        self.db.fail_once_path = "hardware_test/nodes/N0/latest"
        status, result = self.request(body=body, headers=headers)
        self.assertEqual((status, result["code"]), (503, "RETRY_LATER"))
        self.assertEqual(len(self.db.values), 2)
        self.assertEqual(self.request(body=body, headers=headers)[0], 200)

    def test_08_oversized_body_rejected_before_auth(self):
        body = b"x" * 2049
        status, result = self.request(body=body)
        self.assertEqual((status, result["code"]), (413, "PAYLOAD_TOO_LARGE"))
        self.assertFalse(self.db.values)

    def test_09_bad_json_signature_rejected_as_unauthorized(self):
        body, headers = signed(sample())
        status, result = self.request(body=body.replace(b"240.0", b"650.0"),
                                      headers=headers)
        self.assertEqual((status, result["code"]), (401, "UNAUTHORIZED"))

    def test_10_missing_content_length_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port,
                                          timeout=5)
        conn.putrequest("POST", "/v1/measurements")
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        resp = conn.getresponse()
        try:
            self.assertEqual(resp.status, 411)
            self.assertEqual(json.loads(resp.read())["code"], "LENGTH_REQUIRED")
        finally:
            conn.close()

    def test_11_duplicate_headers_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port,
                                          timeout=5)
        conn.putrequest("POST", "/v1/measurements")
        conn.putheader("Content-Length", "2")
        conn.putheader("X-Tasnim-Node", "N0")
        conn.putheader("X-Tasnim-Node", "N1")
        conn.endheaders(b"{}")
        resp = conn.getresponse()
        try:
            self.assertEqual(resp.status, 400)
            self.assertEqual(json.loads(resp.read())["code"], "INVALID_HEADERS")
        finally:
            conn.close()

    def test_12_http_path_with_query_rejected(self):
        body, headers = signed(sample())
        status, _ = self.request("/v1/measurements?debug=1",
                                  body=body, headers=headers)
        self.assertEqual(status, 404)
        self.assertEqual(self.db.values, {})

    def test_13_demo_guard_rejects_missing_environment(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                require_demo_environment()

    def test_15_partial_body_eof_rejected_without_database_write(self):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=6
        )
        try:
            conn.putrequest("POST", "/v1/measurements")
            conn.putheader("Content-Length", "10")
            conn.endheaders(b"{}")
            conn.sock.shutdown(socket.SHUT_WR)
            resp = conn.getresponse()
            self.assertEqual((resp.status, json.loads(resp.read())["code"]),
                             (400, "BODY_INCOMPLETE"))
            self.assertEqual(self.db.values, {})
        finally:
            conn.close()

    def test_16_stalled_partial_body_times_out_without_database_write(self):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=6
        )
        try:
            conn.putrequest("POST", "/v1/measurements")
            conn.putheader("Content-Length", "10")
            conn.endheaders(b"{")
            resp = conn.getresponse()
            self.assertEqual((resp.status, json.loads(resp.read())["code"]),
                             (400, "BODY_INCOMPLETE"))
            self.assertEqual(self.db.values, {})
        finally:
            conn.close()

    def test_17_expect_continue_is_not_accepted(self):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=6
        )
        try:
            conn.putrequest("POST", "/v1/measurements")
            conn.putheader("Content-Length", "2")
            conn.putheader("Expect", "100-continue")
            conn.endheaders()
            resp = conn.getresponse()
            self.assertEqual((resp.status, json.loads(resp.read())["code"]),
                             (417, "EXPECTATION_FAILED"))
            self.assertEqual(self.db.values, {})
        finally:
            conn.close()

    def test_14_demo_secrets_reject_duplicates(self):
        from unittest.mock import patch
        environment = {
            "TASNIM_TEST_KEY_N0_HEX": "11" * 32,
            "TASNIM_TEST_KEY_N1_HEX": "11" * 32,
            "TASNIM_TEST_KEY_N2_HEX": "33" * 32,
        }
        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaises(RuntimeError):
                read_demo_secrets()


if __name__ == "__main__":
    unittest.main()
