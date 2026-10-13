// Membaca CSV microSD ESP32 (dan ekspor JSON hardware_test) LANGSUNG di
// browser. File tidak diunggah ke mana pun dan Firebase tidak ditulis.
//
// Format firmware: timestamp,node,sequence,ph,tds,turbidity,rssi
// - timestamp: epoch UTC milidetik (detik juga diterima, otomatis ×1000)
//   atau teks tanggal "YYYY-MM-DD HH:MM[:SS]" (tanpa zona = WITA, UTC+8)
// - "NA"/kosong = nilai sensor tidak ada (TIDAK diubah menjadi 0)
// - pemisah koma, titik koma (Excel Indonesia, desimal koma) atau tab
//
// Satu slot history = 5 menit. Jika satu node punya beberapa baris di slot
// yang sama, baris PERTAMA (waktu terkecil) dipakai — sama dengan perekam
// history backend — dan sisanya dihitung sebagai "baris tambahan".
import {
  FIELD_NODE_IDS, FIELD_SLOT_MS, selectFieldHardwareExport,
} from './fieldHardwarePreview.js'

export const MAX_LOCAL_FILE_BYTES = 20_000_000
const MAX_ROWS = 500_000
const MIN_MS = 1_704_067_200_000 // 2024-01-01
const WITA_OFFSET_MS = 8 * 3_600_000
const MISSING = new Set(['', 'na', 'n/a', 'nan', 'null', 'none', 'missing', '-', '—'])

const COLUMN_ALIASES = {
  timestamp: ['timestamp', 'timestamp_ms', 'epoch_ms', 'time_ms', 'ts', 'epoch',
    'waktu', 'datetime', 'date_time', 'time', 'tanggal_waktu'],
  node: ['node', 'node_id', 'nodeid', 'id_node', 'titik'],
  sequence: ['sequence', 'seq', 'urutan', 'no'],
  ph: ['ph', 'ph_value', 'nilai_ph'],
  tds: ['tds', 'tds_ppm', 'ppm'],
  turbidity: ['turbidity', 'turb', 'ntu', 'turbidity_ntu', 'kekeruhan', 'turbiditas'],
  rssi: ['rssi', 'rssi_dbm', 'wifi_rssi'],
}

function normalizeHeader(cell) {
  return cell.trim().toLowerCase().replace(/^\ufeff/, '')
    .replace(/\s*\(.*\)\s*$/, '').replace(/[\s-]+/g, '_')
}

function detectSeparator(headerLine) {
  const counts = [';', ',', '\t'].map(sep => [sep, headerLine.split(sep).length - 1])
  counts.sort((a, b) => b[1] - a[1])
  return counts[0][1] > 0 ? counts[0][0] : ','
}

function splitLine(line, sep) {
  // CSV firmware tidak memakai tanda kutip, tetapi file yang pernah dibuka
  // di Excel bisa memakainya; dukung kutip sederhana.
  if (!line.includes('"')) return line.split(sep)
  const cells = []
  let current = ''
  let quoted = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { current += '"'; i += 1 } else quoted = !quoted
    } else if (ch === sep && !quoted) {
      cells.push(current); current = ''
    } else current += ch
  }
  cells.push(current)
  return cells
}

export function nodeFromFileName(fileName = '') {
  const match = /(?:^|[^a-z0-9])(n[012])(?:[^0-9]|$)/i.exec(fileName)
  return match ? match[1].toUpperCase() : null
}

function parseNumber(text, decimalComma) {
  const raw = String(text ?? '').trim()
  if (MISSING.has(raw.toLowerCase())) return null
  // "1.890,8" / "7,43" (Excel Indonesia) → 1890.8 / 7.43; "7.43" tetap.
  const cleaned = decimalComma && raw.includes(',')
    ? raw.replace(/\./g, '').replace(',', '.') : raw
  if (!/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(cleaned)) return null
  const value = Number(cleaned)
  return Number.isFinite(value) ? value : null
}

export function parseTimestamp(text) {
  const raw = String(text ?? '').trim()
  if (MISSING.has(raw.toLowerCase())) return null
  if (/^\d+(\.\d+)?$/.test(raw)) {
    const value = Number(raw)
    if (!Number.isFinite(value)) return null
    // < 1e11 → epoch detik; selain itu epoch milidetik.
    const ms = Math.round(value < 1e11 ? value * 1000 : value)
    return Number.isSafeInteger(ms) && ms >= MIN_MS ? ms : null
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?\s*(z|[+-]\d{2}:?\d{2})?$/i.exec(raw)
  if (!match) return null
  const [, y, mo, d, h, mi, s = '0', frac = '0', zone] = match
  let ms = Date.UTC(+y, +mo - 1, +d, +h, +mi, +s, Number(frac.padEnd(3, '0')))
  if (!zone) ms -= WITA_OFFSET_MS
  else if (zone.toLowerCase() !== 'z') {
    const sign = zone[0] === '-' ? -1 : 1
    const digits = zone.slice(1).replace(':', '')
    ms -= sign * (Number(digits.slice(0, 2)) * 3_600_000 + Number(digits.slice(2)) * 60_000)
  }
  return Number.isSafeInteger(ms) && ms >= MIN_MS ? ms : null
}

// Mengembalikan pembacaan mentah, BUKAN nilai yang sudah "diperbaiki".
export function parseSdCsv(text, { fileName = '' } = {}) {
  if (typeof text !== 'string') throw new Error('Isi CSV tidak terbaca.')
  const lines = text.replace(/^\ufeff/, '').split(/\r\n|\n|\r/)
  const headerIndex = lines.findIndex(line => line.trim() && !line.trim().startsWith('#'))
  if (headerIndex < 0) throw new Error(`${fileName || 'CSV'} kosong.`)
  const headerLine = lines[headerIndex]
  const sep = detectSeparator(headerLine)
  const decimalComma = sep === ';'
  const headers = splitLine(headerLine, sep).map(normalizeHeader)
  const columns = {}
  for (const [field, aliases] of Object.entries(COLUMN_ALIASES)) {
    const index = headers.findIndex(h => aliases.includes(h))
    if (index >= 0) columns[field] = index
  }
  if (columns.timestamp === undefined) {
    throw new Error(`${fileName || 'CSV'}: kolom timestamp tidak ditemukan. Header yang diharapkan: timestamp,node,sequence,ph,tds,turbidity,rssi`)
  }
  if (columns.ph === undefined && columns.tds === undefined && columns.turbidity === undefined) {
    throw new Error(`${fileName || 'CSV'}: kolom ph/tds/turbidity tidak ditemukan.`)
  }
  const fileNode = nodeFromFileName(fileName)
  const readings = []
  const skipped = []
  const headerKey = headers.join('|')
  for (let i = headerIndex + 1; i < lines.length; i += 1) {
    const line = lines[i]
    if (!line.trim() || line.trim().startsWith('#')) continue
    const cells = splitLine(line, sep)
    if (cells.map(normalizeHeader).join('|') === headerKey) continue // header berulang
    if (readings.length >= MAX_ROWS) {
      skipped.push({ line: i + 1, reason: 'TOO_MANY_ROWS' })
      break
    }
    const cell = field => columns[field] === undefined ? '' : cells[columns[field]]
    const timestamp = parseTimestamp(cell('timestamp'))
    if (timestamp === null) {
      skipped.push({ line: i + 1, reason: 'TIMESTAMP_INVALID' })
      continue
    }
    const nodeText = String(cell('node') ?? '').trim().toUpperCase()
    const node = FIELD_NODE_IDS.includes(nodeText) ? nodeText
      : (/^[012]$/.test(nodeText) ? 'N' + nodeText : (nodeText ? null : fileNode))
    if (!node) {
      skipped.push({ line: i + 1, reason: nodeText ? 'NODE_INVALID' : 'NODE_UNKNOWN' })
      continue
    }
    const reading = { node, timestamp }
    const sequence = parseNumber(cell('sequence'), false)
    if (sequence !== null && Number.isSafeInteger(sequence) && sequence >= 0) reading.sequence = sequence
    for (const sensor of ['ph', 'tds', 'turbidity']) {
      const value = parseNumber(cell(sensor), decimalComma)
      if (value !== null) reading[sensor] = value
    }
    const rssi = parseNumber(cell('rssi'), decimalComma)
    if (rssi !== null) reading.rssi = rssi
    reading.source_line = i + 1
    readings.push(reading)
  }
  return { readings, skipped, fileName }
}

function packetOf(reading) {
  const packet = { timestamp: reading.timestamp, node_id: reading.node }
  for (const key of ['sequence', 'ph', 'tds', 'turbidity', 'rssi']) {
    if (reading[key] !== undefined) packet[key] = reading[key]
  }
  return packet
}

const earlier = (a, b) => a.timestamp - b.timestamp || (a.sequence ?? 0) - (b.sequence ?? 0)

// Menyusun snapshot berbentuk hardware_test {nodes, history, analysis}.
// base (opsional) = hasil ekspor JSON yang dipilih bersamaan; slot yang
// sudah ada di base TIDAK ditimpa CSV.
export function readingsToHardwareSnapshot(readings, base = null) {
  const nodes = {}
  const history = {}
  for (const node of FIELD_NODE_IDS) nodes[node] = { latest: base?.nodes?.[node]?.latest ?? null }
  if (base?.history && typeof base.history === 'object') {
    for (const [slot, value] of Object.entries(base.history)) history[slot] = { ...value }
  }
  const stats = { rows: readings.length, slots: 0, extraInSlot: 0, perNode: {} }
  for (const node of FIELD_NODE_IDS) stats.perNode[node] = 0
  for (const reading of [...readings].sort(earlier)) {
    stats.perNode[reading.node] += 1
    const slot = String(Math.floor(reading.timestamp / FIELD_SLOT_MS) * FIELD_SLOT_MS)
    history[slot] ??= {}
    if (history[slot][reading.node]) stats.extraInSlot += 1
    else history[slot][reading.node] = packetOf(reading)
    const latest = nodes[reading.node].latest
    if (!latest || earlier(latest, reading) <= 0) nodes[reading.node].latest = packetOf(reading)
  }
  stats.slots = Object.keys(history).length
  return { nodes, history, analysis: base?.analysis ?? null, stats }
}

async function readText(file) {
  if (typeof file.text === 'function') return file.text()
  return new Response(file).text()
}

// Gabungkan beberapa file (CSV per node dan/atau satu ekspor JSON).
export async function loadLocalHardwareFiles(fileList) {
  const files = Array.from(fileList ?? [])
  if (!files.length) throw new Error('Tidak ada file yang dipilih.')
  const total = files.reduce((sum, f) => sum + (f.size ?? 0), 0)
  if (total > MAX_LOCAL_FILE_BYTES) throw new Error('Total ukuran file maksimal 20 MB.')
  let base = null
  const readings = []
  const skipped = []
  const names = []
  for (const file of files) {
    const name = file.name ?? 'file'
    names.push(name)
    const text = await readText(file)
    if (/\.json$/i.test(name)) {
      let parsed
      try {
        parsed = JSON.parse(text)
      } catch {
        throw new Error(`${name} bukan JSON yang valid.`)
      }
      if (base) throw new Error('Pilih maksimal satu file JSON.')
      base = selectFieldHardwareExport(parsed)
    } else if (/\.(csv|txt)$/i.test(name)) {
      const result = parseSdCsv(text, { fileName: name })
      readings.push(...result.readings)
      skipped.push(...result.skipped.map(s => ({ ...s, file: name })))
    } else {
      throw new Error(`${name}: hanya file .csv, .txt atau .json yang didukung.`)
    }
  }
  if (!base && !readings.length) {
    throw new Error('Tidak ada baris data valid di file yang dipilih' +
      (skipped.length ? ` (${skipped.length} baris dilewati, contoh: ${skipped[0].reason} baris ${skipped[0].line}).` : '.'))
  }
  const snapshot = readingsToHardwareSnapshot(readings, base)
  return {
    ...snapshot,
    fileNames: names,
    stats: { ...snapshot.stats, skipped: skipped.length, skippedSample: skipped.slice(0, 5) },
  }
}
