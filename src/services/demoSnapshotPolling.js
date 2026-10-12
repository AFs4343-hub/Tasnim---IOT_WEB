// Read-only browser-demo snapshot lifecycle. No Firebase or browser writes.
// A session may issue only one request at a time. Failed refresh hides the
// old snapshot: the UI must not imply that cached telemetry is live.
import { normalizeSupervisorStatus } from './operationalMonitorDemo.js'

const SNAPSHOT_KEYS = ['nodes', 'history', 'analysis', 'operational_status']

const nullableObject = value => value === null
  || (typeof value === 'object' && !Array.isArray(value))

export function validDemoSnapshot(data) {
  if (data === null || typeof data !== 'object' || Array.isArray(data)
      || Object.keys(data).length !== SNAPSHOT_KEYS.length
      || !SNAPSHOT_KEYS.every(key => Object.hasOwn(data, key))) return false
  if (!SNAPSHOT_KEYS.every(key => nullableObject(data[key]))) return false
  // Do not display untrusted operational text, private worker state or
  // hidden extra fields as part of a read-only dashboard snapshot.
  return data.operational_status === null
    || normalizeSupervisorStatus(data.operational_status) !== null
}

/**
 * Injected async reader + callbacks keep behavior offline-testable.
 * start() performs one immediate refresh, followed by periodic updates.
 * stop() invalidates late responses before they can update a new session.
 * refresh() returns false when another request is still pending.
 */
export function createDemoSnapshotPoller({
  load, onSnapshot, onFailure, intervalMs = 30_000,
  schedule = (callback, delay) => setInterval(callback, delay),
  unschedule = id => clearInterval(id),
  controllerFactory = () => new AbortController(),
}) {
  if (typeof load !== 'function' || typeof onSnapshot !== 'function'
      || typeof onFailure !== 'function'
      || !Number.isSafeInteger(intervalMs) || intervalMs < 1_000) {
    throw Error('demo_poller:invalid_configuration')
  }

  let active = false
  let busy = false
  let intervalId = null
  let pending = null

  async function refresh() {
    if (!active || busy) return false
    busy = true
    const request = controllerFactory()
    pending = request
    try {
      const data = await load(request.signal)
      if (active && pending === request) {
        if (!validDemoSnapshot(data)) throw Error('DEMO_SNAPSHOT_INVALID')
        onSnapshot(data)
      }
    } catch (error) {
      if (active && pending === request) onFailure(error)
    } finally {
      if (pending === request) {
        pending = null
        busy = false
      }
    }
    return true
  }

  function start() {
    if (active) return
    active = true
    intervalId = schedule(() => { void refresh() }, intervalMs)
    void refresh()
  }

  function stop() {
    if (!active) return
    active = false
    unschedule(intervalId)
    intervalId = null
    const previous = pending
    pending = null
    busy = false
    previous?.abort()
  }

  return { start, refresh, stop }
}
