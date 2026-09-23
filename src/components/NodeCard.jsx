function NodeCard({
  node,
  location,
  ph,
  tds,
  turbidity,
  status,
  lastSeen
}) {

  const isOnline = status === 'Online'

  const formatLastSeen = () => {

    if (!lastSeen) {
      return 'Belum ada timestamp'
    }

    return new Date(lastSeen).toLocaleString('id-ID', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }


  return (

    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      {/* HEADER */}

      <div className="flex items-start justify-between">

        <div>

          <p className="text-sm text-slate-400">
            Node
          </p>

          <h3 className="mt-1 text-2xl font-bold">
            {node}
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            {location}
          </p>

        </div>


        <div
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            isOnline
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-red-500/10 text-red-400'
          }`}
        >
          {status}
        </div>

      </div>



      {/* SENSOR */}

      <div className="mt-6 grid gap-3">


        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            pH
          </p>

          <p className="mt-1 text-2xl font-semibold">
            {ph ?? '—'}
          </p>

        </div>



        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            TDS
          </p>

          <p className="mt-1 text-2xl font-semibold">

            {tds ?? '—'}

            <span className="ml-1 text-sm font-normal text-slate-500">
              ppm
            </span>

          </p>

        </div>



        <div className="rounded-xl bg-slate-950 p-4">

          <p className="text-xs text-slate-500">
            Turbiditas
          </p>

          <p className="mt-1 text-2xl font-semibold">

            {turbidity ?? '—'}

            <span className="ml-1 text-sm font-normal text-slate-500">
              NTU
            </span>

          </p>

        </div>


      </div>



      {/* LAST SEEN */}

      <div className="mt-5 border-t border-slate-800 pt-4">

        <p className="text-xs text-slate-500">
          Data terakhir
        </p>

        <p className="mt-1 text-sm text-slate-300">
          {formatLastSeen()}
        </p>

      </div>


    </div>

  )
}

export default NodeCard