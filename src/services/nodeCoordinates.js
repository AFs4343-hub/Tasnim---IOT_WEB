// Koordinat node untuk peta. Sumber (prioritas):
// 1. latitude/longitude di paket latest alat (jika firmware GPS mengirimnya)
// 2. VITE_TASNIM_NODE_COORDS di .env, contoh:
//    VITE_TASNIM_NODE_COORDS=N0:0.5512,123.0601;N1:0.5520,123.0610;N2:0.5530,123.0590
const validLat = v => Number.isFinite(v) && v >= -90 && v <= 90
const validLng = v => Number.isFinite(v) && v >= -180 && v <= 180

export function parseNodeCoords(text = '') {
  const result = {}
  for (const part of String(text ?? '').split(';')) {
    const match = /^\s*(N[012])\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/i.exec(part)
    if (!match) continue
    const lat = Number(match[2])
    const lng = Number(match[3])
    if (validLat(lat) && validLng(lng)) result[match[1].toUpperCase()] = { lat, lng }
  }
  return result
}

export function resolveNodeCoords(nodeId, node, configured = {}) {
  const lat = Number(node?.latitude)
  const lng = Number(node?.longitude)
  if (node?.latitude != null && node?.longitude != null && validLat(lat) && validLng(lng)) {
    return { lat, lng, source: 'GPS alat' }
  }
  const fixed = configured[nodeId]
  return fixed ? { ...fixed, source: 'Konfigurasi' } : { lat: null, lng: null, source: null }
}
