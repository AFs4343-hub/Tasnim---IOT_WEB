// Pilihan sumber data dashboard. Tidak ada penulisan Firebase di sini.
//
//   hardware_test : data alat asli ESP32 N0/N1/N2 (default)
//   simulation    : data dummy dari iot/simulator.py
//
// Urutan prioritas: pilihan terakhir pengguna (localStorage) →
// VITE_TASNIM_DATA_SOURCE → VITE_TASNIM_FIELD_PREVIEW=YES (lama) →
// hardware_test. tasnim.config.json tetap dipakai backend Python.
export const SOURCE_HARDWARE = 'hardware_test'
export const SOURCE_SIMULATION = 'simulation'

export const DATA_SOURCES = Object.freeze({
  [SOURCE_HARDWARE]: Object.freeze({
    id: SOURCE_HARDWARE,
    root: 'hardware_test',
    label: 'Data Alat',
    description: 'ESP32 N0/N1/N2 dari Firebase hardware_test',
  }),
  [SOURCE_SIMULATION]: Object.freeze({
    id: SOURCE_SIMULATION,
    root: 'simulation',
    label: 'Simulasi',
    description: 'Data dummy dari simulator (bukan hasil pengukuran)',
  }),
})

const STORAGE_KEY = 'tasnim.dataSource'

export function isDataSource(value) {
  return value === SOURCE_HARDWARE || value === SOURCE_SIMULATION
}

export function resolveInitialDataSource({ env = {}, stored = null } = {}) {
  if (isDataSource(stored)) return stored
  if (isDataSource(env.VITE_TASNIM_DATA_SOURCE)) return env.VITE_TASNIM_DATA_SOURCE
  if (env.VITE_TASNIM_FIELD_PREVIEW === 'YES') return SOURCE_HARDWARE
  return SOURCE_HARDWARE
}

// localStorage bisa tidak tersedia (mode privat, iframe, test); pilihan
// sumber data hanya kenyamanan, jadi kegagalan diabaikan.
export function readStoredDataSource() {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) ?? null
  } catch {
    return null
  }
}

export function storeDataSource(value) {
  if (!isDataSource(value)) return
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, value)
  } catch {
    // abaikan
  }
}
