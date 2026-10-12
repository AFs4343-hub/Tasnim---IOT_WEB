/**
 * Real Firebase Web Auth SDK -> real RTDB Emulator integration acceptance.
 * Synthetic users are provisioned ONLY by the guarded Python demo seed.
 * No Firebase production access or browser writes are exercised.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { initializeApp, deleteApp } from 'firebase/app'
import {
  getAuth, connectAuthEmulator, signInWithEmailAndPassword,
  getIdTokenResult, signOut,
} from 'firebase/auth'
import {
  getDatabase, connectDatabaseEmulator,
  ref, get, set, query, orderByKey, limitToLast,
} from 'firebase/database'
import { getRoleFromClaims } from '../src/services/hardwareV2View.js'

const PROJECT = 'demo-tasnim-security'
const AUTH_HOST = '127.0.0.1:19004'
const DB_HOST = '127.0.0.1:19003'
const PASSWORD = 'EmulatorOnly_2026_Test!'
const SLOT = 1791724500000

function requireDemoOnly() {
  if (process.env.TASNIM_AUTH_TEST_EMULATOR_ONLY !== 'YES'
      || process.env.GCLOUD_PROJECT !== PROJECT
      || process.env.FIREBASE_AUTH_EMULATOR_HOST !== AUTH_HOST
      || process.env.FIREBASE_DATABASE_EMULATOR_HOST !== DB_HOST) {
    throw new Error('REFUSED: real Auth integration requires demo localhost emulators')
  }
}
requireDemoOnly() // Must fail before initializing Firebase clients.

let clientCounter = 0
function client() {
  const app = initializeApp({
    apiKey: 'emulator-only-not-a-real-api-key',
    authDomain: 'demo-tasnim-security.firebaseapp.com',
    projectId: PROJECT,
    databaseURL: `http://${DB_HOST}/?ns=${PROJECT}-default-rtdb`,
  }, `auth-demo-test-${++clientCounter}`)
  const auth = getAuth(app)
  connectAuthEmulator(auth, `http://${AUTH_HOST}`, { disableWarnings: true })
  const database = getDatabase(app)
  connectDatabaseEmulator(database, '127.0.0.1', 19003)
  return { app, auth, database }
}

async function withAccount(role, action) {
  const c = client()
  try {
    await signInWithEmailAndPassword(
      c.auth, `${role}@tasnim-auth-demo.invalid`, PASSWORD,
    )
    const result = await getIdTokenResult(c.auth.currentUser, true)
    await action(c, result.claims)
  } finally {
    await signOut(c.auth)
    await deleteApp(c.app)
  }
}

function mustDeny(action) {
  return assert.rejects(action, /permission.denied/i)
}

test('Auth Emulator issues real tokens and RTDB enforces candidate role claims', async (t) => {
  for (const role of ['admin', 'manager', 'viewer']) {
    await t.test(`${role} can read V2 paths but cannot write`, async () => {
      await withAccount(role, async ({ database }, claims) => {
        assert.equal(getRoleFromClaims(claims), role)
        const nodes = await get(ref(database, 'hardware_test/nodes'))
        assert.equal(nodes.val()?.N0?.latest?.node_id, 'N0')
        const history = await get(query(
          ref(database, 'hardware_test/history'),
          orderByKey(), limitToLast(61),
        ))
        assert.equal(history.val()?.[SLOT]?.N1?.node_id, 'N1')
        const ai = await get(ref(database, 'hardware_test/analysis/latest'))
        assert.equal(ai.val()?.model_stage, 'PROTOTYPE_SIMULATION')
        await mustDeny(() => set(
          ref(database, 'hardware_test/nodes/N0/latest'),
          { ph: 0 },
        ))
        await mustDeny(() => get(
          ref(database, 'gateway_state/nonces/N0/test-only'),
        ))
      })
    })
  }

  for (const role of ['unknown', 'device', 'badrole']) {
    await t.test(`${role} signs in but is denied hardware access`, async () => {
      await withAccount(role, async ({ database }, claims) => {
        assert.equal(getRoleFromClaims(claims), null)
        await mustDeny(() => get(ref(database, 'hardware_test/nodes')))
        await mustDeny(() => get(query(
          ref(database, 'hardware_test/history'),
          orderByKey(), limitToLast(61),
        )))
        await mustDeny(() => get(ref(database, 'hardware_test/analysis/latest')))
      })
    })
  }

  await t.test('anonymous client cannot read hardware', async () => {
    const c = client()
    try {
      await mustDeny(() => get(ref(c.database, 'hardware_test/nodes')))
    } finally {
      await deleteApp(c.app)
    }
  })

  await t.test('role revocation is visible after an actual token refresh', async () => {
    await withAccount('viewer', async (c, claims) => {
      assert.equal(getRoleFromClaims(claims), 'viewer')
      const proc = spawnSync('python3', [
        'tests/seed_hardware_auth_emulator.py', '--set-viewer-role', 'none',
      ], { env: process.env, encoding: 'utf8', timeout: 15000 })
      assert.equal(proc.status, 0, proc.stderr || proc.stdout)
      const refreshed = await getIdTokenResult(c.auth.currentUser, true)
      assert.equal(getRoleFromClaims(refreshed.claims), null)
      // When the application receives this token event, it must remove the
      // role-gated UI. The RTDB Rules are also tested against new tokens.
    })
  })
})
