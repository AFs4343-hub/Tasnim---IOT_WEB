import test from 'node:test'
import assert from 'node:assert/strict'
import {
  evaluateOperationalAlerts, normalizeSupervisorStatus,
} from '../src/services/operationalMonitorDemo.js'
import { NODE_IDS } from '../src/services/hardwareV2View.js'

const now = 1_792_000_000_000
const currentSlot = Math.floor(now / 300000) * 300000
const node = (timestamp=now-60_000) => ({
  timestamp, ph:7,tds:220,turbidity:12,requiresReview:false,
})
const nodes = () => Object.fromEntries(NODE_IDS.map(k=>[k,node()]))
const status = (changes={}) => ({
  schema_version:1, state:'PROCESSED',error_code:'NONE',
  timestamp_ms:now-60_000,attempts:1,processed_count:2,
  recovered_count:0,deferred_count:0,would_process_count:0,
  source_root:'hardware_test',model_stage:'PROTOTYPE_SIMULATION',
  ...changes,
})

test('strictly allowlist worker status fields before display',()=>{
  assert.equal(normalizeSupervisorStatus(status()).state,'PROCESSED')
  assert.equal(normalizeSupervisorStatus(null),null)
  assert.equal(normalizeSupervisorStatus(status({password:'secret'})),null)
  assert.equal(normalizeSupervisorStatus(status({model_stage:'FIELD_CERTIFIED'})),null)
  assert.equal(normalizeSupervisorStatus(status({processed_count:-1})),null)
  assert.equal(normalizeSupervisorStatus(status({processed_count:NaN})),null)
  assert.equal(normalizeSupervisorStatus(status({timestamp_ms:'2026-10-12'})),null)
  assert.equal(normalizeSupervisorStatus(status({state:'WATER_SAFE'})),null)
})

test('no sensor history and no supervisor report never produce a false offline alarm',()=>{
  const out=evaluateOperationalAlerts(null,[],null,now)
  assert.equal(out.level,'normal')
  assert.equal(out.alerts.length,0)
  assert.deepEqual(out.missingNodes,['N0','N1','N2'])
  assert.equal(out.supervisor,null)
})

test('one delayed or still-open incomplete slot is not an alarm',()=>{
  const r=[
    {slot:currentSlot-300000,complete:false},
    {slot:currentSlot,complete:false},
  ]
  assert.equal(evaluateOperationalAlerts(nodes(),r,null,now).level,'normal')
  assert.equal(evaluateOperationalAlerts(nodes(),r,null,now+300001).level,'normal')
})

test('two closed incomplete slots after grace produce a warning, not fabricated data',()=>{
  const r=[
    {slot:currentSlot-1_200_000,complete:false},
    {slot:currentSlot-900_000,complete:false},
    {slot:currentSlot-600_000,complete:true},
    {slot:currentSlot-300_000,complete:false},
  ]
  const out=evaluateOperationalAlerts(nodes(),r,status(),now)
  assert.equal(out.level,'warning')
  assert.equal(out.waitingSlots,2)
  assert.ok(out.alerts.some(a=>a.code==='INCOMPLETE_SLOTS'))
})

test('stale acquisition timestamps matter more than receive time',()=>{
  const n=nodes()
  n.N1=node(now-16*60_000)
  const out=evaluateOperationalAlerts(n,[],null,now)
  assert.equal(out.level,'warning')
  assert.ok(out.alerts.some(a=>a.code==='NODE_DELAY_N1'))
  n.N1=node(now-31*60_000)
  const overdue=evaluateOperationalAlerts(n,[],null,now)
  assert.equal(overdue.level,'review')
  assert.ok(overdue.alerts.some(a=>a.code==='NODE_STALE_N1'))
})

test('quality flags or clock in the future require review but do not assert water unsafe',()=>{
  const n=nodes()
  n.N0.requiresReview=true
  n.N2=node(now+120000)
  const out=evaluateOperationalAlerts(n,[],null,now)
  assert.equal(out.level,'review')
  assert.ok(out.alerts.some(a=>a.code==='NODE_QUALITY_N0'))
  assert.ok(out.alerts.some(a=>a.code==='NODE_CLOCK_N2'))
  assert.ok(out.alerts.every(a=>!a.message.includes('air tidak aman')))
})

test('supervisor lock wait and old report are not alarms; recent failure is',()=>{
  const waiting=evaluateOperationalAlerts(nodes(),[],status({state:'WAITING_LOCK',error_code:'LEASE_BUSY'}),now)
  assert.equal(waiting.level,'normal')
  const old=evaluateOperationalAlerts(nodes(),[],status({
    state:'FAILED',error_code:'WORKER_ERROR',timestamp_ms:now-16*60_000,
  }),now)
  assert.equal(old.level,'normal')
  const active=evaluateOperationalAlerts(nodes(),[],status({
    state:'REVIEW_REQUIRED',error_code:'REVIEW_REQUIRED',
  }),now)
  assert.equal(active.level,'review')
  assert.ok(active.alerts.some(a=>a.code==='SUPERVISOR_REVIEW_REQUIRED'))
})

test('malformed status and invalid evaluation clock fail closed',()=>{
  assert.equal(evaluateOperationalAlerts(nodes(),[],{state:'FAILED',error_message:'secret'},now).level,'normal')
  assert.throws(()=>evaluateOperationalAlerts(nodes(),[],null,0),/invalid_now_ms/)
})
