import test from 'node:test'
import assert from 'node:assert/strict'
import { adaptEmulatorForLegacyDashboard } from '../src/services/demoLegacyAdapter.js'

const s = 1791724500000
const node = (id, slot = s, values = {}) => ({
  node_id: id, schema_version: 2, sample_id: id + '_' + slot + '_1',
  timestamp: slot + 1000, sequence: 1, ph: 7.2, tds: 220,
  turbidity: 13, ...values,
})
const records = (slot=s) => Object.fromEntries(['N0','N1','N2'].map(id=>[id,node(id,slot)]))

test('reuses original dashboard shape for N0/N1/N2 and keeps acquisition time', () => {
  const m = records()
  const out = adaptEmulatorForLegacyDashboard({
    nodes: Object.fromEntries(Object.entries(m).map(([id,v])=>[id,{latest:v}])),
    history: { [s]: m },
    analysis: { status:'ANOMALI' },
  })
  assert.equal(out.nodes.N0.location, 'Hulu / Baseline')
  assert.equal(out.nodes.N1.location, 'Cabang Irigasi 1')
  assert.equal(out.nodes.N2.location, 'Cabang Irigasi 2')
  assert.equal(out.nodes.N0.lastSeen, s+1000)
  assert.equal(out.history[0].N1_tds, 220)
  assert.equal(out.history[0].N2_turbidity, 13)
  assert.equal(out.history[0].timestamp,s)
  assert.equal(out.firebaseStatus,'online')
  assert.equal(out.analysis,null)
  assert.equal(out.history[0].analysis,null)
})

test('incomplete/flagged data is absent rather than fabricated zeros', () => {
  const n0=node('N0',s,{ph:null,quality_flags:['PH_INVALID']})
  const n1=node('N1',s,{tds:-3})
  const m = { N0:n0, N1:n1 }
  const out=adaptEmulatorForLegacyDashboard({
    nodes:{N0:{latest:n0},N1:{latest:n1}},
    history:{[s]:m},
  })
  assert.equal(out.nodes.N0.ph,null)
  assert.equal(out.history[0].N0_ph,null)
  assert.equal(out.history[0].N1_tds,null)
  assert.equal(out.history[0].N2,null)
  assert.equal(out.history[0].N2_ph,null)
  assert.equal(out.nodes.N2.hasData,false)
  assert.equal(out.nodes.N2.ph,null)
})

test('history paging and timestamps match original dashboard expectation', () => {
  const history = {}
  for(let i=0;i<5;i++) history[s+i*300000] = records(s+i*300000)
  const out=adaptEmulatorForLegacyDashboard({history},3)
  assert.equal(out.history.length,3)
  assert.equal(out.history[0].timestamp,s+2*300000)
  assert.equal(out.history[2].timestamp,s+4*300000)
  assert.equal(out.hasMoreHistory,true)
})

test('empty and malformed inputs are handled without live database fallback', () => {
  const out=adaptEmulatorForLegacyDashboard({})
  assert.equal(out.history.length,0)
  assert.equal(out.nodes.N0.hasData,false)
  assert.equal(out.hasMoreHistory,false)
  assert.equal(out.analysis,null)
})

test('transport placeholder distinguishes connecting/error from online', () => {
  const none = { nodes: null, history: null, analysis: null }
  const loading = adaptEmulatorForLegacyDashboard({
    ...none, demoConnectionState: 'connecting',
  })
  assert.equal(loading.firebaseStatus, 'connecting')
  assert.equal(loading.history.length, 0)
  assert.equal(loading.nodes.N0.ph, null)

  const disconnected = adaptEmulatorForLegacyDashboard({
    ...none, demoConnectionState: 'error',
  })
  assert.equal(disconnected.firebaseStatus, 'error')
  assert.equal(disconnected.history.length, 0)
  assert.equal(disconnected.analysis, null)

  const restored = adaptEmulatorForLegacyDashboard({
    nodes: { N0: { latest: node('N0') } },
    history: { [s]: { N0: node('N0') } },
    analysis: null, operational_status: null,
  })
  assert.equal(restored.firebaseStatus, 'online')
  assert.equal(restored.nodes.N0.ph, 7.2)
})
