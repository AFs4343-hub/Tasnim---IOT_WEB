import { useMemo, useState } from 'react'

function HistoryExplorer({ data = [] }) {
  const [nodeFilter, setNodeFilter] = useState('ALL')
  const [parameterFilter, setParameterFilter] = useState('ALL')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const parameterInfo = {
    ph: { label: 'pH', unit: '' },
    tds: { label: 'TDS', unit: 'ppm' },
    turbidity: { label: 'Turbiditas', unit: 'NTU' }
  }

  const rows = useMemo(() => {
    return data
      .flatMap((record) =>
        ['N0', 'N1', 'N2'].map((node) => {
          const timestamp = Number(record.timestamp)

          return {
            timestamp,
            date: new Date(timestamp).toLocaleDateString('id-ID', {
              day: '2-digit',
              month: 'short',
              year: 'numeric'
            }),
            time: new Date(timestamp).toLocaleTimeString('id-ID', {
              hour: '2-digit',
              minute: '2-digit'
            }),
            node,
            ph: Number(record[`${node}_ph`]),
            tds: Number(record[`${node}_tds`]),
            turbidity: Number(record[`${node}_turbidity`]),
            status: 'Belum Dianalisis'
          }
        })
      )
      .sort((a, b) => b.timestamp - a.timestamp)
  }, [data])

  const filteredRows = useMemo(() => {
    const startTimestamp = startDate
      ? new Date(`${startDate}T00:00:00`).getTime()
      : null

    const endTimestamp = endDate
      ? new Date(`${endDate}T23:59:59.999`).getTime()
      : null

    return rows.filter((row) => {
      const matchNode =
        nodeFilter === 'ALL' || row.node === nodeFilter

      const matchStart =
        startTimestamp === null || row.timestamp >= startTimestamp

      const matchEnd =
        endTimestamp === null || row.timestamp <= endTimestamp

      return matchNode && matchStart && matchEnd
    })
  }, [rows, nodeFilter, startDate, endDate])

  const resetFilters = () => {
    setNodeFilter('ALL')
    setParameterFilter('ALL')
    setStartDate('')
    setEndDate('')
  }

  const escapeCsv = (value) => {
    const text = String(value ?? '')

    if (
      text.includes(',') ||
      text.includes('"') ||
      text.includes('\n')
    ) {
      return `"${text.replace(/"/g, '""')}"`
    }

    return text
  }

  const exportCsv = () => {
    if (filteredRows.length === 0) return

    let headers
    let csvRows

    if (parameterFilter === 'ALL') {
      headers = [
        'Waktu',
        'Node',
        'pH',
        'TDS_ppm',
        'Turbiditas_NTU',
        'Status'
      ]

      csvRows = filteredRows.map((row) => [
        new Date(row.timestamp).toISOString(),
        row.node,
        row.ph,
        row.tds,
        row.turbidity,
        row.status
      ])
    } else {
      const info = parameterInfo[parameterFilter]

      headers = [
        'Waktu',
        'Node',
        'Parameter',
        'Nilai',
        'Satuan',
        'Status'
      ]

      csvRows = filteredRows.map((row) => [
        new Date(row.timestamp).toISOString(),
        row.node,
        info.label,
        row[parameterFilter],
        info.unit,
        row.status
      ])
    }

    const csvContent = [headers, ...csvRows]
      .map((row) => row.map(escapeCsv).join(','))
      .join('\n')

    const blob = new Blob([csvContent], {
      type: 'text/csv;charset=utf-8;'
    })

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const today = new Date().toISOString().slice(0, 10)

    link.href = url
    link.download = `tasnim-history-${today}.csv`

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const formatValue = (value, parameter) => {
    if (
      value === null ||
      value === undefined ||
      Number.isNaN(Number(value))
    ) {
      return '—'
    }

    if (parameter === 'ph') {
      return Number(value).toFixed(2)
    }

    return Number(value).toFixed(1)
  }

  const nodeStyle = {
    N0: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300',
    N1: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    N2: 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
      {/* HEADER */}
      <div className="border-b border-slate-800 px-5 py-5 md:px-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">
              Riwayat Data
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Rekaman pengukuran kualitas air berdasarkan waktu dan node.
            </p>
          </div>

          <button
            type="button"
            onClick={exportCsv}
            disabled={filteredRows.length === 0}
            className="w-fit rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* FILTER */}
      <div className="border-b border-slate-800 bg-slate-950/40 p-5">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div>
            <label className="mb-2 block text-xs font-medium text-slate-500">
              Node
            </label>

            <select
              value={nodeFilter}
              onChange={(event) => setNodeFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            >
              <option value="ALL">Semua Node</option>
              <option value="N0">N0 — Hulu</option>
              <option value="N1">N1 — Cabang 1</option>
              <option value="N2">N2 — Cabang 2</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-slate-500">
              Parameter
            </label>

            <select
              value={parameterFilter}
              onChange={(event) => setParameterFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            >
              <option value="ALL">Semua Parameter</option>
              <option value="ph">pH</option>
              <option value="tds">TDS</option>
              <option value="turbidity">Turbiditas</option>
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-slate-500">
              Tanggal Awal
            </label>

            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            />
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-slate-500">
              Tanggal Akhir
            </label>

            <input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={resetFilters}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-slate-800"
            >
              Reset Filter
            </button>
          </div>
        </div>
      </div>

      {/* SUMMARY */}
      <div className="flex flex-col gap-2 border-b border-slate-800 px-5 py-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-semibold text-slate-300">
            {filteredRows.length}
          </span>{' '}
          baris ditampilkan dari {rows.length} baris.
        </p>

        <p>Data terbaru ditampilkan paling atas.</p>
      </div>

      {/* DESKTOP TABLE */}
      <div className="hidden overflow-x-auto md:block">
        {filteredRows.length === 0 ? (
          <div className="flex min-h-48 items-center justify-center">
            <p className="text-sm text-slate-500">
              Tidak ada data yang sesuai dengan filter.
            </p>
          </div>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-950 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-5 py-4">Waktu</th>
                <th className="px-5 py-4">Node</th>

                {parameterFilter === 'ALL' ? (
                  <>
                    <th className="px-5 py-4">pH</th>
                    <th className="px-5 py-4">TDS</th>
                    <th className="px-5 py-4">Turbiditas</th>
                  </>
                ) : (
                  <>
                    <th className="px-5 py-4">Parameter</th>
                    <th className="px-5 py-4">Nilai</th>
                  </>
                )}

                <th className="px-5 py-4">Status</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800">
              {filteredRows.map((row, index) => (
                <tr
                  key={`${row.timestamp}-${row.node}-${index}`}
                  className="bg-slate-900 transition hover:bg-slate-800/60"
                >
                  <td className="whitespace-nowrap px-5 py-4">
                    <p className="font-medium text-slate-200">
                      {row.time}
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      {row.date}
                    </p>
                  </td>

                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-semibold ${nodeStyle[row.node]}`}
                    >
                      {row.node}
                    </span>
                  </td>

                  {parameterFilter === 'ALL' ? (
                    <>
                      <td className="px-5 py-4 font-mono font-semibold text-slate-100">
                        {formatValue(row.ph, 'ph')}
                      </td>

                      <td className="px-5 py-4">
                        <p className="font-mono font-semibold text-slate-100">
                          {formatValue(row.tds, 'tds')}
                        </p>
                        <p className="mt-1 text-[11px] text-slate-600">
                          ppm
                        </p>
                      </td>

                      <td className="px-5 py-4">
                        <p className="font-mono font-semibold text-slate-100">
                          {formatValue(row.turbidity, 'turbidity')}
                        </p>
                        <p className="mt-1 text-[11px] text-slate-600">
                          NTU
                        </p>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-5 py-4 text-slate-300">
                        {parameterInfo[parameterFilter].label}
                      </td>

                      <td className="px-5 py-4">
                        <p className="font-mono font-semibold text-slate-100">
                          {formatValue(
                            row[parameterFilter],
                            parameterFilter
                          )}
                        </p>

                        {parameterInfo[parameterFilter].unit && (
                          <p className="mt-1 text-[11px] text-slate-600">
                            {parameterInfo[parameterFilter].unit}
                          </p>
                        )}
                      </td>
                    </>
                  )}

                  <td className="px-5 py-4">
                    <span className="inline-flex rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300">
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* MOBILE CARDS */}
      <div className="grid gap-3 p-4 md:hidden">
        {filteredRows.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">
            Tidak ada data yang sesuai dengan filter.
          </p>
        ) : (
          filteredRows.map((row, index) => (
            <div
              key={`${row.timestamp}-${row.node}-${index}`}
              className="rounded-xl border border-slate-800 bg-slate-950 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-slate-200">
                    {row.time}
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    {row.date}
                  </p>
                </div>

                <span
                  className={`rounded-lg border px-2.5 py-1 text-xs font-semibold ${nodeStyle[row.node]}`}
                >
                  {row.node}
                </span>
              </div>

              {parameterFilter === 'ALL' ? (
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-slate-900 p-3">
                    <p className="text-[10px] text-slate-500">pH</p>
                    <p className="mt-1 font-mono font-semibold text-slate-100">
                      {formatValue(row.ph, 'ph')}
                    </p>
                  </div>

                  <div className="rounded-lg bg-slate-900 p-3">
                    <p className="text-[10px] text-slate-500">TDS</p>
                    <p className="mt-1 font-mono font-semibold text-slate-100">
                      {formatValue(row.tds, 'tds')}
                    </p>
                    <p className="text-[10px] text-slate-600">ppm</p>
                  </div>

                  <div className="rounded-lg bg-slate-900 p-3">
                    <p className="text-[10px] text-slate-500">Turb.</p>
                    <p className="mt-1 font-mono font-semibold text-slate-100">
                      {formatValue(row.turbidity, 'turbidity')}
                    </p>
                    <p className="text-[10px] text-slate-600">NTU</p>
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-lg bg-slate-900 p-3">
                  <p className="text-xs text-slate-500">
                    {parameterInfo[parameterFilter].label}
                  </p>

                  <p className="mt-1 font-mono text-lg font-semibold text-slate-100">
                    {formatValue(
                      row[parameterFilter],
                      parameterFilter
                    )}
                    {parameterInfo[parameterFilter].unit
                      ? ` ${parameterInfo[parameterFilter].unit}`
                      : ''}
                  </p>
                </div>
              )}

              <div className="mt-4 border-t border-slate-800 pt-3">
                <span className="inline-flex rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300">
                  {row.status}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default HistoryExplorer
