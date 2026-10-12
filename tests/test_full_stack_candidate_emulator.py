"""Single synthetic localhost integration through actual RTDB transactions.

Signed HTTP -> immutable N0/N1/N2 history -> guarded AI Supervisor ->
archived checkpoint/last pointer -> private audit and browser status mirror.
The next Node.js test checks the actual authenticated Vite demo reader.
No production credentials, LIVE URLs, firmware or trained model.
"""
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import firebase_admin
from firebase_admin import db

from ai.hardware_test_supervisor_v1 import run_supervised_emulator_cycle
from ai.hardware_test_supervisor_audit_v1 import AUDIT_PATH, verify_supervisor_audit
from ai.hardware_test_supervisor_status_v1 import STATUS_PATH
from ai.hardware_test_supervisor_feed_v1 import FEED_PATH
from ai.hardware_test_checkpoint_integrity_v1 import inspect_demo_checkpoints
from iot.hardware_test_gateway_http_v1 import create_demo_server
from test_hardware_test_gateway_auth_v1 import KEYS, NOW, signed
from test_hardware_test_ingestion_core import TS, sample
from test_hardware_test_worker_v2 import prediction

HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"
SLOT = (TS // 300_000) * 300_000


class AppAdapter:
    emulator_only = True
    emulator_project = PROJECT
    emulator_host = HOST

    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


class FullStackCandidateEmulatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            os.getenv("GCLOUD_PROJECT") != PROJECT
            or os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST
            or os.getenv("FIREBASE_AUTH_EMULATOR_HOST") != "127.0.0.1:19004"
            or os.getenv("TASNIM_AUTH_TEST_EMULATOR_ONLY") != "YES"
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        ):
            raise RuntimeError("REFUSED: full-stack test requires only local demo Emulators")
        cls.app = firebase_admin.initialize_app(
            options={"projectId": PROJECT, "databaseURL": URL, "httpTimeout": 12},
            name="tasnim-full-stack-acceptance",
        )
        cls.adapter = AppAdapter(cls.app)

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def read(self, path):
        return self.adapter.reference(path).get()

    def test_signed_gateway_to_supervisor_complete_emulator_pipeline(self):
        # Run last, after other emulator suites have reset this demo root.
        self.adapter.reference("hardware_test").delete()
        self.adapter.reference("gateway_state").delete()
        self.adapter.reference("worker_state/ai_v2_supervisor").delete()
        self.adapter.reference("worker_state/ai_v2_exclusive").delete()

        with patch.dict(os.environ, {
            "TASNIM_GATEWAY_EMULATOR_ONLY": "YES",
            "TASNIM_AI_WORKER_EMULATOR_ONLY": "YES",
            "TASNIM_AI_COORDINATION_EMULATOR_ONLY": "YES",
        }):
            server = create_demo_server(
                self.adapter, KEYS, port=0, clock_ms=lambda: NOW,
            )
            thread = threading.Thread(
                target=server.serve_forever, daemon=True,
            )
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/v1/measurements"
                sent = []
                for tick in range(3):
                    for index, node in enumerate(("N0", "N1", "N2")):
                        packet = sample(
                            node=node, ts=TS + tick * 300_000, seq=tick+1,
                            ph=7.1 + index*.1, tds=210 + tick*5,
                            turbidity=11 + index,
                        )
                        nonce = f"fullstacknonce{node}{tick:08d}"
                        body, headers = signed(packet, nonce=nonce, stamp=NOW)
                        request = Request(
                            url, data=body, headers=headers, method="POST",
                        )
                        with urlopen(request, timeout=10) as response:
                            ack = json.loads(response.read())
                            self.assertEqual(response.status, 200)
                            self.assertEqual(ack["history"], "CONFIRMED")
                        sent.append((body, headers))
                # Exactly identical HTTP retry does not add a second record.
                body, headers = sent[0]
                with urlopen(Request(
                    url, data=body, headers=headers, method="POST",
                ), timeout=10) as response:
                    self.assertEqual(response.status, 200)

                history = self.read("hardware_test/history")
                self.assertEqual(set(history), {
                    str(SLOT + tick*300_000) for tick in range(3)
                })
                for row in history.values():
                    self.assertEqual(set(row), {"N0", "N1", "N2"})
                self.assertEqual(len(self.read("gateway_state/nonces")), 3)

                report = run_supervised_emulator_cycle(
                    self.adapter, session_id="SYNTHETIC_FULL_STACK",
                    model_version="prototype-v1", model_bundle=None,
                    predict_fn=prediction, now_ms=NOW,
                    max_attempts=2, max_actions_per_cycle=3,
                )
                self.assertEqual(report["state"], "PROCESSED")
                self.assertEqual(report["processed_count"], 2)
                self.assertTrue(report["status_persisted"])
                self.assertTrue(report["feed_persisted"])
                self.assertTrue(report["audit_persisted"])
                latest = self.read("hardware_test/analysis/latest")
                self.assertEqual(latest["source_timestamp_ms"], SLOT+600_000)
                self.assertEqual(latest["model_stage"], "PROTOTYPE_SIMULATION")
                self.assertEqual(self.read(STATUS_PATH), self.read(FEED_PATH))
                self.assertEqual(
                    verify_supervisor_audit(self.read(AUDIT_PATH))[-1]["record"],
                    self.read(STATUS_PATH),
                )
                integrity = inspect_demo_checkpoints(
                    self.adapter, session_id="SYNTHETIC_FULL_STACK",
                    model_version="prototype-v1",
                )
                self.assertEqual(integrity["state"], "ALIGNED")
                self.assertEqual(integrity["archived_count"], 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
