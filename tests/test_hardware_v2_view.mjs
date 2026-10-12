import test from 'node:test'
import assert from 'node:assert/strict'
import {
  analysisStatus, canonicalSlot, getRoleFromClaims, historyRows, latestNodes,
  nodeMeasurement,
} from '../src/services/hardwareV2View.js'

const slot = 1791724500000
const sample = (node, changes = {}) => ({
  schema_version: 2, node_id: node, sample_id: node + '_1791724501000_3',
  timestamp: slot + 1000, sequence: 3, ph: 7.2, tds: 240,
  turbidity: 16, quality_flags: [], ...changes,
})
const record = (changes = {}) => ({
  N0: sample('N0'), N1: sample('N1'), N2: sample('N2'), ...changes,
})

test('role claims strictly permit only the three expected research roles', () => {
  assert.equal(getRoleFromClaims({ tasnim_role: 'viewer' }), 'viewer')
  assert.equal(getRoleFromClaims({ tasnim_role: 'admin' }), 'admin')
  assert.equal(getRoleFromClaims({ tasnim_role: 'manager' }), 'manager')
  assert.equal(getRoleFromClaims({ tasnim_role: 'esp32' }), null)
  assert.equal(getRoleFromClaims({ role: 'admin' }), null)
  assert.equal(getRoleFromClaims(null), null)
})

test('missing RTDB empty flags remains valid and original acquisition time preserved', () => {
  const raw = sample('N0')
  delete raw.quality_flags
  const out = nodeMeasurement(raw, 'N0')
  assert.equal(out.timestamp, slot + 1000)
  assert.equal(out.ph, 7.2)
  assert.deepEqual(out.flags, [])
  assert.equal(canonicalSlot(out.timestamp), slot)
  assert.equal(raw.quality_flags, undefined)
})

test('bad or flagged sensor values are never converted to fake zeros', () => {
  assert.equal(nodeMeasurement(sample('N0', { ph: null }), 'N0').ph, null)
  assert.equal(nodeMeasurement(sample('N0', { ph: -1 }), 'N0').ph, null)
  assert.equal(nodeMeasurement(sample('N0', { tds: 6000 }), 'N0').tds, null)
  assert.equal(nodeMeasurement(sample('N0', { turbidity: 3000 }), 'N0').turbidity, null)
  const flagged = nodeMeasurement(sample('N0', { quality_flags: ['PH_INVALID'] }), 'N0')
  assert.equal(flagged.requiresReview, true)
  assert.equal(flagged.ph, null)
  assert.equal(flagged.tds, null)
  assert.equal(nodeMeasurement(sample('N0', { quality_flags: { fake: true } }), 'N0'), null)
})

test('wrong node, missing metadata, bad clock or invalid sequence do not render', () => {
  assert.equal(nodeMeasurement(sample('N1'), 'N0'), null)
  assert.equal(nodeMeasurement(sample('N0', { timestamp: 170 }), 'N0'), null)
  assert.equal(nodeMeasurement(sample('N0', { sequence: -1 }), 'N0'), null)
  assert.equal(nodeMeasurement(sample('N0', { schema_version: 1 }), 'N0'), null)
  assert.equal(nodeMeasurement(sample('N0', { sample_id: 'N1_bad' }), 'N0'), null)
})

test('history separates complete slots, missing nodes and AI metadata', () => {
  const history = {
    [slot + 300000]: record({ N1: undefined }),
    [slot]: { ...record(), analysis: { status: 'NORMAL' } },
    broken: record(),
  }
  const out = historyRows(history)
  assert.equal(out.length, 2)
  assert.equal(out[0].complete, true)
  assert.equal(out[0].hasAnalysis, true)
  assert.equal(out[1].complete, false)
  assert.equal(out[1].nodes.N1, null)
})

test('only matching, structurally complete latest slot can claim AI sync', () => {
  const rows = historyRows({ [slot]: record() })
  const analysis = {
    source_timestamp_ms: slot, data_source: 'HARDWARE_TEST',
    model_stage: 'PROTOTYPE_SIMULATION', status: 'NORMAL',
    model_version: 'prototype-v1', session_id: 'DEMO_TEST',
    model_disagreement: false,
  }
  assert.equal(analysisStatus(analysis, rows).state, 'SLOT_ALIGNED_UNVERIFIED')
  assert.equal(analysisStatus({ ...analysis, source_timestamp_ms: slot + 300000 }, rows).state, 'STALE_OR_INCOMPLETE')
  assert.equal(analysisStatus({ ...analysis, model_stage: 'FIELD_VALIDATED' }, rows).state, 'UNTRUSTED_ANALYSIS')
  assert.equal(analysisStatus(analysis, historyRows({ [slot]: record({ N2: null }) })).state, 'STALE_OR_INCOMPLETE')
})

test('AI result with missing version/session or invalid disagreement is never shown as verified', () => {
  const rows = historyRows({ [slot]: record() })
  const valid = {
    source_timestamp_ms: slot, data_source: 'HARDWARE_TEST',
    model_stage: 'PROTOTYPE_SIMULATION', status: 'NORMAL',
    model_version: 'v1', session_id: 'S1', model_disagreement: false,
  }
  assert.equal(analysisStatus({ ...valid, model_version: '' }, rows).state, 'UNTRUSTED_ANALYSIS')
  assert.equal(analysisStatus({ ...valid, session_id: '' }, rows).state, 'UNTRUSTED_ANALYSIS')
  assert.equal(analysisStatus({ ...valid, model_disagreement: 'false' }, rows).state, 'UNTRUSTED_ANALYSIS')
  assert.equal(analysisStatus({ ...valid, status: 'OTHER' }, rows).state, 'UNTRUSTED_ANALYSIS')
})

test('latest node converter never imports an analysis record as a sensor', () => {
  const results = latestNodes({
    N0: { latest: sample('N0') }, N1: { latest: sample('N2') },
    N2: { latest: { analysis: 'not a sensor' } },
  })
  assert.equal(results.N0.node_id, 'N0')
  assert.equal(results.N1, null)
  assert.equal(results.N2, null)
})
