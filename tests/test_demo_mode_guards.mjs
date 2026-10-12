import test from 'node:test'
import assert from 'node:assert/strict'
import { createDemoBridgePlugin, isDemoEnvironment } from '../dev/tasnimDemoBridge.js'

const ALL = {
  TASNIM_DEMO_LOGIN_MODE: 'YES',
  VITE_TASNIM_DEMO_LOGIN: 'YES',
  VITE_TASNIM_HARDWARE_V2_PREVIEW: 'YES',
  GCLOUD_PROJECT: 'demo-tasnim-security',
  FIREBASE_AUTH_EMULATOR_HOST: '127.0.0.1:19004',
  FIREBASE_DATABASE_EMULATOR_HOST: '127.0.0.1:19003',
}

test('demo bridge unavailable by default and rejects incomplete environment', () => {
  assert.equal(createDemoBridgePlugin({}), null)
  for (const key of Object.keys(ALL)) {
    const bad = { ...ALL, [key]: 'NOT_VALID' }
    assert.equal(isDemoEnvironment(bad), false, key)
    assert.throws(() => createDemoBridgePlugin(bad), /REFUSED/, key)
  }
})
test('explicit demo flags permit a dev-server-only bridge', () => {
  assert.equal(isDemoEnvironment(ALL), true)
  const plugin = createDemoBridgePlugin(ALL)
  assert.equal(plugin.name, 'tasnim-emulator-browser-demo-only')
  assert.equal(plugin.apply, 'serve')
  assert.equal(typeof plugin.configureServer, 'function')
})
