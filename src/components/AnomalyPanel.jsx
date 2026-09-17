function AnomalyPanel({ analysis }) {

  if (!analysis) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <p className="text-sm text-slate-400">
          Sistem Peringatan Dini
        </p>

        <h2 className="mt-1 text-2xl font-bold">
          Status Anomali
        </h2>

        <p className="mt-4 text-slate-400">
          Menunggu hasil analisis AI...
        </p>
      </div>
    )
  }

  const isNormal =
    analysis.status === 'NORMAL'

  const rf =
    analysis.random_forest || {}

  const iso =
    analysis.isolation_forest || {}

  const zscore =
    analysis.dominant_zscore || {}

  const confidence =
    typeof rf.confidence === 'number'
      ? (rf.confidence * 100).toFixed(1)
      : '-'

  const zValue =
    typeof zscore.zscore === 'number'
      ? zscore.zscore.toFixed(2)
      : '-'

  const isoScore =
    typeof iso.decision_score === 'number'
      ? iso.decision_score.toFixed(3)
      : '-'

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">

        <div>
          <p className="text-sm text-slate-400">
            Sistem Peringatan Dini
          </p>

          <h2 className="mt-1 text-2xl font-bold">
            Status Anomali
          </h2>
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
            className={`text-xl font-bold ${
              isNormal
                ? 'text-emerald-400'
                : 'text-amber-400'
            }`}
          >
            {isNormal
              ? 'NORMAL'
              : 'ANOMALI'}
          </span>

        </div>

      </div>


      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Lokasi
          </p>

          <p className="mt-2 text-2xl font-bold">
            {analysis.location || '-'}
          </p>

        </div>


        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Confidence RF
          </p>

          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {confidence}%
          </p>

        </div>


        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Random Forest
          </p>

          <p className="mt-2 text-lg font-bold">
            {rf.prediction || '-'}
          </p>

        </div>


        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Isolation Forest
          </p>

          <p
            className={`mt-2 text-lg font-bold ${
              iso.is_anomaly
                ? 'text-amber-400'
                : 'text-emerald-400'
            }`}
          >
            {typeof iso.is_anomaly === 'boolean'
              ? iso.is_anomaly
                ? 'ANOMALI'
                : 'NORMAL'
              : '-'}
          </p>

          <p className="mt-1 text-xs text-slate-500">
            Score: {isoScore}
          </p>

        </div>

      </div>


      <div className="mt-4 grid gap-4 md:grid-cols-2">

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Z-score Dominan
          </p>

          <p className="mt-2 text-lg font-bold">
            {zscore.parameter || '-'}
            {' · '}
            {zscore.node || '-'}
          </p>

          <p className="mt-1 text-cyan-400">
            z = {zValue}
          </p>

        </div>


        <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Interpretasi AI
          </p>

          <p className="mt-2 text-sm text-slate-300">

            {isNormal
              ? 'Random Forest tidak mendeteksi anomali pada data terbaru.'
              : `Random Forest mendeteksi anomali pada ${analysis.location || 'node tertentu'}.`
            }

          </p>

          <p className="mt-2 text-xs text-slate-500">
            Model prototype berbasis data simulasi.
          </p>

        </div>

      </div>

    </div>
  )
}

export default AnomalyPanel
