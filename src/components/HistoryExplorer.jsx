import {
  useEffect,
  useMemo,
  useState
} from 'react'


const PAGE_SIZE = 10


function HistoryExplorer({
  data = []
}) {

  const [statusFilter, setStatusFilter] =
    useState('ALL')

  const [locationFilter, setLocationFilter] =
    useState('ALL')

  const [startDate, setStartDate] =
    useState('')

  const [endDate, setEndDate] =
    useState('')

  const [page, setPage] =
    useState(1)

  const [
    expandedTimestamp,
    setExpandedTimestamp
  ] = useState(null)


  // =========================================
  // RECORD
  // 1 timestamp = 1 record
  // =========================================

  const records = useMemo(() => {

    return [...data].sort(
      (a, b) =>
        b.timestamp - a.timestamp
    )

  }, [data])


  // =========================================
  // FILTER
  // =========================================

  const filteredRecords = useMemo(() => {

    const startTimestamp =
      startDate
        ? new Date(
            `${startDate}T00:00:00`
          ).getTime()
        : null

    const endTimestamp =
      endDate
        ? new Date(
            `${endDate}T23:59:59.999`
          ).getTime()
        : null


    return records.filter((record) => {

      const status =
        record?.analysis?.status
        ?? 'BELUM_DIANALISIS'

      const location =
        record?.analysis?.location
        ?? '-'


      const matchStatus =
        statusFilter === 'ALL'
        || (
          statusFilter === 'BELUM_DIANALISIS'
          && !record?.analysis
        )
        || status === statusFilter


      const matchLocation =
        locationFilter === 'ALL'
        || location === locationFilter


      const matchStart =
        startTimestamp === null
        || record.timestamp >= startTimestamp


      const matchEnd =
        endTimestamp === null
        || record.timestamp <= endTimestamp


      return (
        matchStatus
        && matchLocation
        && matchStart
        && matchEnd
      )

    })

  }, [
    records,
    statusFilter,
    locationFilter,
    startDate,
    endDate
  ])


  // Balik ke halaman pertama ketika filter berubah
  useEffect(() => {

    setPage(1)
    setExpandedTimestamp(null)

  }, [
    statusFilter,
    locationFilter,
    startDate,
    endDate
  ])


  // =========================================
  // PAGINATION
  // =========================================

  const totalPages = Math.max(
    1,
    Math.ceil(
      filteredRecords.length
      / PAGE_SIZE
    )
  )


  useEffect(() => {

    if (page > totalPages) {
      setPage(totalPages)
    }

  }, [
    page,
    totalPages
  ])


  const pageRecords =
    filteredRecords.slice(
      (page - 1) * PAGE_SIZE,
      page * PAGE_SIZE
    )


  // =========================================
  // FORMAT
  // =========================================

  const formatNumber = (
    value,
    digits = 2
  ) => {

    if (
      value === null
      || value === undefined
      || Number.isNaN(Number(value))
    ) {
      return '—'
    }

    return Number(value)
      .toFixed(digits)

  }


  const formatConfidence = (
    value
  ) => {

    if (
      value === null
      || value === undefined
      || Number.isNaN(Number(value))
    ) {
      return '—'
    }

    return (
      Number(value) * 100
    ).toFixed(1) + '%'
  }


  const formatDate = (
    timestamp
  ) => {

    const date =
      new Date(timestamp)

    return {
      date:
        date.toLocaleDateString(
          'id-ID',
          {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
          }
        ),

      time:
        date.toLocaleTimeString(
          'id-ID',
          {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          }
        )
    }

  }


  // =========================================
  // CSV
  // =========================================

  const escapeCsv = (
    value
  ) => {

    const text =
      String(value ?? '')

    if (
      text.includes(',')
      || text.includes('"')
      || text.includes('\n')
    ) {

      return (
        `"${text.replace(
          /"/g,
          '""'
        )}"`
      )

    }

    return text
  }


  const exportCsv = () => {

    if (
      filteredRecords.length === 0
    ) {
      return
    }


    const headers = [

      'Timestamp',
      'Waktu',

      'Data_Source',
      'Mode',

      'N0_pH',
      'N0_TDS_ppm',
      'N0_Turbidity_NTU',
      'N0_RSSI_dBm',
      'N0_Sequence',

      'N1_pH',
      'N1_TDS_ppm',
      'N1_Turbidity_NTU',
      'N1_RSSI_dBm',
      'N1_Sequence',

      'N2_pH',
      'N2_TDS_ppm',
      'N2_Turbidity_NTU',
      'N2_RSSI_dBm',
      'N2_Sequence',

      'AI_Status',
      'AI_Location',

      'RF_Prediction',
      'RF_Confidence',

      'IF_Is_Anomaly',
      'IF_Decision_Score',

      'Z_Parameter',
      'Z_Node',
      'Z_Score',

      'Model_Version'
    ]


    const csvRows =
      filteredRecords.map(
        (record) => {

          const analysis =
            record?.analysis ?? {}

          const rf =
            analysis?.random_forest
            ?? {}

          const iso =
            analysis?.isolation_forest
            ?? {}

          const z =
            analysis?.dominant_zscore
            ?? {}

          const meta =
            record?.meta ?? {}


          return [

            record.timestamp,

            new Date(
              record.timestamp
            ).toISOString(),

            meta.data_source
              ?? analysis.data_source
              ?? 'LEGACY',

            meta.mode ?? '',


            record?.N0?.ph,
            record?.N0?.tds,
            record?.N0?.turbidity,
            record?.N0?.rssi,
            record?.N0?.sequence,


            record?.N1?.ph,
            record?.N1?.tds,
            record?.N1?.turbidity,
            record?.N1?.rssi,
            record?.N1?.sequence,


            record?.N2?.ph,
            record?.N2?.tds,
            record?.N2?.turbidity,
            record?.N2?.rssi,
            record?.N2?.sequence,


            analysis.status
              ?? 'BELUM_DIANALISIS',

            analysis.location
              ?? '-',


            rf.prediction
              ?? '',

            rf.confidence
              ?? '',


            iso.is_anomaly
              ?? '',

            iso.decision_score
              ?? '',


            z.parameter
              ?? '',

            z.node
              ?? '',

            z.zscore
              ?? '',


            analysis.model_version
              ?? ''

          ]

        }
      )


    const csvContent =
      [
        headers,
        ...csvRows
      ]
        .map(
          (row) =>
            row
              .map(escapeCsv)
              .join(',')
        )
        .join('\n')


    const blob =
      new Blob(
        [csvContent],
        {
          type:
            'text/csv;charset=utf-8;'
        }
      )


    const url =
      URL.createObjectURL(blob)

    const link =
      document.createElement('a')

    const today =
      new Date()
        .toISOString()
        .slice(0, 10)


    link.href = url

    link.download =
      `tasnim-history-${today}.csv`

    document.body
      .appendChild(link)

    link.click()

    document.body
      .removeChild(link)

    URL.revokeObjectURL(url)

  }


  // =========================================
  // RESET
  // =========================================

  const resetFilters = () => {

    setStatusFilter('ALL')
    setLocationFilter('ALL')
    setStartDate('')
    setEndDate('')
    setPage(1)
    setExpandedTimestamp(null)

  }


  // =========================================
  // STATUS BADGE
  // =========================================

  const StatusBadge = ({
    status
  }) => {

    if (
      status === 'ANOMALI'
    ) {

      return (
        <span className="inline-flex rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-300">
          ANOMALI
        </span>
      )

    }


    if (
      status === 'NORMAL'
    ) {

      return (
        <span className="inline-flex rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-300">
          NORMAL
        </span>
      )

    }


    return (
      <span className="inline-flex rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-400">
        BELUM DIANALISIS
      </span>
    )

  }


  // =========================================
  // DETAIL NODE
  // =========================================

  const NodeDetail = ({
    node,
    values
  }) => {

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

        <p className="font-bold text-white">
          {node}
        </p>

        <div className="mt-3 grid grid-cols-2 gap-x-5 gap-y-2 text-sm">

          <span className="text-slate-500">
            pH
          </span>

          <span className="text-right text-slate-200">
            {formatNumber(
              values?.ph,
              2
            )}
          </span>


          <span className="text-slate-500">
            TDS
          </span>

          <span className="text-right text-slate-200">
            {formatNumber(
              values?.tds,
              1
            )} ppm
          </span>


          <span className="text-slate-500">
            Turbiditas
          </span>

          <span className="text-right text-slate-200">
            {formatNumber(
              values?.turbidity,
              1
            )} NTU
          </span>


          <span className="text-slate-500">
            RSSI
          </span>

          <span className="text-right text-slate-200">
            {values?.rssi ?? '—'} dBm
          </span>


          <span className="text-slate-500">
            Sequence
          </span>

          <span className="text-right text-slate-200">
            {values?.sequence ?? '—'}
          </span>

        </div>

      </div>
    )

  }


  // =========================================
  // DETAIL RECORD
  // =========================================

  const DetailPanel = ({
    record
  }) => {

    const analysis =
      record?.analysis ?? {}

    const rf =
      analysis?.random_forest ?? {}

    const iso =
      analysis?.isolation_forest ?? {}

    const z =
      analysis?.dominant_zscore ?? {}

    const meta =
      record?.meta ?? {}


    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">

        <div className="grid gap-4 md:grid-cols-3">

          <NodeDetail
            node="N0"
            values={record.N0}
          />

          <NodeDetail
            node="N1"
            values={record.N1}
          />

          <NodeDetail
            node="N2"
            values={record.N2}
          />

        </div>


        <div className="mt-4 grid gap-4 md:grid-cols-2">

          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Analisis AI
            </p>


            <div className="mt-3 space-y-2 text-sm">

              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Status
                </span>

                <span className="font-medium text-slate-200">
                  {analysis.status ?? '—'}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Lokasi
                </span>

                <span className="font-medium text-slate-200">
                  {analysis.location ?? '—'}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Random Forest
                </span>

                <span className="text-right font-medium text-slate-200">
                  {rf.prediction ?? '—'}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  RF Confidence
                </span>

                <span className="font-medium text-cyan-400">
                  {formatConfidence(
                    rf.confidence
                  )}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Isolation Forest
                </span>

                <span
                  className={
                    iso.is_anomaly
                      ? 'font-medium text-amber-400'
                      : 'font-medium text-emerald-400'
                  }
                >
                  {
                    typeof iso.is_anomaly
                    === 'boolean'
                      ? iso.is_anomaly
                        ? 'ANOMALI'
                        : 'NORMAL'
                      : '—'
                  }
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  IF Score
                </span>

                <span className="font-medium text-slate-200">
                  {formatNumber(
                    iso.decision_score,
                    4
                  )}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Z-score Dominan
                </span>

                <span className="text-right font-medium text-slate-200">
                  {
                    z.parameter
                      ? `${z.parameter} · ${z.node}`
                      : '—'
                  }
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Nilai Z
                </span>

                <span className="font-medium text-cyan-400">
                  {formatNumber(
                    z.zscore,
                    2
                  )}
                </span>
              </div>

            </div>

          </div>


          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">

            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Metadata
            </p>


            <div className="mt-3 space-y-2 text-sm">

              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Sumber Data
                </span>

                <span className="font-medium text-slate-200">
                  {
                    meta.data_source
                    ?? analysis.data_source
                    ?? 'LEGACY'
                  }
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Mode
                </span>

                <span className="font-medium text-slate-200">
                  {meta.mode ?? '—'}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Model
                </span>

                <span className="font-medium text-slate-200">
                  {analysis.model_version ?? '—'}
                </span>
              </div>


              <div className="flex justify-between gap-4">
                <span className="text-slate-500">
                  Tahap Model
                </span>

                <span className="text-right font-medium text-slate-200">
                  {analysis.model_stage ?? '—'}
                </span>
              </div>

            </div>

          </div>

        </div>

      </div>
    )

  }


  // =========================================
  // UI
  // =========================================

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">


      {/* HEADER */}

      <div className="border-b border-slate-800 px-5 py-5 md:px-6">

        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">

          <div>

            <h2 className="text-xl font-bold text-white">
              Riwayat Data
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Satu baris mewakili satu waktu pengukuran lengkap N0, N1, N2 dan hasil analisis AI.
            </p>

          </div>


          <button
            type="button"
            onClick={exportCsv}
            disabled={
              filteredRecords.length === 0
            }
            className="w-fit rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Export CSV
          </button>

        </div>

      </div>


      {/* FILTER */}

      <div className="border-b border-slate-800 bg-slate-950/40 p-5">

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">


          <div>

            <label className="mb-2 block text-xs font-medium text-slate-500">
              Status
            </label>

            <select
              value={statusFilter}
              onChange={
                (event) =>
                  setStatusFilter(
                    event.target.value
                  )
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            >
              <option value="ALL">
                Semua Status
              </option>

              <option value="NORMAL">
                Normal
              </option>

              <option value="ANOMALI">
                Anomali
              </option>

              <option value="BELUM_DIANALISIS">
                Belum Dianalisis
              </option>

            </select>

          </div>


          <div>

            <label className="mb-2 block text-xs font-medium text-slate-500">
              Lokasi Anomali
            </label>

            <select
              value={locationFilter}
              onChange={
                (event) =>
                  setLocationFilter(
                    event.target.value
                  )
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            >
              <option value="ALL">
                Semua Lokasi
              </option>

              <option value="N0">
                N0
              </option>

              <option value="N1">
                N1
              </option>

              <option value="N2">
                N2
              </option>

              <option value="-">
                Tidak Ada
              </option>

            </select>

          </div>


          <div>

            <label className="mb-2 block text-xs font-medium text-slate-500">
              Tanggal Awal
            </label>

            <input
              type="date"
              value={startDate}
              onChange={
                (event) =>
                  setStartDate(
                    event.target.value
                  )
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            />

          </div>


          <div>

            <label className="mb-2 block text-xs font-medium text-slate-500">
              Tanggal Akhir
            </label>

            <input
              type="date"
              value={endDate}
              onChange={
                (event) =>
                  setEndDate(
                    event.target.value
                  )
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
            />

          </div>


          <div className="flex items-end">

            <button
              type="button"
              onClick={resetFilters}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-slate-800"
            >
              Reset Filter
            </button>

          </div>

        </div>

      </div>


      {/* SUMMARY */}

      <div className="flex flex-col gap-2 border-b border-slate-800 px-5 py-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">

        <p>
          <span className="font-semibold text-slate-300">
            {filteredRecords.length}
          </span>
          {' '}record dari{' '}
          {records.length} record yang dimuat.
        </p>

        <p>
          10 record per halaman.
        </p>

      </div>


      {/* DESKTOP */}

      <div className="hidden overflow-x-auto md:block">

        {pageRecords.length === 0 ? (

          <div className="flex min-h-48 items-center justify-center">

            <p className="text-sm text-slate-500">
              Tidak ada data yang sesuai dengan filter.
            </p>

          </div>

        ) : (

          <table className="min-w-full text-left text-sm">

            <thead className="bg-slate-950 text-xs uppercase tracking-wider text-slate-500">

              <tr>

                <th className="px-5 py-4">
                  Waktu
                </th>

                <th className="px-5 py-4">
                  Status
                </th>

                <th className="px-5 py-4">
                  Lokasi
                </th>

                <th className="px-5 py-4">
                  Random Forest
                </th>

                <th className="px-5 py-4">
                  Isolation Forest
                </th>

                <th className="px-5 py-4">
                  Z-score
                </th>

                <th className="px-5 py-4">
                  Detail
                </th>

              </tr>

            </thead>


            <tbody className="divide-y divide-slate-800">

              {pageRecords.map(
                (record) => {

                  const date =
                    formatDate(
                      record.timestamp
                    )

                  const analysis =
                    record?.analysis ?? {}

                  const rf =
                    analysis?.random_forest
                    ?? {}

                  const iso =
                    analysis?.isolation_forest
                    ?? {}

                  const z =
                    analysis?.dominant_zscore
                    ?? {}

                  const expanded =
                    expandedTimestamp
                    === record.timestamp


                  return (
                    <>
                      <tr
                        key={
                          `row-${record.timestamp}`
                        }
                        className="bg-slate-900 transition hover:bg-slate-800/60"
                      >

                        <td className="whitespace-nowrap px-5 py-4">

                          <p className="font-medium text-slate-200">
                            {date.time}
                          </p>

                          <p className="mt-1 text-xs text-slate-500">
                            {date.date}
                          </p>

                        </td>


                        <td className="px-5 py-4">

                          <StatusBadge
                            status={
                              analysis.status
                            }
                          />

                        </td>


                        <td className="px-5 py-4 font-semibold text-slate-200">
                          {analysis.location ?? '—'}
                        </td>


                        <td className="px-5 py-4">

                          <p className="font-medium text-slate-200">
                            {rf.prediction ?? '—'}
                          </p>

                          <p className="mt-1 text-xs text-cyan-400">
                            {formatConfidence(
                              rf.confidence
                            )}
                          </p>

                        </td>


                        <td className="px-5 py-4">

                          {
                            typeof iso.is_anomaly
                            === 'boolean'
                              ? iso.is_anomaly
                                ? (
                                  <span className="font-medium text-amber-400">
                                    ANOMALI
                                  </span>
                                )
                                : (
                                  <span className="font-medium text-emerald-400">
                                    NORMAL
                                  </span>
                                )
                              : '—'
                          }

                        </td>


                        <td className="px-5 py-4">

                          {
                            z.parameter
                              ? (
                                <>
                                  <p className="font-medium text-slate-200">
                                    {z.parameter} · {z.node}
                                  </p>

                                  <p className="mt-1 text-xs text-cyan-400">
                                    z = {formatNumber(
                                      z.zscore,
                                      2
                                    )}
                                  </p>
                                </>
                              )
                              : '—'
                          }

                        </td>


                        <td className="px-5 py-4">

                          <button
                            type="button"
                            onClick={() =>
                              setExpandedTimestamp(
                                expanded
                                  ? null
                                  : record.timestamp
                              )
                            }
                            className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-cyan-400 hover:text-cyan-300"
                          >
                            {
                              expanded
                                ? 'Tutup'
                                : 'Lihat'
                            }
                          </button>

                        </td>

                      </tr>


                      {expanded && (

                        <tr
                          key={
                            `detail-${record.timestamp}`
                          }
                        >

                          <td
                            colSpan="7"
                            className="bg-slate-950/60 p-5"
                          >

                            <DetailPanel
                              record={record}
                            />

                          </td>

                        </tr>

                      )}

                    </>
                  )

                }
              )}

            </tbody>

          </table>

        )}

      </div>


      {/* MOBILE */}

      <div className="space-y-3 p-4 md:hidden">

        {pageRecords.map(
          (record) => {

            const date =
              formatDate(
                record.timestamp
              )

            const analysis =
              record?.analysis ?? {}

            const rf =
              analysis?.random_forest
              ?? {}

            const expanded =
              expandedTimestamp
              === record.timestamp


            return (
              <div
                key={record.timestamp}
                className="rounded-xl border border-slate-800 bg-slate-950 p-4"
              >

                <div className="flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      {date.time}
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      {date.date}
                    </p>

                  </div>


                  <StatusBadge
                    status={
                      analysis.status
                    }
                  />

                </div>


                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">

                  <div>
                    <p className="text-xs text-slate-500">
                      Lokasi
                    </p>

                    <p className="mt-1 font-medium text-slate-200">
                      {analysis.location ?? '—'}
                    </p>
                  </div>


                  <div>
                    <p className="text-xs text-slate-500">
                      RF Confidence
                    </p>

                    <p className="mt-1 font-medium text-cyan-400">
                      {formatConfidence(
                        rf.confidence
                      )}
                    </p>
                  </div>

                </div>


                <button
                  type="button"
                  onClick={() =>
                    setExpandedTimestamp(
                      expanded
                        ? null
                        : record.timestamp
                    )
                  }
                  className="mt-4 w-full rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-300"
                >
                  {
                    expanded
                      ? 'Tutup Detail'
                      : 'Lihat Detail'
                  }
                </button>


                {expanded && (

                  <div className="mt-4">

                    <DetailPanel
                      record={record}
                    />

                  </div>

                )}

              </div>
            )

          }
        )}

      </div>


      {/* PAGINATION */}

      {filteredRecords.length > 0 && (

        <div className="flex flex-col gap-3 border-t border-slate-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">

          <p className="text-xs text-slate-500">
            Halaman{' '}
            <span className="font-semibold text-slate-300">
              {page}
            </span>
            {' '}dari{' '}
            <span className="font-semibold text-slate-300">
              {totalPages}
            </span>
          </p>


          <div className="flex gap-2">

            <button
              type="button"
              disabled={page <= 1}
              onClick={() =>
                setPage(
                  (current) =>
                    Math.max(
                      1,
                      current - 1
                    )
                )
              }
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Sebelumnya
            </button>


            <button
              type="button"
              disabled={
                page >= totalPages
              }
              onClick={() =>
                setPage(
                  (current) =>
                    Math.min(
                      totalPages,
                      current + 1
                    )
                )
              }
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Berikutnya
            </button>

          </div>

        </div>

      )}

    </div>
  )

}


export default HistoryExplorer
