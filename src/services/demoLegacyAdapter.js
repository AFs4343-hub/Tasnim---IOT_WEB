// Presenter for the ORIGINAL TASNIM dashboard from emulator-only V2 records.
// No Firebase imports or writes; missing/invalid values stay null (never 0).
import { historyRows, latestNodes, NODE_IDS } from './hardwareV2View.js'

const locations = {
  N0: 'Hulu / Baseline',
  N1: 'Cabang Irigasi 1',
  N2: 'Cabang Irigasi 2',
}
const sensors = ['ph', 'tds', 'turbidity']

export function adaptEmulatorForLegacyDashboard(snapshot, limit = 60) {
  const latest = latestNodes(snapshot?.nodes)
  const nodes = {}
  for (const id of NODE_IDS) {
    const record = latest[id]
    nodes[id] = {
      node: id, location: locations[id],
      ph: record?.ph ?? null,
      tds: record?.tds ?? null,
      turbidity: record?.turbidity ?? null,
      timestamp: record?.timestamp ?? null,
      lastSeen: record?.timestamp ?? null,
      sequence: record?.sequence ?? null,
      rssi: record?.rssi ?? null,
      hasData: Boolean(record),
    }
  }

  const allValidKeys = Object.keys(snapshot?.history ?? {}).filter(key =>
    /^\d+$/.test(key) && Number.isSafeInteger(Number(key))
    && Number(key) > 0 && Number(key) % 300000 === 0
  )
  const orderedRows = historyRows(snapshot?.history, limit)
  const history = orderedRows.map(row => {
    const item = {
      timestamp: row.slot,
      time: new Date(row.slot).toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit',
      }),
      // Do NOT pretend synthetic browser demo has trusted AI predictions.
      analysis: null, meta: null,
    }
    for (const id of NODE_IDS) {
      item[id] = row.nodes[id]
      for (const field of sensors)
        item[id + '_' + field] = row.nodes[id]?.[field] ?? null
    }
    return item
  })

  return {
    nodes,
    history,
    hasMoreHistory: allValidKeys.length > orderedRows.length,
    // Prototype AI mock is deliberately withheld from the legacy
    // AnomalyPanel, which otherwise might claim a scientific RF decision.
    analysis: null,
    firebaseStatus: 'online',
  }
}
