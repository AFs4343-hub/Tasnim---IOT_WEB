import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createDemoSnapshotPoller, validDemoSnapshot,
} from '../src/services/demoSnapshotPolling.js'

const valid = () => ({
  nodes: null, history: null, analysis: null, operational_status: null,
})
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}
const harness = (load) => {
  let interval, cancelled = 0
  const delivered = [], failures = []
  const poller = createDemoSnapshotPoller({
    load,
    onSnapshot: value => delivered.push(value),
    onFailure: error => failures.push(error.message),
    schedule: (callback, ms) => {
      assert.equal(ms, 30_000)
      interval = callback
      return 1
    },
    unschedule: id => { assert.equal(id, 1); cancelled++ },
  })
  return { poller, delivered, failures, tick: () => interval(), cancelled: () => cancelled }
}

test('snapshot boundary rejects partial, malformed, and private fields', () => {
  assert.equal(validDemoSnapshot(valid()), true)
  assert.equal(validDemoSnapshot({ ...valid(), history: {} }), true)
  assert.equal(validDemoSnapshot({ ...valid(), history: [] }), false)
  assert.equal(validDemoSnapshot({ ...valid(), analysis: 99 }), false)
  assert.equal(validDemoSnapshot({ ...valid(), nodes: 'unavailable' }), false)
  assert.equal(validDemoSnapshot({ ...valid(), worker_state: { token: 'never' } }), false)
  assert.equal(validDemoSnapshot({ nodes: null, history: null }), false)
  assert.equal(validDemoSnapshot({ ...valid(), operational_status: { state: 'PROCESSED' } }), false)
})

test('overlapping 30-second refresh never starts a second in-flight request', async () => {
  const requests = []
  const h = harness(signal => {
    const next = deferred()
    requests.push({ ...next, signal })
    return next.promise
  })
  h.poller.start()
  assert.equal(requests.length, 1)
  h.tick()
  assert.equal(await h.poller.refresh(), false)
  assert.equal(requests.length, 1)
  requests[0].resolve({ ...valid(), nodes: { N0: {} } })
  await flush()
  assert.equal(h.delivered.length, 1)
  h.tick()
  assert.equal(requests.length, 2)
  requests[1].resolve(valid())
  await flush()
  assert.equal(h.delivered.length, 2)
  assert.equal(h.failures.length, 0)
  h.poller.stop()
  assert.equal(h.cancelled(), 1)
})

test('disconnect hides obsolete readings, then recovery restores fresh snapshot', async () => {
  let call = 0
  const h = harness(async () => {
    call++
    if (call === 1) return { ...valid(), history: { 1791724500000: { N0: {} } } }
    if (call === 2) throw Error('Emulator unavailable')
    return { ...valid(), history: { 1791724800000: { N1: {} } } }
  })
  h.poller.start()
  await flush()
  assert.equal(h.delivered.length, 1)
  h.tick()
  await flush()
  assert.deepEqual(h.failures, ['Emulator unavailable'])
  h.tick()
  await flush()
  assert.equal(h.delivered.length, 2)
  assert.deepEqual(Object.keys(h.delivered[1].history), ['1791724800000'])
  h.poller.stop()

  // The UI's onFailure callback must blank its last shown value and then
  // display the next successful refresh, with no cached "online" state.
  let shown = null
  let runs = 0
  let tick
  const poller = createDemoSnapshotPoller({
    load: async () => {
      runs++
      if (runs === 2) throw Error('connection lost')
      return { ...valid(), nodes: { N0: { seq: runs } } }
    },
    onSnapshot: next => { shown = next },
    onFailure: () => { shown = null },
    schedule: callback => { tick = callback; return 1 },
    unschedule: () => {},
  })
  poller.start()
  await flush()
  assert.equal(shown.nodes.N0.seq, 1)
  tick()
  await flush()
  assert.equal(shown, null)
  tick()
  await flush()
  assert.equal(shown.nodes.N0.seq, 3)
  poller.stop()
})

test('invalid successful response fails closed instead of being rendered', async () => {
  const h = harness(async () => ({ ...valid(), history: ['malformed'] }))
  h.poller.start()
  await flush()
  assert.deepEqual(h.delivered, [])
  assert.deepEqual(h.failures, ['DEMO_SNAPSHOT_INVALID'])
  h.poller.stop()
})

test('logout aborts in-flight request and ignores late success and failure', async () => {
  const pending = deferred()
  let signal
  const h = harness(s => { signal = s; return pending.promise })
  h.poller.start()
  h.poller.stop()
  assert.equal(signal.aborted, true)
  pending.resolve(valid())
  await flush()
  assert.equal(h.delivered.length, 0)
  assert.equal(h.failures.length, 0)
  assert.equal(h.cancelled(), 1)
  assert.equal(await h.poller.refresh(), false)
})

test('session restart ignores response from previous request', async () => {
  const requests = []
  const h = harness(s => {
    const task = deferred()
    requests.push({ ...task, signal: s })
    return task.promise
  })
  h.poller.start()
  h.poller.stop()
  h.poller.start()
  assert.equal(requests.length, 2)
  requests[0].resolve({ ...valid(), history: { old: true } })
  await flush()
  assert.equal(h.delivered.length, 0)
  requests[1].resolve({ ...valid(), history: { new: true } })
  await flush()
  assert.deepEqual(h.delivered[0].history, { new: true })
  h.poller.stop()
})
