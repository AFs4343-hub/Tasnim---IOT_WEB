// Candidate read-only presentation adapter for /hardware_test V2.
// Does not import Firebase, perform writes or infer sensor accuracy.
export const NODE_IDS = Object.freeze(['N0', 'N1', 'N2'])
export const DATA_ROOT = 'hardware_test'
export const SLOT_MS = 300_000
const INFO_FLAGS = new Set(['BASIC_RANGE_PASS_NOT_ACCURACY_CERTIFIED'])
// Keep this schema synchronized with the Python V2 ingestion contract.
// Database RTDB may omit ONLY an empty quality_flags array on retrieval.
const PACKET_FIELDS = new Set([
  'schema_version', 'node_id', 'sample_id', 'timestamp', 'sequence',
  'ph', 'tds', 'turbidity', 'rssi', 'quality_flags',
])
const QUALITY_CODE = /^[A-Z][A-Z0-9_]{0,63}$/
const SAMPLE_SUFFIX = /^[A-Za-z0-9_-]{1,80}$/
const SENSOR_LIMITS = {
  ph: (x) => x >= 0 && x <= 14,
  tds: (x) => x >= 0 && x <= 5000,
  turbidity: (x) => x >= 0 && x < 3000,
}

export function isAllowedRole(role) {
  return role === 'admin' || role === 'manager' || role === 'viewer'
}

export function getRoleFromClaims(claims) {
  return isAllowedRole(claims?.tasnim_role) ? claims.tasnim_role : null
}

export function validEpoch(value) {
  return Number.isSafeInteger(value) && value >= 1_704_067_200_000
}

export function canonicalSlot(value) {
  return validEpoch(value) ? Math.floor(value / SLOT_MS) * SLOT_MS : null
}

export function nodeMeasurement(raw, expectedNode) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)
      || raw.node_id !== expectedNode || raw.schema_version !== 2
      || !validEpoch(raw.timestamp)
      || typeof raw.sample_id !== 'string'
      || !raw.sample_id.startsWith(expectedNode + '_')
      || !SAMPLE_SUFFIX.test(raw.sample_id.slice(expectedNode.length + 1))
      || !Number.isSafeInteger(raw.sequence) || raw.sequence < 0
      || Object.keys(raw).some(key => !PACKET_FIELDS.has(key))
      || (raw.rssi !== undefined
          && (typeof raw.rssi !== 'number' || !Number.isFinite(raw.rssi)))) {
    return null
  }

  // RTDB can drop an empty [] property. This exception is for READS only:
  // sending a V2 packet to the gateway still requires quality_flags: [].
  const flags = raw.quality_flags === undefined ? [] : raw.quality_flags
  if (!Array.isArray(flags) || flags.length > 12
      || !flags.every(f => typeof f === 'string' && QUALITY_CODE.test(f))
      || new Set(flags).size !== flags.length) return null
  const flagged = flags.some(flag => !INFO_FLAGS.has(flag))
  const values = {}
  let incomplete = false
  for (const [key, valid] of Object.entries(SENSOR_LIMITS)) {
    const value = raw[key]
    const ok = typeof value === 'number' && Number.isFinite(value) && valid(value)
    if (!ok) incomplete = true
    // A flagged packet must not show any of its measurements as validated.
    values[key] = !flagged && ok ? value : null
  }
  const requiresReview = flagged || incomplete

  return {
    node_id: expectedNode,
    timestamp: raw.timestamp,
    sequence: raw.sequence,
    sample_id: raw.sample_id,
    rssi: typeof raw.rssi === 'number' && Number.isFinite(raw.rssi) ? raw.rssi : null,
    flags: [...flags],
    requiresReview,
    ...values,
  }
}

export function latestNodes(raw) {
  const records = {}
  for (const node of NODE_IDS) {
    records[node] = nodeMeasurement(raw?.[node]?.latest, node)
  }
  return records
}

export function historyRows(raw, limit = 60) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return []
  const rows = []
  for (const [slotKey, entry] of Object.entries(raw)) {
    const slot = Number(slotKey)
    if (!Number.isSafeInteger(slot) || slot <= 0 || slot % SLOT_MS !== 0
        || String(slot) !== slotKey || !entry || typeof entry !== 'object'
      || Array.isArray(entry)) continue
    const nodes = {}
    for (const node of NODE_IDS) {
      const parsed = nodeMeasurement(entry[node], node)
      nodes[node] = parsed && canonicalSlot(parsed.timestamp) === slot ? parsed : null
    }
    const complete = NODE_IDS.every(node => {
      const r = nodes[node]
      return r && !r.requiresReview
        && r.ph !== null && r.tds !== null && r.turbidity !== null
    })
    rows.push({ slot, nodes, complete, hasAnalysis: !!entry.analysis })
  }
  rows.sort((a, b) => a.slot - b.slot)
  return rows.slice(-Math.max(1, Math.min(limit, 240)))
}

export function analysisStatus(analysis, rows) {
  if (!analysis || typeof analysis !== 'object'
      || !validEpoch(analysis.source_timestamp_ms)) {
    return { state: 'NO_ANALYSIS', analysis: null }
  }
  if (analysis.data_source !== 'HARDWARE_TEST'
      || analysis.model_stage !== 'PROTOTYPE_SIMULATION'
      || typeof analysis.model_version !== 'string'
      || !analysis.model_version.trim()
      || typeof analysis.session_id !== 'string'
      || !analysis.session_id.trim()
      || !['NORMAL', 'ANOMALI'].includes(analysis.status)
      || typeof analysis.model_disagreement !== 'boolean') {
    return { state: 'UNTRUSTED_ANALYSIS', analysis: null }
  }
  const last = rows[rows.length - 1]
  const matches = last?.complete && last.slot === analysis.source_timestamp_ms
  // This only establishes timestamp alignment. The browser does not verify
  // worker source_digest_sha256 or the provenance of a model decision.
  return { state: matches ? 'SLOT_ALIGNED_UNVERIFIED' : 'STALE_OR_INCOMPLETE',
    analysis }
}

export function wita(value) {
  return validEpoch(value) ? new Date(value).toLocaleString('id-ID', {
    timeZone: 'Asia/Makassar', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }) + ' WITA' : '—'
}

/**
 * Dashboard field-readiness signals (engineering health, not water safety).
 * Staleness is based on acquisition time, never the Firebase receive time.
 */
export function hardwareReadiness(nodes, rows, nowMs = Date.now()) {
  const states = {}
  const threshold = 10 * 60 * 1000
  for (const node of NODE_IDS) {
    const r = nodes?.[node]
    if (!r) {
      states[node] = 'NO_DATA'
    } else if (!validEpoch(r.timestamp) || r.timestamp > nowMs + 60_000) {
      states[node] = 'CLOCK_INVALID'
    } else if (nowMs - r.timestamp > threshold) {
      states[node] = 'STALE'
    } else if (r.requiresReview || ['ph', 'tds', 'turbidity'].some(k => r[k] === null)) {
      states[node] = 'REVIEW'
    } else {
      states[node] = 'RECENT'
    }
  }
  const completeSlots = rows.filter(r => r.complete).length
  return {
    states,
    recentNodes: NODE_IDS.filter(n => states[n] === 'RECENT').length,
    totalSlots: rows.length,
    completeSlots,
    incompleteSlots: rows.length - completeSlots,
  }
}
