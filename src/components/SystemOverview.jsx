function SystemOverview({
  firebaseStatus,
  lastUpdate,
  nodes,
  historyCount = 0,
  demoMode = false
}) {

  const nodeList =
    nodes
      ? Object.values(nodes)
      : []


  const onlineCount =
    nodeList.filter(
      (node) =>
        node.status === 'Online'
    ).length


  const offlineCount =
    nodeList.filter(
      (node) =>
        node.status === 'Offline'
    ).length


  const noDataCount =
    nodeList.filter(
      (node) =>
        node.status === 'Tidak Ada Data'
    ).length


  const statusConfig = {

    connecting: {
      title: 'Menghubungkan...',
      label: 'Firebase',
      className:
        'border-amber-500/20 bg-amber-500/10 text-amber-300',
      dot:
        'bg-amber-400'
    },

    online: {
      title: 'Monitoring Aktif',
      label: 'Firebase Online',
      className:
        'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
      dot:
        'bg-emerald-400'
    },

    empty: {
      title: 'Database Kosong',
      label: 'Menunggu Data',
      className:
        'border-slate-700 bg-slate-800 text-slate-300',
      dot:
        'bg-slate-400'
    },

    error: {
      title: 'Koneksi Bermasalah',
      label: 'Firebase Error',
      className:
        'border-red-500/20 bg-red-500/10 text-red-300',
      dot:
        'bg-red-400'
    }

  }


  const current =
    demoMode && firebaseStatus === 'online'
      ? { ...statusConfig.online, label: 'Firebase Emulator' }
      : (statusConfig[firebaseStatus] ?? statusConfig.connecting)


  const formatUpdate = () => {

    if (!lastUpdate) {
      return 'Belum ada update'
    }


    return lastUpdate
      .toLocaleString(
        'id-ID',
        {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          day: '2-digit',
          month: 'short'
        }
      )

  }


  function SmallCard({
    title,
    value,
    note
  }) {

    return (

      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

        <p className="text-xs text-slate-500">
          {title}
        </p>

        <p className="mt-2 text-2xl font-semibold text-white">
          {value}
        </p>

        <p className="mt-1 text-xs text-slate-600">
          {note}
        </p>

      </div>

    )

  }


  return (

    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 md:p-6">


      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">


        <div>

          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Ringkasan Sistem
          </p>

          <h2 className="mt-2 text-2xl font-bold text-white">
            {current.title}
          </h2>

          <p className="mt-2 text-sm text-slate-400">
            Update terakhir: {formatUpdate()}
          </p>

        </div>


        <div
          className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${current.className}`}
        >

          <span
            className={`h-2 w-2 rounded-full ${current.dot}`}
          />

          {current.label}

        </div>


      </div>



      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <SmallCard
          title="Node Online"
          value={`${onlineCount} / 3`}
          note="Aktif berdasarkan timestamp"
        />

        <SmallCard
          title="Node Offline"
          value={`${offlineCount} / 3`}
          note="Melewati batas waktu"
        />

        <SmallCard
          title="Belum Ada Data"
          value={`${nodes ? noDataCount : 3} / 3`}
          note="Belum memiliki timestamp"
        />

        <SmallCard
          title="History Dimuat"
          value={historyCount}
          note="Slot waktu terbaru"
        />

      </div>


    </div>

  )

}


export default SystemOverview
