function ConnectionStateBanner({
  firebaseStatus,
  hasNodes,
  historyCount = 0
}) {

  if (firebaseStatus === 'online') {
    return null
  }


  const reloadPage = () => {
    window.location.reload()
  }


  if (firebaseStatus === 'connecting') {

    return (

      <section className="mb-8 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-5">

        <div className="flex items-center gap-3">

          <span className="h-3 w-3 animate-pulse rounded-full bg-cyan-400" />

          <div>

            <p className="font-medium text-cyan-300">
              Menghubungkan ke Firebase
            </p>

            <p className="mt-1 text-sm text-slate-500">
              Mengambil data node dan history...
            </p>

          </div>

        </div>

      </section>

    )

  }


  if (firebaseStatus === 'error') {

    return (

      <section className="mb-8 rounded-2xl border border-red-500/20 bg-red-500/5 p-5">

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

          <div>

            <p className="font-semibold text-red-300">
              Koneksi Firebase bermasalah
            </p>

            <p className="mt-1 text-sm leading-6 text-slate-500">
              Periksa koneksi internet, konfigurasi .env,
              firebase.js, databaseURL, dan Realtime Database Rules.
            </p>

          </div>

          <button
            type="button"
            onClick={reloadPage}
            className="w-fit rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-200 transition hover:bg-red-500/20"
          >
            Coba Lagi
          </button>

        </div>

      </section>

    )

  }


  if (firebaseStatus === 'empty') {

    return (

      <section className="mb-8 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">

        <p className="font-medium text-amber-300">
          Firebase terhubung, tetapi data node belum tersedia
        </p>

        <p className="mt-1 text-sm leading-6 text-slate-500">
          Tidak masalah untuk tahap pengembangan. Begitu ESP32 mengirim data,
          monitoring akan muncul otomatis.
          {historyCount > 0
            ? ` History tetap tersedia sebanyak ${historyCount} slot waktu.`
            : ''}
        </p>

      </section>

    )

  }


  if (!hasNodes) {

    return (

      <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-5">

        <p className="text-sm text-slate-400">
          Menunggu data sistem.
        </p>

      </section>

    )

  }


  return null

}


export default ConnectionStateBanner
