function HistoryTable({ data }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">

      {/* Header */}
      <div className="border-b border-slate-800 p-6">
        <h2 className="text-xl font-bold">
          Riwayat Pengukuran
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Rekaman data kualitas air dari setiap node.
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">

          <thead className="bg-slate-950 text-xs uppercase text-slate-500">

            <tr>
              <th className="px-6 py-4">
                Waktu
              </th>

              <th className="px-6 py-4">
                Node
              </th>

              <th className="px-6 py-4">
                pH
              </th>

              <th className="px-6 py-4">
                TDS
              </th>

              <th className="px-6 py-4">
                Turbiditas
              </th>

              <th className="px-6 py-4">
                Status
              </th>
            </tr>

          </thead>


          <tbody className="divide-y divide-slate-800">

            {data.map((item, index) => (

              <tr
                key={index}
                className="transition hover:bg-slate-800/50"
              >

                <td className="px-6 py-4 text-sm text-slate-400">
                  {item.time}
                </td>

                <td className="px-6 py-4">
                  <span className="font-semibold text-cyan-400">
                    {item.node}
                  </span>
                </td>

                <td className="px-6 py-4">
                  {item.ph}
                </td>

                <td className="px-6 py-4">
                  {item.tds} ppm
                </td>

                <td className="px-6 py-4">
                  {item.turbidity} NTU
                </td>

                <td className="px-6 py-4">

                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      item.status === 'Normal'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-amber-500/10 text-amber-400'
                    }`}
                  >
                    {item.status}
                  </span>

                </td>

              </tr>

            ))}

          </tbody>

        </table>
      </div>

    </div>
  )
}

export default HistoryTable