"""End-to-end transaction tests on demo RTDB emulator only.

Never uses service-account keys or a production URL. Requires explicit
FIREBASE_DATABASE_EMULATOR_HOST and GCLOUD_PROJECT guards.
"""
import os
import unittest

import firebase_admin
from firebase_admin import db

from ai.check_ai_readiness import audit_slot
from ai.hardware_test_analysis_writer_v2 import (
    AnalysisConflict, AnalysisLatestConflict,
    prepare_analysis_record, commit_verified_analysis,
)

HOST = "127.0.0.1:19003"
PROJECT = "demo-tasnim-security"
URL = f"http://{HOST}/?ns={PROJECT}-default-rtdb"
SLOT = 1_791_724_500_000
STEP = 300_000


def observation(node, slot):
    return {"schema_version": 2, "node_id": node,
            "sample_id": f"{node}_{slot+1000}_1",
            "timestamp": slot+1000, "sequence": 1,
            "ph": 7.2, "tds": 230, "turbidity": 10.1}


def proposal(slot):
    return {
        "source_timestamp_ms": slot,
        "session_id": "DEMO_TEST_SESSION",
        "model_stage": "PROTOTYPE_SIMULATION",
        "data_source": "HARDWARE_TEST",
        "time_mode": "ACTUAL_TIMESTAMP",
        "status": "NORMAL",
        "location": None,
        "random_forest": {"prediction": "NORMAL", "confidence": 0.54},
        "isolation_forest": {"is_anomaly": True, "decision_score": -0.2},
        "dominant_zscore": {"node": "N0", "parameter": "tds", "zscore": -7.15},
        "model_disagreement": True,
        "interpretation": "MODEL_REVIEW_REQUIRED",
    }


def record(slot=SLOT, version="prototype-v1"):
    return prepare_analysis_record(
        proposal(slot), model_version=version,
        inference_timestamp_ms=SLOT + 90_000,
    )


class AppAdapter:
    def __init__(self, app):
        self.app = app

    def reference(self, path):
        return db.reference(path, app=self.app)


class FailLatestOnce:
    def __init__(self, adapter):
        self.adapter = adapter
        self.failed = False

    def reference(self, path):
        if path == "hardware_test/analysis/latest" and not self.failed:
            parent = self

            class Fault:
                def transaction(self, callback):
                    parent.failed = True
                    raise ConnectionError("injected failure between transactions")

            return Fault()
        return self.adapter.reference(path)


class RealAnalysisEmulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FIREBASE_DATABASE_EMULATOR_HOST") != HOST:
            raise RuntimeError("REFUSED: emulator host mismatch")
        if os.getenv("GCLOUD_PROJECT") != PROJECT:
            raise RuntimeError("REFUSED: demo project mismatch")
        cls.app = firebase_admin.initialize_app(
            options={"databaseURL": URL, "projectId": PROJECT, "httpTimeout": 15},
            name="tasnim-analysis-emulator-tests",
        )
        cls.adapter = AppAdapter(cls.app)
        print("\n[SAFE] AI writer connected to demo localhost only")

    @classmethod
    def tearDownClass(cls):
        firebase_admin.delete_app(cls.app)

    def setUp(self):
        db.reference("hardware_test", app=self.app).delete()
        for slot in (SLOT, SLOT+STEP):
            nodes = {node: observation(node, slot) for node in ("N0", "N1", "N2")}
            self.assertEqual(audit_slot(str(slot), nodes), [])
            db.reference(f"hardware_test/history/{slot}", app=self.app).set(nodes)

    def read(self, path):
        return db.reference(path, app=self.app).get()

    def test_01_first_write(self):
        r = record()
        result = commit_verified_analysis(self.adapter, r)
        self.assertEqual(result["latest"], "LATEST_CONFIRMED")
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/analysis"), r)
        self.assertEqual(self.read("hardware_test/analysis/latest"), r)

    def test_02_identical_retry(self):
        r = record()
        commit_verified_analysis(self.adapter, r)
        commit_verified_analysis(self.adapter, dict(r))
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/analysis"), r)

    def test_03_old_backfill_latest_monotonic(self):
        newer, older = record(SLOT+STEP), record(SLOT)
        commit_verified_analysis(self.adapter, newer)
        state = commit_verified_analysis(self.adapter, older)
        self.assertEqual(state["latest"], "OLDER_ANALYSIS_PRESERVED")
        self.assertEqual(self.read("hardware_test/analysis/latest"), newer)
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/analysis"), older)

    def test_04_same_slot_different_result_conflict(self):
        r = record()
        commit_verified_analysis(self.adapter, r)
        other = dict(r)
        other["status"] = "ANOMALI"
        with self.assertRaises(AnalysisConflict):
            commit_verified_analysis(self.adapter, other)
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/analysis"), r)

    def test_05_retry_after_partial_failure(self):
        r = record()
        adapter = FailLatestOnce(self.adapter)
        with self.assertRaises(ConnectionError):
            commit_verified_analysis(adapter, r)
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/analysis"), r)
        self.assertIsNone(self.read("hardware_test/analysis/latest"))
        commit_verified_analysis(self.adapter, r)
        self.assertEqual(self.read("hardware_test/analysis/latest"), r)

    def test_06_same_slot_latest_conflict(self):
        r = record()
        db.reference("hardware_test/analysis/latest", app=self.app).set({
            **r, "status": "ANOMALI",
        })
        with self.assertRaises(AnalysisLatestConflict):
            commit_verified_analysis(self.adapter, r)
        self.assertEqual(self.read("hardware_test/analysis/latest")["status"], "ANOMALI")

    def test_07_wrong_source_never_written(self):
        r = record()
        r["data_source"] = "SIMULATION"
        with self.assertRaises(ValueError):
            commit_verified_analysis(self.adapter, r)
        self.assertIsNone(self.read(f"hardware_test/history/{SLOT}/analysis"))

    def test_08_other_model_version_conflicts(self):
        commit_verified_analysis(self.adapter, record(version="prototype-v1"))
        with self.assertRaises(AnalysisConflict):
            commit_verified_analysis(self.adapter, record(version="prototype-v2"))

    def test_09_three_node_measurements_unchanged(self):
        before = self.read(f"hardware_test/history/{SLOT}/N0")
        commit_verified_analysis(self.adapter, record())
        self.assertEqual(self.read(f"hardware_test/history/{SLOT}/N0"), before)


if __name__ == "__main__":
    unittest.main()
