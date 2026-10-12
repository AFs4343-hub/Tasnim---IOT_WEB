// Uses the EXACT shapes/timestamps seen in the three physical-node screenshots.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatFieldLatestNodes, fieldHistoryRows, readFieldNode, FIELD_SLOT_MS,
  selectFieldHardwareExport,
} from '../src/services/fieldHardwarePreview.js'
import { readFileSync } from 'node:fs'

const raw = {
  N0: { latest: { ph: 7.43, rssi: -52, sequence: 2, tds: 0,
    timestamp: 1791811802000, turbidity: 24 } },
  N1: { latest: { ph: 16.9, rssi: -53, sequence: 2, tds: 0,
    timestamp: 1791813601000, turbidity: 39.5 } },
  N2: { latest: { ph: 4.96, rssi: -53, sequence: 1, tds: 1890.8,
    timestamp: 1791813908000, turbidity: 0 } },
}

test('actual screenshots render all three nodes, invalid pH is not trusted', () => {
  const snapshot = structuredClone(raw)
  const nodes = formatFieldLatestNodes(snapshot)
  assert.equal(nodes.N0.ph, 7.43)
  assert.equal(nodes.N0.tds, 0)
  assert.ok(nodes.N0.qualityWarnings.includes('TDS_ZERO_CHECK_CLAMP'))
  assert.equal(nodes.N1.ph, null)
  assert.ok(nodes.N1.qualityWarnings.includes('PH_INVALID'))
  assert.equal(nodes.N1.turbidity, 39.5)
  assert.equal(nodes.N2.ph, 4.96)
  assert.ok(nodes.N2.qualityWarnings.includes('TURB_ZERO_VERIFY'))
  assert.equal(nodes.N2.tds, 1890.8)
  assert.deepEqual(raw, snapshot)
})

test('no Firebase history means no chart or exported history (no phantom slots)', () => {
  assert.deepEqual(fieldHistoryRows(null), [])
  assert.deepEqual(fieldHistoryRows(undefined), [])
  assert.deepEqual(fieldHistoryRows({}), [])
  // /nodes/latest alone does NOT automatically constitute /history.
  assert.deepEqual(fieldHistoryRows({ nodes: raw }), [])
})

test('as Firebase history slots appear, chart and table consume same records', () => {
  const s0 = Math.floor(raw.N0.latest.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS
  const s1 = Math.floor(raw.N1.latest.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS
  const s2 = Math.floor(raw.N2.latest.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS
  const history = {
    [s2]: { N2: raw.N2.latest },
    [s0]: { N0: raw.N0.latest },
    [s1]: { N1: raw.N1.latest },
    bogus: { N0: raw.N0.latest },
  }
  const rows = fieldHistoryRows(history)
  assert.deepEqual(rows.map(row => row.timestamp), [s0, s1, s2])
  assert.equal(rows[0].N0_ph, 7.43)
  assert.equal(rows[1].N1_ph, null)
  assert.equal(rows[1].N1_turbidity, 39.5)
  assert.equal(rows[2].N2_tds, 1890.8)
  assert.equal(rows[0].N2, null)
  assert.equal(rows[1].analysis, null)
  assert.deepEqual(fieldHistoryRows(history, 1).map(x => x.timestamp), [s2])
})

test('history timestamp mismatch, spoofed node ID and non-numeric values rejected', () => {
  const s0 = Math.floor(raw.N0.latest.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS
  const history = {
    [s0]: { N0: { ...raw.N0.latest, timestamp: raw.N0.latest.timestamp + FIELD_SLOT_MS },
      N1: { ...raw.N1.latest, node_id: 'N0' } },
  }
  const [row] = fieldHistoryRows(history)
  assert.equal(row.N0, null)
  assert.equal(row.N1, null)
  assert.equal(readFieldNode({ ...raw.N0.latest, ph: '7.43' }, 'N0').ph, null)
  assert.equal(readFieldNode({ ...raw.N0.latest, timestamp: 80 }, 'N0'), null)
})

test('real Firebase preview is explicitly development-only; default config remains simulation', () => {
  const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
  const entry = readFileSync(new URL('../src/main.jsx', import.meta.url), 'utf8')
  const cfg = JSON.parse(readFileSync(new URL('../tasnim.config.json', import.meta.url), 'utf8'))
  assert.equal(cfg.activeDataRoot, 'simulation')
  assert.match(source, /import\.meta\.env\.DEV/)
  assert.match(source, /VITE_TASNIM_FIELD_PREVIEW/)
  assert.match(source, /FIELD_PREVIEW \? 'hardware_test' : tasnimConfig\.activeDataRoot/)
  assert.match(entry, /fieldEnabled/)
  assert.match(entry, /FieldHardwarePreview/)
  const preview = readFileSync(new URL('../src/FieldHardwarePreview.jsx', import.meta.url), 'utf8')
  assert.match(preview, /<App fieldSnapshot=/)
  assert.match(preview, /Pilih ekspor JSON hardware_test/)
  assert.doesNotMatch(preview, /signInWithEmailAndPassword|onAuthStateChanged|type="password"/)
  assert.match(source, /fieldReadError/)
  assert.match(source, /hardware_test.*tanpa autentikasi/)
})


test('local Firebase Console export opens without login and never exposes private roots', () => {
  const rawHistory = {
    [Math.floor(raw.N0.latest.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS]:
      { N0: raw.N0.latest },
  }
  const exportFile = {
    hardware_test: {
      nodes: raw, history: rawHistory,
      analysis: { latest: { status: 'NOT_YET_ANALYZED' } },
      secret_branch: { token: 'MUST_NOT_SHOW' },
    },
    gateway_state: { nonces: { private: 'MUST_NOT_SHOW' } },
  }
  const selected = selectFieldHardwareExport(exportFile)
  assert.deepEqual(Object.keys(selected).sort(), ['analysis', 'history', 'nodes'])
  assert.deepEqual(Object.keys(selected.nodes).sort(), ['N0', 'N1', 'N2'])
  assert.equal(selected.nodes.N1.latest.ph, 16.9)
  assert.equal(fieldHistoryRows(selected.history).length, 1)
  assert.ok(!JSON.stringify(selected).includes('MUST_NOT_SHOW'))
  assert.equal(formatFieldLatestNodes(selected.nodes).N1.ph, null)
})

test('local JSON import rejects unrelated Firebase dumps and missing nodes', () => {
  for (const invalid of [null, {}, { hardware_test: { history: {} } },
    { gateway_state: { keys: 'secret' } }, [], 'invalid']) {
    assert.throws(() => selectFieldHardwareExport(invalid), /JSON harus berisi/)
  }
})

test('dashboard clearly differentiates local JSON, permission-denied and realtime', () => {
  const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
  const summary = readFileSync(new URL('../src/components/SystemOverview.jsx', import.meta.url), 'utf8')
  assert.match(app, /fieldSnapshot !== undefined/)
  assert.match(app, /setFirebaseStatus\('file'\)/)
  assert.match(summary, /Pratinjau JSON Lokal/)
  assert.match(app, /setFieldReadError/)
  assert.match(app, /tidak dapat dibaca/)
  assert.doesNotMatch(readFileSync(new URL('../src/FieldHardwarePreview.jsx', import.meta.url), 'utf8'),
    /set\(|push\(|update\(|remove\(/)
})
