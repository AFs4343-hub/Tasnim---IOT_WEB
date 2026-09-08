function NodeCard({ node, location, ph, tds, turbidity, status }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">

      <div className="mb-6 flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">{location}</p>

          <h2 className="mt-1 text-3xl font-bold text-white">
            {node}
          </h2>
        </div>

        <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-400">
          {status}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">

        <div className="rounded-xl bg-slate-950 p-4">
          <p className="text-xs text-slate-500">
            pH
          </p>

          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {ph}
          </p>
        </div>

        <div className="rounded-xl bg-slate-950 p-4">
          <p className="text-xs text-slate-500">
            TDS
          </p>

          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {tds}
          </p>

          <p className="text-xs text-slate-500">
            ppm
          </p>
        </div>

        <div className="rounded-xl bg-slate-950 p-4">
          <p className="text-xs text-slate-500">
            Turbiditas
          </p>

          <p className="mt-2 text-2xl font-bold text-cyan-400">
            {turbidity}
          </p>

          <p className="text-xs text-slate-500">
            NTU
          </p>
        </div>

      </div>

    </div>
  )
}

export default NodeCard