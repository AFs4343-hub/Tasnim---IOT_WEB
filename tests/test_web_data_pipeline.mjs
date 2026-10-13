// Website data pipeline: microSD CSV → dashboard rows, data-source choice,
// IoT transmission metrics, node coordinates and WITA formatting.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  parseSdCsv, parseTimestamp, readingsToHardwareSnapshot, loadLocalHardwareFiles,
  nodeFromFileName,
} from '../src/services/sdCsv.js'
import { fieldHistoryRows, formatFieldLatestNodes } from '../src/services/fieldHardwarePreview.js'
import {
  resolveInitialDataSource, SOURCE_HARDWARE, SOURCE_SIMULATION,
} from '../src/services/dataSource.js'
import { computeTransmissionStats } from '../src/services/iotMetrics.js'
import { parseNodeCoords, resolveNodeCoords } from '../src/services/nodeCoordinates.js'
import { witaDateTime, witaDayKey, witaDayStartMs, witaTime } from '../src/services/timeFormat.js'

const fixture = name => ({
  name,
  size: 1000,
  text: async () => readFileSync(new URL(`./fixtures/sd_csv/${name}`, import.meta.url), 'utf8'),
})
const SLOT = 1791811800000

test('firmware microSD CSV becomes first-per-slot history without fake zeros', async () => {
  const snapshot = await loadLocalHardwareFiles(
    ['tasnim_N0.csv', 'tasnim_N1.csv', 'tasnim_N2.csv'].map(fixture))
  assert.equal(snapshot.stats.rows, 19)
  assert.equal(snapshot.stats.slots, 6)
  assert.equal(snapshot.stats.extraInSlot, 1)
  const rows = fieldHistoryRows(snapshot.history)
  assert.equal(rows.length, 6)
  assert.equal(rows[0].timestamp, SLOT)
  assert.equal(rows[0].N0.sequence, 1)
  assert.ok(rows.every(row => row.N0 && row.N1 && row.N2))
  const naRow = rows.find(row => row.N1_turbidity === null)
  assert.ok(naRow, 'NA turbidity stays missing')
  assert.equal(naRow.N1_ph, 7.15)
  const latest = formatFieldLatestNodes(snapshot.nodes)
  assert.equal(latest.N0.sequence, 7)
  assert.deepEqual(snapshot.fileNames, ['tasnim_N0.csv', 'tasnim_N1.csv', 'tasnim_N2.csv'])
})

test('CSV variants: semicolon/decimal comma, WITA date text, epoch seconds, bad rows', () => {
  const { readings } = parseSdCsv('waktu;pH;TDS (ppm);Turbidity\n2026-10-12 08:30:00;7,10;1.890,8;NA\n',
    { fileName: 'log_n2.csv' })
  assert.equal(readings[0].node, 'N2')
  assert.equal(readings[0].ph, 7.1)
  assert.equal(readings[0].tds, 1890.8)
  assert.equal(readings[0].turbidity, undefined)
  assert.equal(readings[0].timestamp, Date.UTC(2026, 9, 12, 0, 30))
  assert.equal(parseTimestamp('1791811802'), 1791811802000)
  assert.equal(parseTimestamp('80'), null)
  assert.equal(nodeFromFileName('tasnim_N1.csv'), 'N1')
  assert.equal(nodeFromFileName('N10.csv'), null)
  const bad = parseSdCsv('timestamp,node,ph\nxx,N0,7\n1791811802000,N9,7\n1791811802000,,7\n',
    { fileName: 'mixed.csv' })
  assert.deepEqual(bad.skipped.map(s => s.reason), ['TIMESTAMP_INVALID', 'NODE_INVALID', 'NODE_UNKNOWN'])
  assert.throws(() => parseSdCsv('ph,tds\n7,1\n'), /kolom timestamp/)
})

test('JSON export and CSV can be combined without overwriting stored slots', async () => {
  const stored = { timestamp: SLOT + 1, ph: 6.5, tds: 1, turbidity: 1, sequence: 99 }
  const json = {
    name: 'hardware_test.json', size: 100,
    text: async () => JSON.stringify({ hardware_test: {
      nodes: { N0: { latest: stored } }, history: { [SLOT]: { N0: stored } },
    } }),
  }
  const snapshot = await loadLocalHardwareFiles([json, fixture('tasnim_N0.csv')])
  assert.equal(snapshot.history[SLOT].N0.sequence, 99)
  assert.equal(snapshot.nodes.N0.latest.sequence, 7)
  await assert.rejects(loadLocalHardwareFiles([{ name: 'x.xlsx', size: 1, text: async () => '' }]),
    /hanya file/)
  await assert.rejects(loadLocalHardwareFiles([]), /Tidak ada file/)
})

test('snapshot builder keeps latest per node by time', () => {
  const snap = readingsToHardwareSnapshot([
    { node: 'N1', timestamp: SLOT + 400_000, sequence: 2, ph: 7.2 },
    { node: 'N1', timestamp: SLOT + 1000, sequence: 1, ph: 7.1 },
  ])
  assert.equal(snap.nodes.N1.latest.sequence, 2)
  assert.equal(snap.nodes.N0.latest, null)
  assert.deepEqual(Object.keys(snap.history), [String(SLOT), String(SLOT + 300_000)])
})

test('data source: stored choice > env > legacy flag > hardware_test default', () => {
  assert.equal(resolveInitialDataSource(), SOURCE_HARDWARE)
  assert.equal(resolveInitialDataSource({ env: { VITE_TASNIM_DATA_SOURCE: 'simulation' } }), SOURCE_SIMULATION)
  assert.equal(resolveInitialDataSource({ env: { VITE_TASNIM_DATA_SOURCE: 'field' } }), SOURCE_HARDWARE)
  assert.equal(resolveInitialDataSource({
    env: { VITE_TASNIM_DATA_SOURCE: 'simulation' }, stored: 'hardware_test',
  }), SOURCE_HARDWARE)
  assert.equal(resolveInitialDataSource({ stored: 'garbage' }), SOURCE_HARDWARE)
})

test('transmission stats count missing slots inside sessions, not between sessions', () => {
  const point = { ph: 7, tds: 1, turbidity: 1 }
  const rows = [
    { timestamp: SLOT, N0: point, N1: point, N2: point },
    { timestamp: SLOT + 300_000, N0: point, N1: null, N2: point },
    // slot SLOT+600000 missing for all nodes (within session)
    { timestamp: SLOT + 900_000, N0: point, N1: point, N2: { ph: null, tds: null, turbidity: null } },
    // next day: new session, gap not counted
    { timestamp: SLOT + 86_400_000, N0: point, N1: point, N2: point },
  ]
  const stats = computeTransmissionStats(rows)
  assert.equal(stats.mode, 'SLOT_5_MIN')
  assert.equal(stats.sessions, 2)
  assert.equal(stats.expectedPerNode, 5)
  assert.deepEqual([stats.perNode.N0.received, stats.perNode.N1.received, stats.perNode.N2.received], [4, 3, 3])
  assert.equal(stats.totalExpected, 15)
  assert.equal(stats.completeSlots, 2)
  assert.ok(Math.abs(stats.lossPct - (5 / 15) * 100) < 1e-9)
  assert.equal(computeTransmissionStats([]), null)
  const sim = computeTransmissionStats([{ timestamp: 5, N0: point }, { timestamp: 10, N0: point }])
  assert.equal(sim.mode, 'RECORD')
  assert.equal(sim.expectedPerNode, 2)
})

test('node coordinates from env string or GPS fields', () => {
  const coords = parseNodeCoords('N0:0.5512,123.0601; N1 : -0.1,123 ;N2:999,1;bad')
  assert.deepEqual(coords, { N0: { lat: 0.5512, lng: 123.0601 }, N1: { lat: -0.1, lng: 123 } })
  assert.equal(resolveNodeCoords('N0', { latitude: 1, longitude: 2 }, coords).source, 'GPS alat')
  assert.equal(resolveNodeCoords('N1', {}, coords).lat, -0.1)
  assert.equal(resolveNodeCoords('N2', null, coords).lat, null)
})

test('times are rendered in WITA regardless of browser timezone', () => {
  // 2026-10-12 23:45 UTC = 13 Okt 07.45 WITA
  const ms = Date.UTC(2026, 9, 12, 23, 45)
  assert.equal(witaTime(ms), '07.45')
  assert.match(witaDateTime(ms), /^13 Okt, 07\.45\.00 WITA$/)
  assert.equal(witaDayKey(ms), '2026-10-13')
  assert.equal(witaDayStartMs('2026-10-13'), Date.UTC(2026, 9, 12, 16, 0))
  assert.equal(witaTime(null), '—')
})
