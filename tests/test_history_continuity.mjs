import test from 'node:test'
import assert from 'node:assert/strict'
import {
  historyRows, historyContinuity, hardwareReadiness, SLOT_MS,
} from '../src/services/hardwareV2View.js'
import { adaptEmulatorForLegacyDashboard } from '../src/services/demoLegacyAdapter.js'

const BASE = 1_791_724_500_000
const packet = (node, slot) => ({
  schema_version: 2, node_id: node,
  sample_id: node + '_' + (slot + 1000) + '_1',
  timestamp: slot + 1000, sequence: 1,
  ph: 7.1, tds: 210, turbidity: 11, quality_flags: [],
})
const complete = slot => Object.fromEntries(
  ['N0', 'N1', 'N2'].map(id => [id, packet(id, slot)]),
)

test('unordered arrivals show interior gaps only, never extrapolate outside observed range', () => {
  const source = {
    [BASE + 3*SLOT_MS]: complete(BASE + 3*SLOT_MS),
    [BASE]: complete(BASE),
  }
  const before = JSON.stringify(source)
  const rows = historyRows(source)
  const coverage = historyContinuity(rows)
  assert.deepEqual(rows.map(row => row.slot), [BASE, BASE + 3*SLOT_MS])
  assert.deepEqual(coverage, {
    observedSlots: 2, interiorGapSlots: 2,
    gapSegments: 1, spanSlots: 4,
  })
  assert.equal(JSON.stringify(source), before)
  assert.equal(historyContinuity(rows.slice(0, 1)).interiorGapSlots, 0)
})

test('backfilled slots restore coverage without creating fabricated sensor values', () => {
  const a = BASE
  const b = BASE + SLOT_MS
  const c = BASE + 2*SLOT_MS
  const history = { [a]: complete(a), [c]: complete(c) }
  assert.equal(historyContinuity(historyRows(history)).interiorGapSlots, 1)
  history[b] = { N0: packet('N0', b), N1: packet('N1', b) }
  const partlyBackfilled = historyRows(history)
  assert.equal(historyContinuity(partlyBackfilled).interiorGapSlots, 0)
  assert.equal(partlyBackfilled[1].complete, false)
  assert.equal(partlyBackfilled[1].nodes.N2, null)
  history[b].N2 = packet('N2', b)
  const restored = historyRows(history)
  const readiness = hardwareReadiness(null, restored, c + 60_000)
  assert.equal(readiness.interiorGapSlots, 0)
  assert.equal(readiness.incompleteSlots, 0)
  assert.equal(readiness.completeSlots, 3)
})

test('wrong-slot acquisition never fills an unobserved node and remains incomplete', () => {
  const source = {
    [BASE]: {
      N0: packet('N0', BASE),
      N1: packet('N1', BASE + SLOT_MS),
      N2: packet('N2', BASE),
    },
  }
  const rows = historyRows(source)
  assert.equal(rows[0].complete, false)
  assert.equal(rows[0].nodes.N1, null)
  assert.equal(historyContinuity(rows).interiorGapSlots, 0)
})

test('historic pre-2024 keys and malformed entries are excluded, not counted as more history', () => {
  const old = 1_609_459_200_000 // 2021-01-01, epoch-ms, canonical slot
  const source = {
    [old]: complete(old),
    [BASE]: complete(BASE),
    [BASE + SLOT_MS]: complete(BASE + SLOT_MS),
    bad: complete(BASE),
  }
  const rows = historyRows(source)
  assert.deepEqual(rows.map(row => row.slot), [BASE, BASE + SLOT_MS])
  const legacy = adaptEmulatorForLegacyDashboard({ history: source }, 2)
  assert.equal(legacy.history.length, 2)
  assert.equal(legacy.hasMoreHistory, false)
})

test('bounded history is not mistaken for a complete observation session', () => {
  const source = Object.fromEntries(
    [0,1,2,3,4,5].map(i =>
      [BASE + i*SLOT_MS, complete(BASE + i*SLOT_MS)],
    ),
  )
  // The visible recent two records are continuous, but this says nothing
  // about data from before the returned window.
  const visible = historyRows(source, 2)
  assert.equal(historyContinuity(visible).interiorGapSlots, 0)
  assert.equal(historyContinuity(visible).observedSlots, 2)
  assert.equal(adaptEmulatorForLegacyDashboard({ history: source }, 2).hasMoreHistory, true)
})

test('missing input and malformed rows cannot cause an infinite gap or false incident', () => {
  assert.deepEqual(historyContinuity(null), {
    observedSlots: 0, interiorGapSlots: 0, gapSegments: 0, spanSlots: 0,
  })
  assert.equal(historyContinuity([
    { slot: BASE }, { slot: BASE }, { slot: BASE + 1 },
    { slot: NaN }, { slot: Infinity }, { slot: '1791724500000' },
  ]).observedSlots, 1)
  assert.equal(historyContinuity([
    { slot: BASE }, { slot: BASE + 1_000_000*SLOT_MS },
  ]).gapSegments, 1)
})
