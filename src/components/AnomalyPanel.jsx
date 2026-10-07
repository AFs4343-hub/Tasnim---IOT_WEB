function AnomalyPanel({
  analysis,
  syncState = 'UNKNOWN',
  dataQuality = null
}) {

  // =========================================
  // STATE
  // =========================================

  const isSynced =
    syncState === 'SYNCED'

  const isPending =
    syncState === 'PENDING'

  const isStale =
    syncState === 'STALE'

  const isIncomplete =
    syncState === 'INCOMPLETE_DATA'

  const isNoHistory =
    syncState === 'NO_HISTORY'

  const isNoAnalysis =
    syncState === 'NO_ANALYSIS'


  const critical =
    Array.isArray(
      dataQuality?.critical
    )
      ? dataQuality.critical
      : []


  const warnings =
    Array.isArray(
      dataQuality?.warnings
    )
      ? dataQuality.warnings
      : []


  // =========================================
  // LABEL ISSUE
  // =========================================

  const componentLabel = (
    component
  ) => {

    const labels = {
      node: 'Node',
      ph: 'pH',
      tds: 'TDS',
      turbidity: 'Turbiditas',
      timestamp: 'Timestamp',
      rssi: 'RSSI',
      sequence: 'Sequence',
      record: 'Data'
    }

    return (
      labels[component]
      ?? component
      ?? 'Komponen'
    )

  }


  const reasonLabel = (
    reason
  ) => {

    const labels = {
      NODE_MISSING:
        'node tidak tersedia',

      SENSOR_MISSING:
        'data sensor tidak tersedia',

      INVALID_SENSOR:
        'nilai sensor tidak valid',

      INVALID_TIME:
        'waktu pengukuran tidak valid',

      TELEMETRY_MISSING:
        'telemetri tidak tersedia',

      MISSING:
        'data tidak tersedia'
    }

    return (
      labels[reason]
      ?? reason
      ?? 'bermasalah'
    )

  }


  const issueText = (
    issue
  ) => {

    const location =
      issue?.node
        ? `${issue.node} — `
        : ''

    return (
      `${location}`
      + `${componentLabel(issue?.component)}: `
      + `${reasonLabel(issue?.reason)}`
    )

  }


  // =========================================
  // BELUM ADA ANALYSIS
  // =========================================

  if (
    !analysis
    && !isIncomplete
  ) {

    const waitingTitle =
      isNoHistory
        ? 'BELUM ADA DATA'
        : isNoAnalysis
          ? 'MENUNGGU ANALISIS'
          : 'MENUNGGU AI'


    const waitingMessage =
      isNoHistory
        ? 'Belum ada slot pengukuran yang dapat diperiksa.'
        : isNoAnalysis
          ? 'Data sensor tersedia, tetapi hasil analisis AI belum tersedia.'
          : 'Menunggu hasil analisis AI...'


    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

        <p className="text-sm text-slate-400">
          Sistem Peringatan Dini
        </p>

        <div className="mt-1 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

          <h2 className="text-2xl font-bold">
            Status Anomali
          </h2>

          <span className="text-lg font-bold text-slate-400">
            {waitingTitle}
          </span>

        </div>

        <p className="mt-4 text-slate-400">
          {waitingMessage}
        </p>

      </div>
    )

  }


  // =========================================
  // STATUS ANALISIS
  // =========================================

  const isNormal =
    isSynced
    && analysis?.status === 'NORMAL'


  const isAnomaly =
    isSynced
    && analysis?.status === 'ANOMALI'


  const statusLabel =
    isIncomplete
      ? 'ANALISIS DITUNDA'
      : isPending
        ? 'MENUNGGU ANALISIS'
        : isStale
          ? 'AI TIDAK SINKRON'
          : syncState === 'UNKNOWN'
            ? 'STATUS TIDAK DIKETAHUI'
            : isNormal
              ? 'NORMAL'
              : isAnomaly
                ? 'ANOMALI'
                : isNoAnalysis
                  ? 'MENUNGGU ANALISIS'
                  : 'STATUS TIDAK DIKETAHUI'


  const statusColor =
    isNormal
      ? 'text-emerald-400'
      : isAnomaly
        ? 'text-amber-400'
        : isIncomplete
          ? 'text-amber-300'
          : isPending
            ? 'text-cyan-400'
            : 'text-slate-400'


  const dotColor =
    isNormal
      ? 'bg-emerald-400'
      : isAnomaly
        ? 'bg-amber-400'
        : isIncomplete
          ? 'bg-amber-300'
          : isPending
            ? 'bg-cyan-400'
            : 'bg-slate-500'


  // =========================================
  // ANALYSIS DATA
  // =========================================

  const rf =
    analysis?.random_forest || {}

  const iso =
    analysis?.isolation_forest || {}

  const zscore =
    analysis?.dominant_zscore || {}


  const confidence =
    typeof rf.confidence === 'number'
      ? (
          rf.confidence * 100
        ).toFixed(1)
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

      {/* HEADER */}

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
            className={`h-3 w-3 rounded-full ${dotColor}`}
          />

          <span
            className={`text-xl font-bold ${statusColor}`}
          >
            {statusLabel}
          </span>

        </div>

      </div>


      {/* =====================================
          CRITICAL DATA QUALITY
      ====================================== */}

      {isIncomplete && (

        <div className="mt-5 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">

          <p className="font-semibold text-amber-300">
            Data kritis belum lengkap
          </p>

          <p className="mt-1 text-sm text-slate-400">
            AI multi-node dilewati untuk slot pengukuran ini.
            Data sensor lain yang tersedia tetap disimpan dan
            dapat ditampilkan.
          </p>


          {critical.length > 0 && (

            <div className="mt-4 space-y-2">

              {critical.map(
                (issue, index) => (

                  <div
                    key={
                      `${issue?.node ?? 'SYSTEM'}-${issue?.component}-${index}`
                    }
                    className="rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-300"
                  >
                    ⚠ {issueText(issue)}
                  </div>

                )
              )}

            </div>

          )}

        </div>

      )}


      {/* =====================================
          TELEMETRY WARNING
      ====================================== */}

      {warnings.length > 0 && (

        <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">

          <p className="font-semibold text-cyan-300">
            Peringatan telemetri
          </p>

          <p className="mt-1 text-sm text-slate-400">
            Masalah berikut tidak menghentikan analisis kualitas air
            selama data kritis sensor tetap lengkap.
          </p>


          <div className="mt-3 space-y-1">

            {warnings.map(
              (issue, index) => (

                <p
                  key={
                    `${issue?.node ?? 'SYSTEM'}-${issue?.component}-${index}`
                  }
                  className="text-sm text-slate-400"
                >
                  • {issueText(issue)}
                </p>

              )
            )}

          </div>

        </div>

      )}


      {/* =====================================
          AI SYNC WARNING
      ====================================== */}

      {!isSynced && !isIncomplete && (

        <div className="mt-5 rounded-xl border border-slate-700 bg-slate-950 p-4">

          <p className="font-semibold text-slate-200">

            {isPending
              ? 'Data sensor terbaru sedang menunggu analisis AI.'
              : isStale
                ? 'Hasil AI belum sinkron dengan data sensor terbaru.'
                : 'Sinkronisasi hasil AI belum dapat diverifikasi.'}

          </p>

          <p className="mt-1 text-sm text-slate-500">
            Detail di bawah merupakan hasil analisis terakhir
            yang tersimpan dan belum tentu mewakili data sensor terbaru.
          </p>

        </div>

      )}


      {/* =====================================
          LAST AI RESULT
      ====================================== */}

      {analysis && (

        <>

          {isIncomplete && (

            <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Hasil AI terakhir sebelum slot tidak lengkap
            </p>

          )}


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
                  typeof iso.is_anomaly === 'boolean'
                    ? iso.is_anomaly
                      ? 'text-amber-400'
                      : 'text-emerald-400'
                    : 'text-slate-400'
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

                {isIncomplete
                  ? 'Slot terbaru tidak dianalisis karena data kritis belum lengkap.'
                  : isNormal
                    ? 'Random Forest tidak mendeteksi anomali pada data terbaru.'
                    : isAnomaly
                      ? `Random Forest mendeteksi anomali pada ${analysis.location || 'node tertentu'}.`
                      : 'Hasil yang ditampilkan merupakan analisis terakhir yang tersimpan.'}

              </p>

              <p className="mt-2 text-xs text-slate-500">
                Model prototype berbasis data simulasi.
              </p>

            </div>

          </div>

        </>

      )}

    </div>
  )
}

export default AnomalyPanel
