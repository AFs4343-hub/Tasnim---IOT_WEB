function IoTPerformancePanel({
  nodes,
  history = [],
  intervalMinutes = 5
}) {

  const nodeList = nodes
    ? Object.values(nodes)
    : []

  const onlineCount =
    nodeList.filter(
      (node) => node.status === 'Online'
    ).length

  const offlineCount =
    nodeList.filter(
      (node) => node.status === 'Offline'
    ).length

  const noDataCount =
    nodeList.filter(
      (node) => node.status === 'Tidak Ada Data'
    ).length

  function MetricCard({
    title,
    value,
    unit,
    note
  }) {

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

        <p className="text-xs text-slate-500">
          {title}
        </p>

        <div className="mt-2 flex items-end gap-1">

          <p className="text-2xl font-semibold text-white">
            {value}
          </p>

          {unit && (
            <span className="mb-1 text-sm text-slate-500">
              {unit}
            </span>
          )}

        </div>

        {note && (
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {note}
          </p>
        )}

      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="mb-6">

        <h2 className="text-xl font-bold">
          Kinerja Sistem IoT
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Pemantauan konektivitas node dan kesiapan
          evaluasi transmisi data.
        </p>

      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

        <MetricCard
          title="Node Online"
          value={onlineCount}
          unit="/ 3"
          note="Berdasarkan timestamp data terakhir."
        />

        <MetricCard
          title="Node Offline"
          value={offlineCount}
          unit="/ 3"
          note="Node yang melewati batas waktu pengiriman."
        />

        <MetricCard
          title="Belum Ada Data"
          value={nodes ? noDataCount : 3}
          unit="/ 3"
          note="Node yang belum memiliki timestamp pengiriman."
        />

        <MetricCard
          title="History Dimuat"
          value={history.length}
          note={`Jumlah slot waktu yang sedang dimuat. Interval target ${intervalMinutes} menit.`}
        />

      </div>

      <div className="mt-6">

        <p className="mb-3 text-sm font-semibold text-slate-300">
          Evaluasi Transmisi
        </p>

        <div className="grid gap-4 md:grid-cols-3">

          <MetricCard
            title="Transmission Success"
            value="—"
            note="Menunggu sequence ID dari ESP32."
          />

          <MetricCard
            title="Data Loss"
            value="—"
            note="Akan dihitung dari paket yang hilang berdasarkan sequence ID."
          />

          <MetricCard
            title="Latency"
            value="—"
            note="Menunggu metadata waktu pengiriman dan penerimaan."
          />

        </div>

      </div>

      <div className="mt-6 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">

        <p className="text-sm font-medium text-cyan-400">
          Panel evaluasi IoT siap
        </p>

        <p className="mt-1 text-xs leading-5 text-slate-400">
          Saat ESP32 mulai digunakan, panel ini dapat
          menghitung metrik transmisi berdasarkan metadata
          aktual. Untuk sekarang web hanya menampilkan
          metrik yang memang sudah dapat dihitung.
        </p>

      </div>

    </div>
  )
}

export default IoTPerformancePanel
