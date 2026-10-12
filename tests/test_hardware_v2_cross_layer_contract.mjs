import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { nodeMeasurement, historyRows, latestNodes } from '../src/services/hardwareV2View.js'

const data = JSON.parse(readFileSync(new URL(
  './fixtures/hardware_v2_cross_layer_cases.json', import.meta.url,
), 'utf8'))

test('shared synthetic contract cases: web rejects malformed metadata and marks diagnostics for review', () => {
  assert.ok(data.cases.length >= 15)
  const names = new Set()
  for (const c of data.cases) {
    assert.ok(!names.has(c.name), 'duplicate fixture: ' + c.name)
    names.add(c.name)
    const node = nodeMeasurement(c.packet, 'N0')
    if (c.web === 'REJECT') {
      assert.equal(node, null, c.name)
    } else if (c.web === 'VALID') {
      assert.ok(node && !node.requiresReview, c.name)
      assert.ok(['ph', 'tds', 'turbidity'].every(key =>
        Number.isFinite(node[key]), c.name))
    } else if (c.web === 'REVIEW') {
      assert.equal(node?.requiresReview, true, c.name)
      assert.equal(c.backend === 'ACCEPT' || c.backend === 'REJECT', true)
    } else {
      assert.fail('unexpected web fixture state ' + c.web)
    }
  }
})

test('read-only dashboard uses same guard in latest and 5-minute history', () => {
  const bad = data.cases.find(c => c.name === 'malformed_sample_id').packet
  const good = data.cases.find(c => c.name === 'canonical_complete').packet
  const flagged = data.cases.find(c => c.name === 'missing_ph_flagged').packet
  const nodes = latestNodes({
    N0: { latest: good }, N1: { latest: { ...good, node_id: 'N1', sample_id: 'N1_good' } },
    N2: { latest: bad },
  })
  assert.equal(nodes.N0?.ph, 7.2)
  assert.equal(nodes.N1?.ph, 7.2)
  assert.equal(nodes.N2, null)
  const rows = historyRows({
    1791724500000: { N0: good, N1: bad, N2: flagged },
  })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].complete, false)
  assert.equal(rows[0].nodes.N1, null)
  assert.equal(rows[0].nodes.N2, null)
})

test('missing turbidity never becomes zero; suspect but well-formed packet remains a review', () => {
  const item = data.cases.find(c => c.name === 'missing_turb_flagged').packet
  const n = nodeMeasurement(item, 'N0')
  assert.equal(n.requiresReview, true)
  assert.equal(n.turbidity, null)
  assert.notEqual(n.turbidity, 0)
  assert.deepEqual(n.flags, ['TURB_INVALID_OR_MISSING'])
})
