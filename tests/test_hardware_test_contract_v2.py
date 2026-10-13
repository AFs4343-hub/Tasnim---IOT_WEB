"""Candidate V2 offline acceptance tests. No database/network calls."""
import unittest
from iot.hardware_test_contract_v2 import (
    ContractError, SLOT_MS, advance_latest_in_memory,
    store_history_in_memory, validate_measurement,
)
from ai.check_ai_readiness import audit_slot

TS = 1_791_724_501_000


def sample(node="N0", ts=TS, seq=3):
    return dict(schema_version=2, node_id=node,
                sample_id=f"{node}_{ts}_{seq}", timestamp=ts,
                sequence=seq, ph=7.1, tds=200.0,
                turbidity=12.5, rssi=-50, quality_flags=[])


class HardwareTestV2CandidateTests(unittest.TestCase):
    def test_valid_three_nodes_and_ai_ready(self):
        slot = TS // SLOT_MS * SLOT_MS
        record = {n: sample(n) for n in ("N0", "N1", "N2")}
        self.assertEqual([validate_measurement(p) for p in record.values()], [slot] * 3)
        self.assertEqual(audit_slot(str(slot), record), [])

    def test_invalid_ph_retained_for_storage_but_rejected_by_ai(self):
        p = sample("N2")
        p.pop("ph")
        p["quality_flags"] = ["PH_INVALID"]
        self.assertIsInstance(validate_measurement(p), int)
        slot = TS // SLOT_MS * SLOT_MS
        record = {n: sample(n) for n in ("N0", "N1", "N2")}
        record["N2"] = p
        self.assertTrue(audit_slot(str(slot), record))

    def test_invalid_negative_ph_must_be_omitted(self):
        p = sample(); p["ph"] = -29.34; p["quality_flags"] = ["PH_INVALID"]
        with self.assertRaises(ContractError): validate_measurement(p)

    def test_missing_sensor_must_have_flag(self):
        p = sample(); p.pop("tds")
        with self.assertRaises(ContractError): validate_measurement(p)

    def test_boolean_and_seconds_timestamp_rejected(self):
        for wrong in (True, 1791724501, float(TS)):
            with self.subTest(wrong=wrong):
                p = sample(); p["timestamp"] = wrong
                with self.assertRaises(ContractError): validate_measurement(p)

    def test_node_and_sample_id_must_match(self):
        p = sample(); p["sample_id"] = "N1_wrong"
        with self.assertRaises(ContractError): validate_measurement(p)

    def test_duplicate_replay_is_noop(self):
        store = {}; p = sample()
        self.assertEqual(store_history_in_memory(store, p), "INSERTED")
        self.assertEqual(store_history_in_memory(store, dict(p)), "DUPLICATE_NOOP")
        self.assertEqual(len(store), 1)

    def test_different_measurement_same_slot_is_conflict(self):
        store = {}; p = sample()
        self.assertEqual(store_history_in_memory(store, p), "INSERTED")
        other = sample(ts=TS + 3_000, seq=4)
        self.assertEqual(store_history_in_memory(store, other), "CONFLICT_NO_OVERWRITE")
        self.assertEqual(next(iter(store.values()))["sample_id"], p["sample_id"])

    def test_old_replay_cannot_replace_latest(self):
        store = {}; new = sample(ts=TS + 300_000, seq=9)
        self.assertEqual(advance_latest_in_memory(store, new), "UPDATED")
        self.assertEqual(advance_latest_in_memory(store, sample()), "OLDER_NOOP")
        self.assertEqual(store["hardware_test/nodes/N0/latest"]["timestamp"], new["timestamp"])

    def test_conflicting_same_timestamp_cannot_replace_latest(self):
        store = {}; p = sample()
        self.assertEqual(advance_latest_in_memory(store, p), "UPDATED")
        altered = dict(p); altered["ph"] = 8.2
        self.assertEqual(advance_latest_in_memory(store, altered), "CONFLICT_NO_OVERWRITE")
        self.assertEqual(store["hardware_test/nodes/N0/latest"]["ph"], 7.1)


if __name__ == "__main__":
    unittest.main()
