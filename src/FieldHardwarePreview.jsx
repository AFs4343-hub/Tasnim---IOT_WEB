import { useState } from 'react'
import App from './App.jsx'
import { selectFieldHardwareExport } from './services/fieldHardwarePreview.js'

// Development-only field preview; opening the dashboard does NOT change
// Firebase Authentication or Database Rules. A local JSON export can be
// inspected without any account or network write.
export default function FieldHardwarePreview() {
  const [localData, setLocalData] = useState(null)
  const [error, setError] = useState('')
  const readLocalExport = async event => {
    const file = event.target.files?.[0]
    if (!file) return
    setError('')
    try {
      if (file.size > 2_000_000 || !file.name.toLowerCase().endsWith('.json')) {
        throw new Error('Pilih file JSON hardware_test maksimal 2 MB.')
      }
      const parsed = JSON.parse(await file.text())
      setLocalData(selectFieldHardwareExport(parsed))
    } catch (cause) {
      setError(cause instanceof SyntaxError
        ? 'File bukan JSON yang valid.'
        : cause instanceof Error ? cause.message : 'Gagal membaca file.')
    }
    event.target.value = ''
  }

  return <div className="min-h-screen bg-slate-950 text-white">
    <section className="border-b border-amber-600/40 bg-slate-900 px-5 py-3">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div>
          <strong className="text-amber-300">PRATINJAU DATA ALAT — TANPA LOGIN WEBSITE</strong>
          <p className="mt-1 max-w-2xl text-xs text-slate-300">
            {localData
              ? 'Sedang menampilkan file JSON lokal, bukan data Firebase real-time.'
              : 'Membaca hardware_test dari Firebase jika Rules mengizinkan. Tidak ada penulisan database.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="cursor-pointer rounded-lg border border-slate-600 px-3 py-2 hover:border-cyan-400">
            Lihat ekspor JSON lokal
            <input aria-label="Pilih ekspor JSON hardware_test"
              type="file" accept=".json,application/json"
              className="sr-only" onChange={readLocalExport}/>
          </label>
          {localData && <button type="button"
            className="rounded-lg border border-slate-600 px-3 py-2"
            onClick={() => { setLocalData(null); setError('') }}>
            Kembali ke Firebase langsung
          </button>}
        </div>
      </div>
      {error && <p role="alert" className="mx-auto mt-2 max-w-7xl text-sm text-rose-300">{error}</p>}
    </section>
    <App fieldSnapshot={localData ?? undefined}/>
  </div>
}
