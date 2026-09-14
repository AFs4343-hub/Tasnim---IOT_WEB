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


  function getSignalQuality(rssi) {

    if (
      rssi === null ||
      rssi === undefined ||
      Number.isNaN(Number(rssi))
    ) {
      return {
        label: 'Belum Ada Data',
        className: 'text-slate-500'
      }
    }

    const value = Number(rssi)

    if (value >= -60) {
      return {
        label: 'Baik',
        className: 'text-emerald-400'
      }
    }

    if (value >= -70) {
      return {
        label: 'Cukup',
        className: 'text-cyan-400'
      }
    }

    if (value >= -80) {
      return {
        label: 'Lemah',
        className: 'text-amber-400'
      }
    }

    return {
      label: 'Sangat Lemah',
      className: 'text-red-400'
    }
  }


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


  function SignalCard({
    nodeId,
    node
  }) {

    const hasRSSI =
      node?.rssi !== null &&
      node?.rssi !== undefined &&
      !Number.isNaN(Number(node.rssi))

    const quality =
      getSignalQuality(
        hasRSSI
          ? node.rssi
          : null
      )

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

        <div className="flex items-start justify-between gap-3">

          <div>

            <p className="text-xs text-slate-500">
              {nodeId}
            </p>

            <p className="mt-1 text-sm font-medium text-slate-300">
              Koneksi Wi-Fi
            </p>

          </div>

          <span
            className={`text-xs font-semibold ${quality.className}`}
          >
            {quality.label}
          </span>

        </div>


        <div className="mt-4 flex items-end gap-1">

          <p className="text-2xl font-semibold text-white">
            {hasRSSI
              ? Number(node.rssi)
              : '—'}
          </p>

          {hasRSSI && (
            <span className="mb-1 text-sm text-slate-500">
              dBm
            </span>
          )}

        </div>


        <p className="mt-3 border-t border-slate-800 pt-3 text-xs text-slate-500">
          Sequence terakhir:{' '}
          <span className="text-slate-300">
            {node?.sequence ?? '—'}
          </span>
        </p>

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
          Pemantauan konektivitas node dan kesiapan evaluasi transmisi data.
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

        <p className="text-sm font-semibold text-slate-300">
          Kualitas Sinyal Wi-Fi
        </p>

        <p className="mt-1 text-xs text-slate-500">
          RSSI diperoleh dari koneksi Wi-Fi masing-masing ESP32.
        </p>

        <div className="mt-3 grid gap-4 md:grid-cols-3">

          <SignalCard
            nodeId="N0"
            node={nodes?.N0}
          />

          <SignalCard
            nodeId="N1"
            node={nodes?.N1}
          />

          <SignalCard
            nodeId="N2"
            node={nodes?.N2}
          />

        </div>

      </div>


      <div className="mt-6">

        <p className="mb-3 text-sm font-semibold text-slate-300">
          Evaluasi Transmisi
        </p>

        <div className="grid gap-4 md:grid-cols-3">

          <MetricCard
            title="Transmission Success"
            value="—"
            note="Menunggu rangkaian sequence ID aktual dari ESP32."
          />

          <MetricCard
            title="Data Loss"
            value="—"
            note="Akan dihitung dari sequence ID yang hilang."
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
          RSSI dan sequence akan muncul otomatis ketika ESP32 mulai
          mengirim metadata tersebut. Metrik transmisi lain tetap
          ditampilkan sebagai belum tersedia sampai data aktual mencukupi.
        </p>

      </div>

    </div>
  )
}

export default IoTPerformancePanel
