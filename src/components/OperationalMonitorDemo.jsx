import { useEffect, useMemo, useState } from 'react'
import { evaluateOperationalAlerts } from '../services/operationalMonitorDemo.js'
import { wita } from '../services/hardwareV2View.js'

const STATE_LABELS = {
  PROCESSED: 'Siklus memproses data',
  IDLE: 'Tidak ada slot baru',
  PREVIEW: 'Pratinjau tanpa penulisan',
  WAITING_LOCK: 'Menunggu kunci worker',
  REVIEW_REQUIRED: 'Memerlukan pemeriksaan',
  RETRY_EXHAUSTED: 'Batas retry tercapai',
  FAILED: 'Siklus gagal',
}

export default function OperationalMonitorDemo({ nodes, rows, rawStatus }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])
  const report = useMemo(
    () => evaluateOperationalAlerts(nodes, rows, rawStatus, now),
    [nodes, rows, rawStatus, now],
  )
  const status = report.supervisor
  return <section aria-label="Status AI Supervisor dan peringatan operasional demo"
    className="rounded-2xl border border-slate-700 bg-slate-900 p-5 text-white">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">Supervisor AI & pemeriksaan data</h2>
      <span className="rounded-lg bg-slate-800 px-3 py-1 text-xs text-cyan-300">
        DEMO — hanya pemantauan, tanpa notifikasi
      </span>
    </div>
    <p className="mt-2 text-xs text-slate-400">
      Ini status rekayasa sistem, bukan hasil diagnosis kualitas air.
      Tidak ada worker otomatis yang diaktifkan oleh tampilan ini.
    </p>
    {status ? <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
      <p>Status: <strong>{STATE_LABELS[status.state]}</strong></p>
      <p>Waktu laporan: {wita(status.timestamp_ms)}</p>
      <p>Slot diproses: {status.processed_count} · Dipulihkan: {status.recovered_count}</p>
      <p>Slot tertunda: {status.deferred_count} · Percobaan: {status.attempts}</p>
    </div> : <p className="mt-4 text-sm text-slate-300">
      Belum ada catatan Supervisor di Emulator ini. Itu bukan berarti
      Supervisor sedang berjalan atau mengalami kegagalan.
    </p>}
    {status && now - status.timestamp_ms > 15 * 60_000
      && <p className="mt-2 text-xs text-amber-300">
        Laporan terakhir sudah lebih dari 15 menit. Belum ada jadwal
        otomatis yang diwajibkan dalam demo ini.
      </p>}
    <div className="mt-4 border-t border-slate-700 pt-3">
      <p className="font-semibold">
        Peringatan rekayasa: {report.level === 'normal'
          ? 'Tidak ada kondisi yang memenuhi ambang peringatan'
          : report.alerts.length + ' kondisi perlu ditinjau'}
      </p>
      {report.alerts.length
        ? <ul className="mt-2 space-y-1 text-sm">
          {report.alerts.map(a => <li key={a.code}
            className={a.severity === 'review' ? 'text-rose-300' : 'text-amber-300'}>
            {a.message}
          </li>)}
        </ul>
        : <p className="mt-2 text-xs text-slate-400">
          Satu slot terlambat, slot yang belum ditutup, serta masa
          tunggu 5 menit setelah slot berakhir tidak otomatis memicu alarm.
        </p>}
      {report.missingNodes.length > 0 && <p className="mt-3 text-xs text-slate-400">
        Data awal belum tersedia untuk {report.missingNodes.join(', ')}.
        Belum dapat disimpulkan node tersebut offline.
      </p>}
    </div>
  </section>
}
