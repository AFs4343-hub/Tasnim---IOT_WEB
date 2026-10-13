// Semua waktu di dashboard ditampilkan dalam WITA (UTC+8, Asia/Makassar),
// apa pun zona waktu komputer yang membuka website. Angka timestamp di
// Firebase tetap epoch UTC milidetik (waktu ukur), tidak ditambah 8 jam.
export const WITA_TZ = 'Asia/Makassar'

const formatters = new Map()

function formatter(key, options) {
  if (!formatters.has(key)) {
    formatters.set(key, new Intl.DateTimeFormat('id-ID', { timeZone: WITA_TZ, ...options }))
  }
  return formatters.get(key)
}

const valid = ms => Number.isFinite(Number(ms)) && ms !== null && ms !== ''

export function witaTime(ms, { seconds = false } = {}) {
  if (!valid(ms)) return '—'
  return formatter(seconds ? 'ts' : 't', {
    hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}),
  }).format(new Date(Number(ms)))
}

export function witaDate(ms, { year = false } = {}) {
  if (!valid(ms)) return '—'
  return formatter(year ? 'dy' : 'd', {
    day: '2-digit', month: 'short', ...(year ? { year: 'numeric' } : {}),
  }).format(new Date(Number(ms)))
}

export function witaDateTime(ms, { seconds = true } = {}) {
  if (!valid(ms)) return '—'
  return `${witaDate(ms)}, ${witaTime(ms, { seconds })} WITA`
}

// Kunci hari WITA (YYYY-MM-DD) untuk memisahkan hari/sesi.
export function witaDayKey(ms) {
  if (!valid(ms)) return ''
  return formatter('key', { year: 'numeric', month: '2-digit', day: '2-digit' })
    .formatToParts(new Date(Number(ms)))
    .filter(p => p.type !== 'literal').reverse().map(p => p.value).join('-')
}

// Batas awal/akhir hari WITA untuk filter tanggal (input "YYYY-MM-DD").
export function witaDayStartMs(day) {
  return day ? new Date(`${day}T00:00:00+08:00`).getTime() : null
}

export function witaDayEndMs(day) {
  return day ? new Date(`${day}T23:59:59.999+08:00`).getTime() : null
}
