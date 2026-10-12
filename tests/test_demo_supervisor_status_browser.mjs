/** Real end-to-end: one-shot supervisor -> sanitized status -> demo browser. */
import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

if (process.env.GCLOUD_PROJECT !== 'demo-tasnim-security'
  || process.env.FIREBASE_DATABASE_EMULATOR_HOST !== '127.0.0.1:19003'
  || process.env.FIREBASE_AUTH_EMULATOR_HOST !== '127.0.0.1:19004'
  || process.env.TASNIM_AUTH_TEST_EMULATOR_ONLY !== 'YES')
  throw Error('REFUSED: demo localhost emulators required')

process.env.TASNIM_DEMO_LOGIN_MODE = 'YES'
process.env.VITE_TASNIM_DEMO_LOGIN = 'YES'
process.env.VITE_TASNIM_HARDWARE_V2_PREVIEW = 'YES'

test('one-shot synthetic supervisor is visible to allowed browser role, private tree stays denied', async () => {
  const vite = await createServer({
    configFile: 'vite.config.js', logLevel: 'silent',
    server: { host: '127.0.0.1', port: 0 },
  })
  await vite.listen()
  try {
    const port = vite.httpServer.address().port
    const base = 'http://127.0.0.1:' + port + '/__tasnim_demo__/'
    const response = await fetch(base + 'login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'admin@tasnim-auth-demo.invalid',
        password: 'EmulatorOnly_2026_Test!',
      }),
    })
    assert.equal(response.status, 200)
    const { token } = await response.json()
    const snapshotResponse = await fetch(base + 'snapshot', {
      headers: { Authorization: 'Bearer ' + token },
    })
    assert.equal(snapshotResponse.status, 200, await snapshotResponse.clone().text())
    const snapshot = await snapshotResponse.json()
    const result = snapshot.operational_status
    assert.equal(result?.state, 'PROCESSED')
    assert.equal(result?.processed_count, 1)
    assert.equal(result?.attempts, 1)
    assert.equal(result?.error_code, 'NONE')
    assert.equal(result?.model_stage, 'PROTOTYPE_SIMULATION')
    assert.deepEqual(Object.keys(result).sort(), [
      'schema_version', 'state', 'error_code', 'timestamp_ms', 'attempts',
      'processed_count', 'recovered_count', 'deferred_count',
      'would_process_count', 'source_root', 'model_stage',
    ].sort())
    assert.equal(Object.hasOwn(snapshot, 'worker_state'), false)
    const denied = await fetch(
      'http://127.0.0.1:19003/worker_state/ai_v2_supervisor/latest.json'
        + '?ns=demo-tasnim-security-default-rtdb&auth=' + encodeURIComponent(token),
    )
    assert.equal(denied.status, 401)
    const deniedAudit = await fetch(
      'http://127.0.0.1:19003/worker_state/ai_v2_supervisor/audit_v1.json'
        + '?ns=demo-tasnim-security-default-rtdb&auth=' + encodeURIComponent(token),
    )
    assert.equal(deniedAudit.status, 401)
    const write = await fetch(base + 'snapshot', {
      method: 'PATCH', headers: { Authorization: 'Bearer ' + token },
    })
    assert.equal(write.status, 405)
  } finally {
    await vite.close()
  }
})
