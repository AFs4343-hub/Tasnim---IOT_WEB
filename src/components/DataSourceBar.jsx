import { DATA_SOURCES, SOURCE_HARDWARE } from '../services/dataSource.js'

// Bilah pemilih sumber data di atas dashboard. Tidak ada login dan tidak
// ada penulisan database; file lokal hanya dibaca di browser.
function DataSourceBar({
  source,
  onSourceChange,
  localFile,
  onOpenFiles,
  onCloseFile,
  loading = false,
  error = '',
}) {
  const fileStats = localFile?.stats

  return (
    <section className="relative border-b border-slate-800 bg-slate-900 px-4 py-3 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Sumber data">
          <span className="mr-1 text-xs font-semibold uppercase tracking-widest text-slate-500">
            Sumber data
          </span>
          {Object.values(DATA_SOURCES).map(option => {
            const active = !localFile && source === option.id
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={active}
                title={option.description}
                onClick={() => onSourceChange(option.id)}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? option.id === SOURCE_HARDWARE
                      ? 'border-emerald-500/60 bg-emerald-500/15 text-emerald-300'
                      : 'border-violet-500/60 bg-violet-500/15 text-violet-300'
                    : 'border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                {option.id === SOURCE_HARDWARE ? 'Data Alat (Firebase)' : 'Simulasi'}
              </button>
            )
          })}

          <label
            className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
              localFile
                ? 'border-amber-500/60 bg-amber-500/15 text-amber-300'
                : 'border-slate-700 text-slate-300 hover:border-cyan-400'
            }`}
          >
            {loading ? 'Membaca file…' : 'Buka CSV/JSON'}
            <input
              aria-label="Pilih file CSV microSD atau ekspor JSON hardware_test"
              type="file"
              multiple
              accept=".csv,.txt,.json,text/csv,application/json"
              className="sr-only"
              disabled={loading}
              onChange={event => {
                const files = event.target.files
                if (files?.length) onOpenFiles(files)
                event.target.value = ''
              }}
            />
          </label>

          {localFile && (
            <button
              type="button"
              onClick={onCloseFile}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500"
            >
              Tutup file
            </button>
          )}
        </div>

        <p className="text-xs leading-5 text-slate-400">
          {localFile
            ? <>
                File: <span className="text-amber-200">{localFile.fileNames.join(', ')}</span>
                {fileStats && <> — {fileStats.rows} baris, {fileStats.slots} slot 5 menit
                  {fileStats.extraInSlot > 0 && <>, {fileStats.extraInSlot} baris tambahan di slot yang sama</>}
                  {fileStats.skipped > 0 && <>, {fileStats.skipped} baris dilewati</>}</>}
              </>
            : source === SOURCE_HARDWARE
              ? <>Real-time dari Firebase <code>hardware_test</code> (hanya baca)</>
              : <>Data dummy <code>simulation</code> — bukan hasil pengukuran</>}
        </p>
      </div>

      {error && (
        <p role="alert" className="mx-auto mt-2 max-w-7xl text-sm text-rose-300">
          {error}
        </p>
      )}
    </section>
  )
}

export default DataSourceBar
