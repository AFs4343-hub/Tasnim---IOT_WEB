function AnomalyPanel({
  status = 'Normal',
  node = '-',
  score = null,
  message = 'Belum ada anomali yang terdeteksi.'
}) {
  const isNormal = status === 'Normal'

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">

        <div>
          <p className="text-sm text-slate-400">
            Sistem Peringatan Dini
          </p>

          <h2 className="mt-1 text-2xl font-bold">
            Status Anomali
          </h2>

          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            {message}
          </p>
        </div>

        <div className="flex items-center gap-3">

          <span
            className={`h-3 w-3 rounded-full ${
              isNormal
                ? 'bg-emerald-400'
                : 'bg-amber-400'
            }`}
          />

          <span
            className={`text-lg font-semibold ${
              isNormal
                ? 'text-emerald-400'
                : 'text-amber-400'
            }`}
          >
            {status}
          </span>

        </div>

      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">

        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Node Terdeteksi
          </p>

          <p className="mt-2 text-2xl font-bold text-white">
            {node}
          </p>

        </div>

        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Anomaly Score
          </p>

          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {score === null ? '-' : score}
          </p>

        </div>

      </div>

    </div>
  )
}

export default AnomalyPanel