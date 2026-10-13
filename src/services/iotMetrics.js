// Evaluasi transmisi dari history yang sedang dimuat (tanpa data karangan).
//
// Data alat: key history = slot 5 menit. Dalam satu sesi pengukuran (slot
// berurutan, jeda <= 15 menit), setiap node diharapkan mengisi setiap slot.
// Kelengkapan = slot terisi / slot yang diharapkan; data loss = sisanya.
// Data simulasi (key = waktu kirim, bukan slot) dihitung per record.
export const NODE_IDS = ['N0', 'N1', 'N2']
const SLOT_MS = 300_000
const SESSION_GAP_MS = 15 * 60_000

const hasNodeData = point => Boolean(point) && typeof point === 'object' &&
  ['ph', 'tds', 'turbidity'].some(key => point[key] !== null && point[key] !== undefined)

export function computeTransmissionStats(history = []) {
  const rows = (Array.isArray(history) ? history : [])
    .filter(row => Number.isFinite(row?.timestamp))
    .sort((a, b) => a.timestamp - b.timestamp)
  if (!rows.length) return null

  const slotMode = rows.every(row => row.timestamp % SLOT_MS === 0)
  let expected = 0
  let sessions = 0
  if (slotMode) {
    let start = null
    let previous = null
    for (const row of rows) {
      if (previous === null || row.timestamp - previous > SESSION_GAP_MS) {
        if (start !== null) expected += (previous - start) / SLOT_MS + 1
        start = row.timestamp
        sessions += 1
      }
      previous = row.timestamp
    }
    expected += (previous - start) / SLOT_MS + 1
  } else {
    expected = rows.length
    sessions = 1
  }

  const perNode = {}
  for (const node of NODE_IDS) {
    const received = rows.filter(row => hasNodeData(row[node])).length
    perNode[node] = {
      received,
      expected,
      missing: Math.max(0, expected - received),
      successPct: expected ? (received / expected) * 100 : null,
    }
  }
  const totalExpected = expected * NODE_IDS.length
  const totalReceived = NODE_IDS.reduce((sum, node) => sum + perNode[node].received, 0)
  const completeSlots = rows.filter(row => NODE_IDS.every(node => hasNodeData(row[node]))).length
  return {
    mode: slotMode ? 'SLOT_5_MIN' : 'RECORD',
    sessions,
    expectedPerNode: expected,
    totalExpected,
    totalReceived,
    successPct: totalExpected ? (totalReceived / totalExpected) * 100 : null,
    lossPct: totalExpected ? ((totalExpected - totalReceived) / totalExpected) * 100 : null,
    completeSlots,
    perNode,
  }
}
