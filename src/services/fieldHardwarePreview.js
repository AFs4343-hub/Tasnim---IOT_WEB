// Read-only presenter for ACTUAL legacy ESP32 N0/N1/N2 Firebase snapshots.
// The deployed sensor firmware currently sends timestamp/sequence/sensor
// fields WITHOUT the V2 metadata. Do not invent history or predictions.
// This is separate from the strict canonical V2 test/AI contract.
export const FIELD_NODE_IDS = Object.freeze(['N0', 'N1', 'N2'])
export const FIELD_SLOT_MS = 300_000
const MIN_MS = 1_704_067_200_000
const LOCATIONS = Object.freeze({
  N0: 'Hulu / Baseline',
  N1: 'Cabang Irigasi 1',
  N2: 'Cabang Irigasi 2',
})
const VALID = {
  ph: n => n >= 0 && n <= 14,
  tds: n => n >= 0 && n <= 5000,
  turbidity: n => n >= 0 && n < 3000,
}
const number = n => typeof n === 'number' && Number.isFinite(n) ? n : null

export function readFieldNode(raw, node) {
  if (!FIELD_NODE_IDS.includes(node) || !raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const timestamp = raw.timestamp
  if (!Number.isSafeInteger(timestamp) || timestamp < MIN_MS ||
      (raw.node_id !== undefined && raw.node_id !== node) ||
      (raw.schema_version !== undefined && raw.schema_version !== 2)) return null
  const sequence = raw.sequence
  if (sequence !== undefined && (!Number.isSafeInteger(sequence) || sequence < 0)) return null
  const warnings = []
  const values = {}
  for (const [sensor, valid] of Object.entries(VALID)) {
    const value = number(raw[sensor])
    values[sensor] = value !== null && valid(value) ? value : null
    if (values[sensor] === null) warnings.push(sensor.toUpperCase() + '_INVALID')
    else if (sensor === 'tds' && value === 0) warnings.push('TDS_ZERO_CHECK_CLAMP')
    else if (sensor === 'turbidity' && value === 0) warnings.push('TURB_ZERO_VERIFY')
  }
  const rawFlags = Array.isArray(raw.quality_flags) ? raw.quality_flags : []
  if (raw.quality_flags !== undefined && !Array.isArray(raw.quality_flags)) return null
  // A flag requiring review must not be hidden even if the numeric range passes.
  const unknownFlags = rawFlags.filter(f => f !== 'BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED')
  if (unknownFlags.length) {
    warnings.push('QUALITY_FLAGS_REVIEW')
    for (const key of Object.keys(values)) values[key] = null
  }
  return {
    node, node_id: node, location: LOCATIONS[node], timestamp,
    lastSeen: timestamp, sequence: sequence ?? null,
    rssi: number(raw.rssi), hasData: true,
    qualityWarnings: warnings, verified: false,
    ...values,
  }
}

export function formatFieldLatestNodes(data) {
  const result = {}
  for (const node of FIELD_NODE_IDS) {
    const point = readFieldNode(data?.[node]?.latest, node)
    result[node] = point ?? {
      node, location: LOCATIONS[node],
      ph: null, tds: null, turbidity: null, timestamp: null,
      lastSeen: null, sequence: null, rssi: null, hasData: false,
      qualityWarnings: ['NO_VALID_DATA'], verified: false,
    }
  }
  return result
}

// Read actual persisted 5-min Firebase history. Never synthesize missing
// slots from /latest: those are separate measurements, not stored history.
export function fieldHistoryRows(rawHistory, limit = 60) {
  if (!rawHistory || typeof rawHistory !== 'object' || Array.isArray(rawHistory)) return []
  return Object.entries(rawHistory)
    .filter(([key, value]) => {
      const slot = Number(key)
      return String(slot) === key && Number.isSafeInteger(slot) &&
        slot >= MIN_MS && slot % FIELD_SLOT_MS === 0 &&
        value && typeof value === 'object' && !Array.isArray(value)
    })
    .sort(([a], [b]) => Number(a) - Number(b))
    .slice(-Math.max(1, Math.min(limit, 240)))
    .map(([key, source]) => {
      const slot = Number(key)
      const row = {
        timestamp: slot,
        time: new Date(slot).toLocaleTimeString('id-ID', {
          hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Makassar',
        }),
        analysis: null, meta: {
          data_source: 'HARDWARE_TEST', mode: 'FIELD_PREVIEW_UNVERIFIED',
        },
      }
      for (const node of FIELD_NODE_IDS) {
        const point = readFieldNode(source[node], node)
        const valid = point && Math.floor(point.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS === slot
        row[node] = valid ? point : null
        for (const sensor of Object.keys(VALID)) row[node + '_' + sensor] = valid ? point[sensor] : null
      }
      // Analysis displayed only if it is actually present; never infer AI.
      if (source.analysis && typeof source.analysis === 'object' &&
          source.analysis.model_stage === 'PROTOTYPE_SIMULATION' &&
          source.analysis.data_source === 'HARDWARE_TEST' &&
          source.analysis.source_timestamp_ms === slot) row.analysis = source.analysis
      return row
    })
}
