
import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds
} from '@firebase/rules-unit-testing';

import {
  ref,
  get,
  set
} from 'firebase/database';

import { readFileSync } from 'node:fs';

const PROJECT = 'demo-tasnim-security';

const env = await initializeTestEnvironment({
  projectId: PROJECT,
  database: {
    host: '127.0.0.1',
    port: 19003,
    rules: readFileSync(
      'database.hardware_test.v2.candidate.rules.json',
      'utf8'
    )
  }
});

let passed = 0;

async function check(name, action) {
  await action();
  passed++;
  console.log(`[PASS ${passed}] ${name}`);
}

const anonymous = env.unauthenticatedContext().database();
const unknown = env.authenticatedContext('unknown').database();

const admin = env.authenticatedContext(
  'admin', {tasnim_role: 'admin'}
).database();

const manager = env.authenticatedContext(
  'manager', {tasnim_role: 'manager'}
).database();

const viewer = env.authenticatedContext(
  'viewer', {tasnim_role: 'viewer'}
).database();

const device = env.authenticatedContext(
  'esp32-n0', {tasnim_role: 'device', node_id: 'N0'}
).database();

const backend = env.authenticatedContext(
  'backend', {tasnim_role: 'backend'}
).database();

const invalidRole = env.authenticatedContext(
  'other', {tasnim_role: 'superuser'}
).database();

const sample = {
  timestamp: 1791724501000,
  ph: 7.1,
  tds: 200,
  turbidity: 12
};

try {
  await env.withSecurityRulesDisabled(async ctx => {
    const db = ctx.database();

    await set(ref(db, 'hardware_test/nodes/N0/latest'), sample);
    await set(ref(db, 'hardware_test/history/1791724500000/N0'), sample);
    await set(ref(db, 'hardware_test/analysis/latest'), {
      status: 'NORMAL'
    });
    await set(ref(db, 'simulation/nodes/N0/latest'), sample);
    await set(ref(db, 'gateway_state/nonces/N0/demoNonce'), {
      fingerprint: 'synthetic-only'
    });
  });

  console.log('=== REALTIME DATABASE EMULATOR ACCESS TEST ===');

  await check('Anonymous hardware read denied', () =>
    assertFails(get(ref(anonymous, 'hardware_test/nodes/N0/latest')))
  );

  await check('Unknown user hardware read denied', () =>
    assertFails(get(ref(unknown, 'hardware_test/nodes/N0/latest')))
  );

  await check('Unsupported role read denied', () =>
    assertFails(get(ref(invalidRole, 'hardware_test/nodes/N0/latest')))
  );

  await check('Admin can read latest', () =>
    assertSucceeds(get(ref(admin, 'hardware_test/nodes/N0/latest')))
  );

  await check('Manager can read history', () =>
    assertSucceeds(get(ref(manager, 'hardware_test/history/1791724500000/N0')))
  );

  await check('Viewer can read analysis', () =>
    assertSucceeds(get(ref(viewer, 'hardware_test/analysis/latest')))
  );

  await check('Viewer can read simulation', () =>
    assertSucceeds(get(ref(viewer, 'simulation/nodes/N0/latest')))
  );

  await check('Anonymous simulation read denied', () =>
    assertFails(get(ref(anonymous, 'simulation/nodes/N0/latest')))
  );

  await check('Anonymous root read denied', () =>
    assertFails(get(ref(anonymous, '/')))
  );

  await check('Viewer cannot write latest', () =>
    assertFails(set(ref(viewer, 'hardware_test/nodes/N0/latest'), sample))
  );

  await check('Manager cannot write history', () =>
    assertFails(set(ref(manager, 'hardware_test/history/test/N0'), sample))
  );

  await check('Admin cannot write sensor data directly', () =>
    assertFails(set(ref(admin, 'hardware_test/nodes/N1/latest'), sample))
  );

  await check('ESP32 cannot write own node in this draft', () =>
    assertFails(set(ref(device, 'hardware_test/nodes/N0/latest'), sample))
  );

  await check('ESP32 cannot write other node', () =>
    assertFails(set(ref(device, 'hardware_test/nodes/N1/latest'), sample))
  );

  await check('ESP32 cannot write AI analysis', () =>
    assertFails(set(ref(device, 'hardware_test/analysis/latest'), {
      status: 'ANOMALI'
    }))
  );

  await check('Backend client cannot write analysis', () =>
    assertFails(set(ref(backend, 'hardware_test/analysis/latest'), {
      status: 'NORMAL'
    }))
  );

  await check('Anonymous cannot write', () =>
    assertFails(set(ref(anonymous, 'hardware_test/nodes/N0/latest'), sample))
  );

  await check('Viewer cannot write simulation', () =>
    assertFails(set(ref(viewer, 'simulation/nodes/N0/latest'), sample))
  );

  await check('Admin cannot read gateway nonce registry', () =>
    assertFails(get(ref(admin, 'gateway_state/nonces/N0/demoNonce')))
  );

  await check('Device cannot write gateway nonce registry', () =>
    assertFails(set(ref(device, 'gateway_state/nonces/N0/forgedNonce'), {
      fingerprint: 'tampered'
    }))
  );

  console.log(`\n[PASS] ${passed}/20 emulator authorization tests`);
  console.log('[INFO] Backend Admin SDK bypass is NOT tested here.');
  console.log('[INFO] ESP32 ingestion is NOT enabled by candidate Rules.');

} finally {
  await env.cleanup();
}
