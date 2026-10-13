"""Shared synthetic V2 backend/web contract fixtures.

This test is offline: no Firebase, credentials, firmware, model or network.
Tests what gateway ingestion accepts; read-side exceptions are documented
separately in the same fixture.
"""
import json
from pathlib import Path
import unittest

from iot.hardware_test_contract_v2 import ContractError
from iot.hardware_test_ingestion_core import check_ingestion_packet

FIXTURE = Path(__file__).resolve().parent / "fixtures/hardware_v2_cross_layer_cases.json"


class CrossLayerBackendContractTests(unittest.TestCase):
    def test_shared_cases_match_backend_ingestion(self):
        data = json.loads(FIXTURE.read_text())
        names = set()
        self.assertGreaterEqual(len(data["cases"]), 15)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                self.assertNotIn(case["name"], names)
                names.add(case["name"])
                if case["backend"] == "ACCEPT":
                    slot = check_ingestion_packet(
                        case["packet"], now_ms=data["assumed_now_ms"],
                    )
                    self.assertEqual(slot, 1791724500000)
                else:
                    self.assertEqual(case["backend"], "REJECT")
                    with self.assertRaises(ContractError):
                        check_ingestion_packet(
                            case["packet"], now_ms=data["assumed_now_ms"],
                        )

    def test_no_fixture_can_claim_field_validation(self):
        data = json.loads(FIXTURE.read_text())
        self.assertIn("synthetic", data["description"].lower())
        for case in data["cases"]:
            self.assertNotIn("FIELD_VALIDATED", str(case))
            self.assertNotIn("password", str(case).lower())


if __name__ == "__main__":
    unittest.main()
