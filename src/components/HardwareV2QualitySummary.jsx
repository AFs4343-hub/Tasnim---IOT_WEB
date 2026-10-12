import { useEffect, useMemo, useState } from 'react'
import { hardwareReadiness, NODE_IDS } from '../services/hardwareV2View'

const LABELS = {
  RECENT: 'Data terbaru tersedia',
  STALE: 'Data lebih dari 10 menit',
  REVIEW: 'Sensor/flag perlu review',
  NO_DATA: 'Belum ada data valid',
  CLOCK_INVALID: 'Waktu pengukuran tidak valid',
}

export default function HardwareV2QualitySummary({ nodes, rows = [] }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])
  const report = useMemo(() => hardwareReadiness(nodes, rows, now), [nodes, rows, now])

  return (
    <section className="mb-6 rounded-2xl border border-slate-700 bg-slate-900 p-5" aria-label="Kesiapan data hardware V2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Kesiapan data tiga node</h2>
          <p className="mt-1 text-xs text-slate-400">
            Status rekayasa data, bukan sertifikasi akurasi sensor atau keamanan air.
          </p>
        </div>
        <p className="rounded-lg bg-slate-950 px-3 py-2 text-sm text-cyan-300">
          {report.recentNodes}/3 node terbaru
        </p>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {NODE_IDS.map(node => (
          <div key={node} className="rounded-xl border border-slate-800 bg-slate-950 p-3">
            <p className="font-semibold">{node}</p>
            <p className="mt-1 text-sm text-slate-300">{LABELS[report.states[node]]}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm text-slate-300">
        Slot lengkap: <strong>{report.completeSlots}</strong> dari {report.totalSlots} ditampilkan.
        {report.incompleteSlots > 0 && <span className="ml-2 text-amber-300">
          {report.incompleteSlots} slot tidak lengkap/perlu review.
        </span>}
      </p>
    </section>
  )
}
