/** Last step of full-stack acceptance: real browser route over Auth/RTDB. */
import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import {
  latestNodes, historyRows, analysisStatus, hardwareReadiness,
} from '../src/services/hardwareV2View.js'
import { validDemoSnapshot } from '../src/services/demoSnapshotPolling.js'
import { normalizeSupervisorStatus } from '../src/services/operationalMonitorDemo.js'

const project = 'demo-tasnim-security'
if (process.env.GCLOUD_PROJECT !== project
    || process.env.FIREBASE_AUTH_EMULATOR_HOST !== '127.0.0.1:19004'
    || process.env.FIREBASE_DATABASE_EMULATOR_HOST !== '127.0.0.1:19003'
    || process.env.TASNIM_AUTH_TEST_EMULATOR_ONLY !== 'YES'
    || process.env.GOOGLE_APPLICATION_CREDENTIALS) {
  throw Error('REFUSED: full-stack browser test requires local demo Emulators')
}

process.env.TASNIM_DEMO_LOGIN_MODE = 'YES'
process.env.VITE_TASNIM_DEMO_LOGIN = 'YES'
process.env.VITE_TASNIM_HARDWARE_V2_PREVIEW = 'YES'

test('signed HTTP-to-AI pipeline is visible via authenticated read-only dashboard', async () => {
  const vite = await createServer({
    configFile: 'vite.config.js', logLevel: 'silent',
    server: { host: '127.0.0.1', port: 0 },
  })
  await vite.listen()
  try {
    const base = 'http://127.0.0.1:' + vite.httpServer.address().port
      + '/__tasnim_demo__/'
    const login = await fetch(base + 'login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'admin@tasnim-auth-demo.invalid',
        password: 'EmulatorOnly_2026_Test!',
      }),
    })
    assert.equal(login.status, 200)
    const { token } = await login.json()
    const response = await fetch(base + 'snapshot?limit=50', {
      headers: { Authorization: 'Bearer ' + token },
    })
    assert.equal(response.status, 200, await response.clone().text())
    const snapshot = await response.json()
    assert.equal(validDemoSnapshot(snapshot), true)
    assert.deepEqual(Object.keys(snapshot).sort(),
      ['nodes', 'history', 'analysis', 'operational_status'].sort())

    const nodes = latestNodes(snapshot.nodes)
    const rows = historyRows(snapshot.history, 50)
    const ai = analysisStatus(snapshot.analysis, rows)
    const supervisor = normalizeSupervisorStatus(snapshot.operational_status)
    assert.deepEqual(Object.keys(nodes).sort(), ['N0', 'N1', 'N2'])
    assert.equal(rows.length, 3)
    assert.ok(rows.every(row => row.complete))
    assert.equal(rows.at(-1).slot, 1791725100000)
    assert.ok(Object.values(nodes).every(n => n && !n.requiresReview))
    // Browser intentionally cannot verify source hash; it must NOT claim
    // AI scientific certification or provenance verification.
    assert.equal(ai.state, 'SLOT_ALIGNED_UNVERIFIED')
    assert.equal(ai.analysis.model_stage, 'PROTOTYPE_SIMULATION')
    assert.equal(supervisor?.state, 'PROCESSED')
    assert.equal(supervisor?.processed_count, 2)
    assert.equal(Object.hasOwn(snapshot, 'worker_state'), false)
    assert.equal(Object.hasOwn(snapshot, 'gateway_state'), false)

    // Acquisition time is historical in this synthetic test, so it must
    // show STALE, not ONLINE/RECENT, when the current date is later.
    const health = hardwareReadiness(nodes, rows, Date.now())
    assert.equal(health.recentNodes, 0)
    assert.ok(Object.values(health.states).every(s => s === 'STALE'))

    const write = await fetch(base + 'snapshot', {
      method: 'POST', headers: { Authorization: 'Bearer ' + token },
    })
    assert.equal(write.status, 405)
    const forbidden = await fetch(
      'http://127.0.0.1:19003/gateway_state/nonces.json'
        + '?ns=demo-tasnim-security-default-rtdb&auth='
        + encodeURIComponent(token),
    )
    assert.equal(forbidden.status, 401)
  } finally {
    await vite.close()
  }
})
