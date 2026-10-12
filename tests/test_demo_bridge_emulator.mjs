// Same-origin browser demo API test using actual Vite dev server + two emulators.
// Both emulators are seeded before this script executes. NEVER connects to LIVE.
import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

const project = 'demo-tasnim-security'
if (process.env.GCLOUD_PROJECT !== project
    || process.env.FIREBASE_AUTH_EMULATOR_HOST !== '127.0.0.1:19004'
    || process.env.FIREBASE_DATABASE_EMULATOR_HOST !== '127.0.0.1:19003'
    || process.env.TASNIM_AUTH_TEST_EMULATOR_ONLY !== 'YES') {
  throw Error('REFUSED: browser demo API test requires both localhost emulators')
}
process.env.TASNIM_DEMO_LOGIN_MODE = 'YES'
process.env.VITE_TASNIM_DEMO_LOGIN = 'YES'
process.env.VITE_TASNIM_HARDWARE_V2_PREVIEW = 'YES'
const password = 'EmulatorOnly_2026_Test!'

test('browser demo login, same-origin snapshot, and read-only security', async () => {
  const vite = await createServer({
    configFile: 'vite.config.js', logLevel: 'silent',
    server: { host: '127.0.0.1', port: 0 },
  })
  await vite.listen()
  try {
    const port = vite.httpServer.address().port
    const base = 'http://127.0.0.1:' + port + '/__tasnim_demo__/'
    const health = await (await fetch(base + 'health')).json()
    assert.deepEqual(health, { demo: true, project, live: false })

    const anonymous = await fetch(base + 'snapshot')
    assert.equal(anonymous.status, 401)

    const malformed = await fetch(base + 'login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@production.invalid', password }),
    })
    assert.equal(malformed.status, 400)

    for (const role of ['admin','manager','viewer']) {
      const login = await fetch(base + 'login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: role + '@tasnim-auth-demo.invalid', password }),
      })
      assert.equal(login.status, 200, role + ': ' + await login.clone().text())
      const session = await login.json()
      assert.equal(session.role, role)
      assert.match(session.token, /^[A-Za-z0-9_.-]+$/)

      const snapshot = await fetch(base + 'snapshot?limit=61', {
        headers: { Authorization: 'Bearer ' + session.token },
      })
      assert.equal(snapshot.status, 200, role + ': ' + await snapshot.clone().text())
      const data = await snapshot.json()
      assert.equal(data.nodes?.N0?.latest?.node_id, 'N0')
      assert.equal(data.nodes?.N1?.latest?.node_id, 'N1')
      assert.equal(data.nodes?.N2?.latest?.node_id, 'N2')
      assert.ok(Object.keys(data.history || {}).length >= 3)
      assert.equal(data.analysis?.model_stage, 'PROTOTYPE_SIMULATION')

      const write = await fetch(base + 'snapshot', {
        method: 'POST', headers: { Authorization: 'Bearer ' + session.token },
      })
      assert.equal(write.status, 405)
    }

    const wrong = await fetch(base + 'login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'viewer@tasnim-auth-demo.invalid', password: 'incorrect',
      }),
    })
    assert.equal(wrong.status, 401)
    const unknown = await fetch(base + 'snapshot', {
      headers: { Authorization: 'Bearer not-a-real-token' },
    })
    assert.equal(unknown.status, 401)
    const crossOrigin = await fetch(base + 'login', {
      method: 'POST', headers: {
        'Content-Type': 'application/json', Origin: 'https://example.com',
      },
      body: JSON.stringify({ email: 'viewer@tasnim-auth-demo.invalid', password }),
    })
    assert.equal(crossOrigin.status, 403)
  } finally {
    await vite.close()
  }
})
