"""Offline tests, no firebase_admin required and no network calls."""
import importlib.util
import unittest
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / 'iot' / 'real_test_bridge_v2.py'
spec = importlib.util.spec_from_file_location('bridge', BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
NOW = 1_791_526_000_000

class FakeRef:
    def __init__(self, store, key):
        self.store = store
        self.key = key
    def get(self):
        return self.store.get(self.key)
    def set(self, value):
        self.store[self.key] = value

class FakeDb:
    def __init__(self, store):
        self.store = store
    def reference(self, path):
        return FakeRef(self.store, path)

class BridgeTests(unittest.TestCase):
    def test_good_all_three(self):
        for n in bridge.NODES:
            p, s = bridge.normalize({'timestamp':NOW-1000,'ph':7.1,'tds':490,'turbidity':12,'sequence':3},n,NOW)
            self.assertEqual(s,'OK'); self.assertEqual(p['turbidity'],12)
            self.assertEqual(p['ph'],7.1)
    def test_bad_ph_and_saturated_turb_omitted_not_faked(self):
        p, s = bridge.normalize({'timestamp':NOW-1000,'ph':-50.9,'tds':0,'turbidity':3000},'N2',NOW)
        self.assertEqual(s,'OK')
        self.assertNotIn('ph',p); self.assertNotIn('turbidity',p)
        self.assertEqual(p['tds'],0)
        self.assertIn('PH_INVALID',p['quality_flags']); self.assertIn('TURB_SATURATED',p['quality_flags'])
    def test_stale_rejected(self):
        p, s = bridge.normalize({'timestamp':NOW-200000,'ph':7,'tds':500,'turbidity':1},'N0',NOW)
        self.assertIsNone(p); self.assertIn('STALE',s)
    def test_dry_run_never_writes(self):
        raw={'timestamp':NOW-1000,'ph':7.1,'tds':490,'turbidity':12}
        store={f'hardware_test/nodes/{n}/latest':dict(raw) for n in bridge.NODES}
        bridge.handle_cycle(FakeDb(store),write=False,last_seen={},now_ms=NOW)
        self.assertEqual(len(store),3)
    def test_write_only_separate_real_test_and_one_history_per_slot(self):
        raw={'timestamp':NOW-1000,'ph':7.1,'tds':490,'turbidity':12}
        store={f'hardware_test/nodes/{n}/latest':dict(raw) for n in bridge.NODES}
        last_seen={}
        db=FakeDb(store)
        s=bridge.handle_cycle(db,write=True,last_seen=last_seen,now_ms=NOW)
        self.assertEqual(s,{'updated':3,'history':3})
        self.assertTrue(all(k.startswith('hardware_test/') or k.startswith('real_test/') for k in store))
        for n in bridge.NODES:
            self.assertIn(f'real_test/nodes/{n}/latest',store)
            self.assertIn(f'real_test/history/{(NOW-1000)//300000*300000}/{n}',store)
        s=bridge.handle_cycle(db,write=True,last_seen=last_seen,now_ms=NOW)
        self.assertEqual(s,{'updated':0,'history':0})

if __name__=='__main__':
    unittest.main()
