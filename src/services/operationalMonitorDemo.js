// Pure candidate engineering-alert policy. No Firebase imports/side effects.
// A delayed sensor is NOT a water-contamination diagnosis.
import { NODE_IDS, SLOT_MS, validEpoch } from './hardwareV2View.js'

const allowedStates = new Set([
  'PROCESSED', 'IDLE', 'PREVIEW', 'WAITING_LOCK',
  'REVIEW_REQUIRED', 'RETRY_EXHAUSTED', 'FAILED',
])
const allowedErrors = new Set([
  'NONE', 'LEASE_BUSY', 'REVIEW_REQUIRED',
  'SOURCE_CHANGED', 'TRANSIENT_ERROR', 'WORKER_ERROR',
])
const statusKeys = [
  'schema_version', 'state', 'error_code', 'timestamp_ms',
  'attempts', 'processed_count', 'recovered_count',
  'deferred_count', 'would_process_count', 'source_root', 'model_stage',
]

export function normalizeSupervisorStatus(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)
      || Object.keys(raw).length !== statusKeys.length
      || !statusKeys.every(k => Object.hasOwn(raw, k))
      || raw.schema_version !== 1
      || !allowedStates.has(raw.state) || !allowedErrors.has(raw.error_code)
      || !validEpoch(raw.timestamp_ms)
      || raw.source_root !== 'hardware_test'
      || raw.model_stage !== 'PROTOTYPE_SIMULATION'
      || !Number.isInteger(raw.attempts) || raw.attempts < 0 || raw.attempts > 3) {
    return null
  }
  for (const k of ['processed_count','recovered_count','deferred_count','would_process_count']) {
    if (!Number.isInteger(raw[k]) || raw[k] < 0 || raw[k] > 5000) return null
  }
  return Object.fromEntries(statusKeys.map(k => [k, raw[k]]))
}

export function evaluateOperationalAlerts(nodes, rows, rawStatus, nowMs = Date.now()) {
  if (!validEpoch(nowMs)) throw Error('operational_alerts:invalid_now_ms')
  const alerts = []
  const emit = (severity, code, message) => alerts.push({ severity, code, message })
  const status = normalizeSupervisorStatus(rawStatus)
  const elapsed = ts => nowMs - ts

  for (const n of NODE_IDS) {
    const packet = nodes?.[n]
    if (!packet) continue // Missing initial data is unknown, not 'offline'.
    if (!validEpoch(packet.timestamp) || elapsed(packet.timestamp) < -60_000) {
      emit('review', 'NODE_CLOCK_' + n, n + ': periksa waktu akuisisi sensor.')
    } else if (elapsed(packet.timestamp) > 30 * 60_000) {
      emit('review', 'NODE_STALE_' + n, n + ': tidak ada pengukuran valid >30 menit.')
    } else if (elapsed(packet.timestamp) > 15 * 60_000) {
      emit('warning', 'NODE_DELAY_' + n, n + ': pengukuran terlambat >15 menit.')
    }
    if (packet.requiresReview || ['ph','tds','turbidity'].some(k => packet[k] === null)) {
      emit('review', 'NODE_QUALITY_' + n, n + ': flag atau nilai perlu ditinjau.')
    }
  }

  // Current/open slots and the first 5-minute grace after closure do not
  // create a missing-node alarm. Backfill may still be on the way.
  const graceMs = 5 * 60_000
  const sorted = (Array.isArray(rows) ? rows : [])
    .filter(row => validEpoch(row?.slot) && row.slot % SLOT_MS === 0
      && row.slot + SLOT_MS + graceMs <= nowMs)
    .sort((a, b) => a.slot - b.slot)
    .slice(-4)
  const incomplete = sorted.filter(row => !row.complete)
  if (incomplete.length >= 2) {
    emit('warning', 'INCOMPLETE_SLOTS', incomplete.length
      + ' dari ' + sorted.length + ' slot tertutup tidak lengkap setelah grace.')
  }
  // One incomplete closed slot is informational, not an alarm.
  // Empty/no history does not imply a failing sensor.

  if (status && elapsed(status.timestamp_ms) >= -60_000
      && elapsed(status.timestamp_ms) <= 15 * 60_000) {
    if (['FAILED','RETRY_EXHAUSTED','REVIEW_REQUIRED'].includes(status.state)) {
      emit('review', 'SUPERVISOR_' + status.state,
        'Supervisor meminta pemeriksaan: ' + status.state + '.')
    }
    // WAITING_LOCK is a normal cooperative outcome, not an alarm.
  }

  const level = alerts.some(a => a.severity === 'review') ? 'review'
    : alerts.length ? 'warning' : 'normal'
  return {
    level, alerts, supervisor: status,
    missingNodes: NODE_IDS.filter(n => !nodes?.[n]),
    waitingSlots: incomplete.length,
    graceMinutes: 5,
  }
}
