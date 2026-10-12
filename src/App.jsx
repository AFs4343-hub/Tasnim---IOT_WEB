import { useEffect, useState } from 'react'

import {
  ref,
  onValue,
  query,
  orderByKey,
  limitToLast
} from 'firebase/database'

import { database } from './services/firebase'
import tasnimConfig from '../tasnim.config.json'
import { adaptEmulatorForLegacyDashboard } from './services/demoLegacyAdapter.js'
import { formatFieldLatestNodes, fieldHistoryRows } from './services/fieldHardwarePreview.js'
import IoTPerformancePanel from './components/IoTPerformancePanel'
import TrendChart from './components/TrendChart'
import NodeCard from './components/NodeCard'
import DeltaPanel from './components/DeltaPanel'
import AnomalyPanel from './components/AnomalyPanel'
import HistoryExplorer from './components/HistoryExplorer'
import NodeMap from './components/NodeMap'
import DashboardNav from './components/DashboardNav'
import StatisticsPanel from './components/StatisticsPanel'
import SystemOverview from './components/SystemOverview'
import ConnectionStateBanner from './components/ConnectionStateBanner'


// Explicit opt-in, development-only read of the field Firebase hardware_test
// root. Production build and default dashboard remain on SIMULATION.
const FIELD_PREVIEW = import.meta.env.DEV &&
  import.meta.env.VITE_TASNIM_FIELD_PREVIEW === 'YES'
const DATA_ROOT = FIELD_PREVIEW ? 'hardware_test' : tasnimConfig.activeDataRoot

function App({ demoSnapshot, fieldSnapshot } = {}) {

  // =========================================
  // STATE FIREBASE
  // =========================================

  // Data terbaru N0, N1, dan N2
  const [nodes, setNodes] = useState(null)

  // Data historis
  const [history, setHistory] = useState([])

  // Jumlah history yang dimuat dari Firebase
  const [historyLimit, setHistoryLimit] = useState(60)

  // Apakah masih ada record yang lebih lama
  // di Firebase daripada yang sedang ditampilkan.
  const [hasMoreHistory, setHasMoreHistory] =
    useState(true)

  // Hasil analisis AI realtime
  const [analysis, setAnalysis] = useState(null)

  // Waktu sejak AI mulai tertinggal dari history terbaru.
  // Tidak di-reset setiap kali sensor mengirim record baru.
  const [analysisMismatchSince, setAnalysisMismatchSince] =
    useState(null)

  // Status koneksi Firebase
  const [firebaseStatus, setFirebaseStatus] =
    useState('connecting')

  // Independent from listener order: a permission denial must never be
  // masked by a successful callback on a different Firebase path.
  const [fieldReadError, setFieldReadError] = useState(null)

  // Waktu terakhir data terbaru diterima
  const [lastUpdate, setLastUpdate] =
    useState(null)

  // Waktu saat ini untuk mengecek status Online/Offline node
  const [currentTime, setCurrentTime] =
    useState(Date.now())


  // The original dashboard can receive emulator-only data in demo mode.
  // All LIVE database subscriptions below are disabled when it is provided.
  useEffect(() => {
    if (demoSnapshot === undefined) return
    const next = adaptEmulatorForLegacyDashboard(demoSnapshot, historyLimit)
    setNodes(next.nodes)
    setHistory(next.history)
    setHasMoreHistory(next.hasMoreHistory)
    setAnalysis(next.analysis)
    setFirebaseStatus(next.firebaseStatus)
    // No invented "just updated" timestamp when the demo transport failed.
    setLastUpdate(demoSnapshot?.demoConnectionState ? null : new Date())
  }, [demoSnapshot, historyLimit])

  // Local JSON export viewer: no Firebase reads, writes or authentication.
  // This is a STATIC snapshot, never disguised as realtime history.
  useEffect(() => {
    if (fieldSnapshot === undefined) {
      setFieldReadError(null)
      return
    }
    const rawHistory = fieldSnapshot.history ?? null
    const rows = fieldHistoryRows(rawHistory, historyLimit)
    setNodes(formatFieldLatestNodes(fieldSnapshot.nodes))
    setHistory(rows)
    setHasMoreHistory(
      rawHistory && typeof rawHistory === 'object'
        ? Object.keys(rawHistory).length > historyLimit
        : false
    )
    setAnalysis(fieldSnapshot.analysis?.latest ?? null)
    setFirebaseStatus('file')
    setLastUpdate(null)
    setFieldReadError(null)
  }, [fieldSnapshot, historyLimit])

  // =========================================
  // TIMER STATUS NODE
  // =========================================

  useEffect(() => {

    // Cek ulang status setiap 30 detik meskipun Firebase tidak mengirim data baru
    const timer = setInterval(() => {
      setCurrentTime(Date.now())
    }, 30000)

    return () => clearInterval(timer)

  }, [])


  // =========================================
  // MEMBACA DATA TERBARU /nodes
  // =========================================

  useEffect(() => {
    if (demoSnapshot !== undefined || fieldSnapshot !== undefined) return

    const nodesRef = ref(database, `${DATA_ROOT}/nodes`)

    const unsubscribe = onValue(

      nodesRef,

      (snapshot) => {

        const data = snapshot.val()

        // Kalau /nodes kosong
        if (!data) {

          setNodes(null)
          setFirebaseStatus('empty')

          return
        }


        // Membentuk data agar cocok dengan NodeCard
        const formattedNodes = {

          N0: {
            node: 'N0',
            location: 'Hulu / Baseline',

            ph: data?.N0?.latest?.ph != null
              ? Number(data.N0.latest.ph)
              : null,

            tds: data?.N0?.latest?.tds != null
              ? Number(data.N0.latest.tds)
              : null,

            turbidity: data?.N0?.latest?.turbidity != null
              ? Number(data.N0.latest.turbidity)
              : null,

            timestamp: data?.N0?.latest?.timestamp != null
              ? Number(data.N0.latest.timestamp)
              : null,

            lastSeen: data?.N0?.latest?.timestamp != null
              ? Number(data.N0.latest.timestamp)
              : null,

            rssi:
              data?.N0?.latest?.rssi != null
                ? Number(data.N0.latest.rssi)
                : null,

            sequence:
              data?.N0?.latest?.sequence != null
                ? Number(data.N0.latest.sequence)
                : null,

            hasData:
              Boolean(data?.N0?.latest)
          },


          N1: {
            node: 'N1',
            location: 'Cabang Irigasi 1',

            ph: data?.N1?.latest?.ph != null
              ? Number(data.N1.latest.ph)
              : null,

            tds: data?.N1?.latest?.tds != null
              ? Number(data.N1.latest.tds)
              : null,

            turbidity: data?.N1?.latest?.turbidity != null
              ? Number(data.N1.latest.turbidity)
              : null,

            timestamp: data?.N1?.latest?.timestamp != null
              ? Number(data.N1.latest.timestamp)
              : null,

            lastSeen: data?.N1?.latest?.timestamp != null
              ? Number(data.N1.latest.timestamp)
              : null,

            rssi:
              data?.N1?.latest?.rssi != null
                ? Number(data.N1.latest.rssi)
                : null,

            sequence:
              data?.N1?.latest?.sequence != null
                ? Number(data.N1.latest.sequence)
                : null,

            hasData:
              Boolean(data?.N1?.latest)
          },


          N2: {
            node: 'N2',
            location: 'Cabang Irigasi 2',

            ph: data?.N2?.latest?.ph != null
              ? Number(data.N2.latest.ph)
              : null,

            tds: data?.N2?.latest?.tds != null
              ? Number(data.N2.latest.tds)
              : null,

            turbidity: data?.N2?.latest?.turbidity != null
              ? Number(data.N2.latest.turbidity)
              : null,

            timestamp: data?.N2?.latest?.timestamp != null
              ? Number(data.N2.latest.timestamp)
              : null,

            lastSeen: data?.N2?.latest?.timestamp != null
              ? Number(data.N2.latest.timestamp)
              : null,

            rssi:
              data?.N2?.latest?.rssi != null
                ? Number(data.N2.latest.rssi)
                : null,

            sequence:
              data?.N2?.latest?.sequence != null
                ? Number(data.N2.latest.sequence)
                : null,

            hasData:
              Boolean(data?.N2?.latest)
          }

        }


        setNodes(FIELD_PREVIEW ? formatFieldLatestNodes(data) : formattedNodes)

        setFirebaseStatus('online')

        setLastUpdate(new Date())


        // Never print physical measurements in the browser console.

      },


      (error) => {

        console.error(
          'Firebase Error:',
          error
        )

        setFirebaseStatus('error')
        if (FIELD_PREVIEW) {
          setNodes(null)
          setHistory([])
          setAnalysis(null)
          setFieldReadError(error?.code === 'PERMISSION_DENIED' ||
            error?.code === 'permission_denied'
            ? 'Firebase menolak akses hardware_test tanpa autentikasi. Dashboard tetap terbuka, tetapi data langsung tidak dapat dibaca. Gunakan ekspor JSON lokal untuk melihat hasil alat sementara; izin Firebase perlu diselesaikan bersama pengelola proyek.'
            : 'Firebase hardware_test tidak dapat dibaca. Periksa konfigurasi proyek dan koneksi.')
        }

      }

    )


    return () => unsubscribe()

  }, [demoSnapshot, fieldSnapshot])



  // =========================================
  // MEMBACA DATA HISTORIS /history
  // =========================================

  useEffect(() => {
    if (demoSnapshot !== undefined || fieldSnapshot !== undefined) return

    // Ambil 60 timestamp terakhir
    const historyRef = query(
      ref(database, `${DATA_ROOT}/history`),
      orderByKey(),
      // Ambil 1 record ekstra untuk mengecek
      // apakah masih ada data yang lebih lama.
      limitToLast(historyLimit + 1)
    )


    const unsubscribe = onValue(

      historyRef,


      (snapshot) => {

        const data = snapshot.val()


        // Kalau history kosong
        if (!data) {

          setHistory([])
          setHasMoreHistory(false)

          return
        }


        // Firebase diminta historyLimit + 1.
        // Record ekstra hanya digunakan untuk mengecek
        // apakah masih ada data yang lebih lama.
        const historyEntries =
          Object.entries(data)
            .sort(
              ([timestampA], [timestampB]) =>
                Number(timestampA)
                - Number(timestampB)
            )


        const hasMore =
          historyEntries.length
          > historyLimit


        setHasMoreHistory(
          hasMore
        )


        // Record ekstra paling lama tidak perlu
        // ditampilkan di tabel.
        const visibleEntries =
          hasMore
            ? historyEntries.slice(
                -historyLimit
              )
            : historyEntries


        const formattedHistory =
          visibleEntries

            .map(([timestamp, value]) => {

              const numericTimestamp =
                Number(timestamp)

              return {

                timestamp:
                  numericTimestamp,

                time:
                  new Date(
                    numericTimestamp
                  ).toLocaleTimeString(
                    'id-ID',
                    {
                      hour: '2-digit',
                      minute: '2-digit'
                    }
                  ),


                // =====================
                // DATA NODE LENGKAP
                // =====================

                N0:
                  value?.N0 ?? null,

                N1:
                  value?.N1 ?? null,

                N2:
                  value?.N2 ?? null,


                // =====================
                // FORMAT LAMA
                // Tetap dipertahankan
                // untuk grafik/statistik
                // =====================

                N0_ph:
                  value?.N0?.ph != null
                  ? Number(value.N0.ph)
                  : null,

                N0_tds:
                  value?.N0?.tds != null
                  ? Number(value.N0.tds)
                  : null,

                N0_turbidity:
                  value?.N0?.turbidity != null
                  ? Number(value.N0.turbidity)
                  : null,

                N1_ph:
                  value?.N1?.ph != null
                  ? Number(value.N1.ph)
                  : null,

                N1_tds:
                  value?.N1?.tds != null
                  ? Number(value.N1.tds)
                  : null,

                N1_turbidity:
                  value?.N1?.turbidity != null
                  ? Number(value.N1.turbidity)
                  : null,

                N2_ph:
                  value?.N2?.ph != null
                  ? Number(value.N2.ph)
                  : null,

                N2_tds:
                  value?.N2?.tds != null
                  ? Number(value.N2.tds)
                  : null,

                N2_turbidity:
                  value?.N2?.turbidity != null
                  ? Number(value.N2.turbidity)
                  : null,


                // =====================
                // METADATA + AI
                // =====================

                meta:
                  value?.meta ?? null,

                analysis:
                  value?.analysis ?? null

              }

            })

            // Lama → baru untuk grafik
            .sort(
              (a, b) =>
                a.timestamp - b.timestamp
            )


        setHistory(FIELD_PREVIEW ? fieldHistoryRows(data, historyLimit) : formattedHistory)


        // History shown only from records actually stored in Firebase.

      },


      (error) => {

        console.error('History Firebase listener failed:', error?.code ?? 'unknown')
        if (FIELD_PREVIEW) {
          setHistory([])
          setHasMoreHistory(false)
          setFieldReadError(error?.code === 'PERMISSION_DENIED' ||
            error?.code === 'permission_denied'
            ? 'Firebase menolak pembacaan history. Pembukaan dashboard tanpa login tidak mengubah izin Firebase.'
            : 'History Firebase tidak dapat dibaca.')
        }

      }

    )


    return () => unsubscribe()

  }, [historyLimit, demoSnapshot, fieldSnapshot])



  // =========================================
  // STATUS ONLINE / OFFLINE NODE
  // =========================================

  const getNodeStatus = (timestamp) => {

    if (!timestamp) {
      return 'Tidak Ada Data'
    }

    const numericTimestamp =
      Number(timestamp)

    if (
      !Number.isFinite(numericTimestamp)
    ) {
      return 'Waktu Tidak Valid'
    }

    const difference =
      currentTime - numericTimestamp

    // Toleransi kecil untuk clock drift.
    // Jika timestamp terlalu jauh di masa depan,
    // jangan dianggap Online.
    const futureTolerance =
      60 * 1000

    if (
      difference < -futureTolerance
    ) {
      return 'Waktu Tidak Valid'
    }

    // Batas sementara: 10 menit
    // Karena interval pengiriman direncanakan sekitar 5 menit.
    const offlineThreshold =
      10 * 60 * 1000

    if (
      difference <= offlineThreshold
    ) {
      return 'Online'
    }

    return 'Offline'
  }


  // =========================================
  // NODE + STATUS HASIL PERHITUNGAN
  // =========================================

  const nodesWithStatus = nodes
    ? {
        N0: {
          ...nodes.N0,
          status: getNodeStatus(nodes.N0.timestamp)
        },

        N1: {
          ...nodes.N1,
          status: getNodeStatus(nodes.N1.timestamp)
        },

        N2: {
          ...nodes.N2,
          status: getNodeStatus(nodes.N2.timestamp)
        }
      }
    : null


  // =========================================
  // SINKRONISASI DATA SENSOR ↔ HASIL AI
  // =========================================

  const AI_PENDING_GRACE_MS =
    30 * 1000

  const latestHistoryTimestamp =
    history.length > 0
      ? Number(
          history[
            history.length - 1
          ]?.timestamp
        )
      : null


  // =========================================
  // KELENGKAPAN DATA SLOT TERBARU
  // =========================================

  const latestHistoryRecord =
    history.length > 0
      ? history[
          history.length - 1
        ]
      : null


  // =========================================
  // DATA QUALITY ENGINE
  //
  // Menentukan apakah satu slot history layak
  // dianalisis AI.
  //
  // critical:
  //   masalah yang membuat AI HARUS skip.
  //
  // warnings:
  //   masalah telemetri/non-sensor yang tidak
  //   membatalkan analisis kualitas air.
  // =========================================

  const isMissingValue = (
    value
  ) => {

    return (
      value === null
      || value === undefined
      || value === ''
    )

  }


  const toFiniteNumber = (
    value
  ) => {

    if (isMissingValue(value)) {
      return null
    }

    const numeric =
      Number(value)

    return Number.isFinite(numeric)
      ? numeric
      : null

  }


  const isSensorValueValid = (
    parameter,
    value
  ) => {

    const numeric =
      toFiniteNumber(value)

    if (numeric === null) {
      return false
    }


    // Validasi dasar sesuai kontrak data TASNIM.
    // BUKAN threshold kualitas air/anomali.
    if (parameter === 'ph') {

      return (
        numeric >= 0
        && numeric <= 14
      )

    }


    if (
      parameter === 'tds'
      || parameter === 'turbidity'
    ) {

      return numeric >= 0

    }


    return false

  }


  const getDataQuality = (
    record
  ) => {

    const critical = []
    const warnings = []


    // -----------------------------------------
    // SLOT / TIMESTAMP
    // -----------------------------------------

    if (!record) {

      return {
        analyzable: false,
        status: 'NO_DATA',
        critical: [
          {
            node: null,
            component: 'record',
            reason: 'MISSING'
          }
        ],
        warnings: []
      }

    }


    const slotTimestamp =
      toFiniteNumber(
        record.timestamp
      )


    if (
      slotTimestamp === null
      || slotTimestamp <= 0
    ) {

      critical.push({
        node: null,
        component: 'timestamp',
        reason: 'INVALID_TIME'
      })

    }


    // -----------------------------------------
    // NODE + SENSOR
    // -----------------------------------------

    for (
      const node of ['N0', 'N1', 'N2']
    ) {

      const nodeData =
        record?.[node]


      if (!nodeData) {

        critical.push({
          node,
          component: 'node',
          reason: 'NODE_MISSING'
        })

        continue

      }


      for (
        const parameter
        of ['ph', 'tds', 'turbidity']
      ) {

        const value =
          nodeData?.[parameter]


        if (
          isMissingValue(value)
        ) {

          critical.push({
            node,
            component: parameter,
            reason: 'SENSOR_MISSING'
          })

          continue

        }


        if (
          !isSensorValueValid(
            parameter,
            value
          )
        ) {

          critical.push({
            node,
            component: parameter,
            reason: 'INVALID_SENSOR'
          })

        }

      }


      // ---------------------------------------
      // TELEMETRY
      // Tidak menghentikan AI.
      // ---------------------------------------

      if (
        isMissingValue(
          nodeData.rssi
        )
        || toFiniteNumber(
          nodeData.rssi
        ) === null
      ) {

        warnings.push({
          node,
          component: 'rssi',
          reason: 'TELEMETRY_MISSING'
        })

      }


      if (
        isMissingValue(
          nodeData.sequence
        )
        || toFiniteNumber(
          nodeData.sequence
        ) === null
      ) {

        warnings.push({
          node,
          component: 'sequence',
          reason: 'TELEMETRY_MISSING'
        })

      }

    }


    // -----------------------------------------
    // STATUS UTAMA
    // -----------------------------------------

    let status =
      'COMPLETE'


    if (
      critical.some(
        issue =>
          issue.reason
          === 'INVALID_TIME'
      )
    ) {

      status =
        'INVALID_TIME'

    } else if (
      critical.some(
        issue =>
          issue.reason
          === 'NODE_MISSING'
      )
    ) {

      status =
        'NODE_MISSING'

    } else if (
      critical.some(
        issue =>
          issue.reason
          === 'SENSOR_MISSING'
      )
    ) {

      status =
        'SENSOR_MISSING'

    } else if (
      critical.some(
        issue =>
          issue.reason
          === 'INVALID_SENSOR'
      )
    ) {

      status =
        'INVALID_SENSOR'

    }


    return {
      analyzable:
        critical.length === 0,

      status,

      critical,
      warnings
    }

  }


  const latestDataQuality =
    getDataQuality(
      latestHistoryRecord
    )


  // Compatibility sementara untuk UI lama.
  // Bisa dihapus setelah seluruh komponen
  // menggunakan latestDataQuality langsung.
  const latestCompleteness = {

    complete:
      latestDataQuality.analyzable,

    missing:
      latestDataQuality.critical.map(
        issue =>
          `${issue.node ?? 'SYSTEM'}:${issue.component}`
      )

  }


  useEffect(() => {

    const latestTimestamp =
      history.length > 0
        ? Number(
            history[
              history.length - 1
            ]?.timestamp
          )
        : null

    const dataQuality =
      getDataQuality(
        latestHistoryRecord
      )


    // Slot yang tidak layak dianalisis memang
    // sengaja dilewati AI.
    // Jangan dianggap sebagai AI mismatch/stale.
    if (!dataQuality.analyzable) {

      setAnalysisMismatchSince(
        null
      )

      return

    }


    const aiTimestamp =
      analysis?.source_timestamp_ms != null
        ? Number(
            analysis.source_timestamp_ms
          )
        : null

    const timestampsValid =
      Number.isFinite(latestTimestamp)
      && Number.isFinite(aiTimestamp)

    if (
      !timestampsValid
      || latestTimestamp === aiTimestamp
    ) {
      setAnalysisMismatchSince(null)
      return
    }

    // AI dan sensor mulai berbeda.
    // Jangan reset timer ketika history baru terus masuk.
    setAnalysisMismatchSince(
      previous =>
        previous ?? Date.now()
    )

  }, [
    history,
    analysis
  ])


  const getAnalysisSyncState = () => {

    if (!latestHistoryRecord) {
      return 'NO_HISTORY'
    }


    if (
      !latestDataQuality.analyzable
    ) {
      return 'INCOMPLETE_DATA'
    }


    if (!analysis) {
      return 'NO_ANALYSIS'
    }

    const aiTimestamp =
      Number(
        analysis.source_timestamp_ms
      )

    if (
      !Number.isFinite(aiTimestamp)
      || !Number.isFinite(
        latestHistoryTimestamp
      )
    ) {
      return 'UNKNOWN'
    }

    if (
      aiTimestamp
      === latestHistoryTimestamp
    ) {
      return 'SYNCED'
    }

    // Listener Firebase dapat tiba tidak berurutan.
    // Jika analysis lebih baru dari history yang
    // sedang tampil, beri waktu listener history
    // untuk mengejar.
    if (
      aiTimestamp
      > latestHistoryTimestamp
    ) {
      return 'PENDING'
    }

    // Hitung sudah berapa lama AI dan sensor
    // berada dalam kondisi tidak sinkron.
    if (
      analysisMismatchSince == null
    ) {
      return 'PENDING'
    }

    const mismatchAge =
      currentTime
      - analysisMismatchSince

    if (
      mismatchAge
      <= AI_PENDING_GRACE_MS
    ) {
      return 'PENDING'
    }

    return 'STALE'
  }


  const analysisSyncState =
    getAnalysisSyncState()




  // =========================================
  // FIREBASE REALTIME - HASIL AI
  // =========================================

  useEffect(() => {
    if (demoSnapshot !== undefined || fieldSnapshot !== undefined) return

    const analysisRef = ref(
      database,
      `${DATA_ROOT}/analysis/latest`
    )

    const unsubscribe = onValue(
      analysisRef,

      (snapshot) => {

        const data = snapshot.val()

        if (data) {
          setAnalysis(data)
        } else {
          setAnalysis(null)
        }

      },

      (error) => {
        console.error('AI Firebase listener failed:', error?.code ?? 'unknown')
        if (FIELD_PREVIEW) {
          setAnalysis(null)
          setFieldReadError(error?.code === 'PERMISSION_DENIED' ||
            error?.code === 'permission_denied'
            ? 'Firebase menolak pembacaan hasil AI. Tidak ada hasil AI yang dibuat-buat.'
            : 'Hasil AI Firebase tidak dapat dibaca.')
        }
      }
    )

    return () => unsubscribe()

  }, [demoSnapshot, fieldSnapshot])



  return (

    <main className="min-h-screen bg-slate-950 text-white">

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-10">


        {/* =================================
            HEADER
        ================================= */}

        {FIELD_PREVIEW && demoSnapshot === undefined && <div role="status"
          className="mb-5 rounded-xl border border-amber-600/60 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          {fieldSnapshot === undefined
            ? <>PRATINJAU ALAT ASLI — koneksi langsung ke Firebase <code>hardware_test</code>.
                Jika izin Firebase ditolak, gunakan JSON ekspor lokal.</>
            : <>PRATINJAU JSON LOKAL — bukan sinkronisasi Firebase real-time.</>}
          {' '}Grafik dan History hanya berisi data yang benar-benar tersimpan;
          tidak ada histori atau hasil AI yang dibuat-buat.
        </div>}

        <header className="mb-7 sm:mb-10">

          <p className="text-sm font-semibold tracking-widest text-cyan-400">
            MULTI-NODE IoT-WEB
          </p>

          <h1 className="mt-2 text-4xl font-bold sm:text-5xl">
            TASNIM
          </h1>

          <p className="mt-3 max-w-3xl text-slate-400">
            Surveilans Kualitas Air Irigasi Budidaya Ikan
            melalui pemantauan multi-node secara real-time.
          </p>

        </header>



        {/* =================================
            NAVIGASI DASHBOARD
        ================================= */}

        <DashboardNav />



        {/* =================================
            STATUS / OVERVIEW SISTEM
        ================================= */}

        <section id="status" className="scroll-mt-28 mb-8">

          <SystemOverview
            demoMode={demoSnapshot !== undefined}
            firebaseStatus={fieldReadError ? 'error' : firebaseStatus}
            lastUpdate={lastUpdate}
            nodes={nodesWithStatus}
            historyCount={history.length}
          />

        </section>


        {/* =================================
            STATUS KONEKSI / EMPTY STATE
        ================================= */}

        {FIELD_PREVIEW && fieldReadError && <section role="alert"
          className="mb-6 rounded-xl border border-amber-500/50 bg-amber-950/40 p-4 text-sm text-amber-100">
          {fieldReadError}
        </section>}
        <ConnectionStateBanner
          firebaseStatus={fieldReadError ? 'error' : firebaseStatus}
          hasNodes={Boolean(nodesWithStatus)}
          historyCount={history.length}
        />


        {/* =================================
            MONITORING NODE
        ================================= */}

        {!nodesWithStatus && firebaseStatus !== 'connecting' && firebaseStatus !== 'error' && (

          <section
            id="monitoring"
            className="scroll-mt-28 rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 p-8 text-center"
          >

            <h2 className="text-lg font-semibold text-slate-300">
              Belum ada data node
            </h2>

            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">
              Dashboard sudah siap. Saat N0, N1, atau N2 mulai mengirim data ke Firebase,
              kartu monitoring akan muncul otomatis tanpa perlu mengubah kode.
            </p>

          </section>

        )}

        {nodesWithStatus && (

          <section id="monitoring" className="scroll-mt-28">

            <div className="mb-5">

              <h2 className="text-2xl font-bold">
                Monitoring Node
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Data kualitas air pada setiap titik
                jaringan irigasi.
              </p>

            </div>


            <div className="grid gap-5 lg:grid-cols-3">

              <NodeCard
                {...nodesWithStatus.N0}
              />

              <NodeCard
                {...nodesWithStatus.N1}
              />

              <NodeCard
                {...nodesWithStatus.N2}
              />

            </div>

          </section>

        )}



        {/* =================================
            GRAFIK RIWAYAT
        ================================= */}

        <section id="grafik" className="scroll-mt-28 mt-8">

          <TrendChart
            data={history.slice(-24)}
          />

        </section>




        {/* =================================
            STATISTIK DESKRIPTIF
        ================================= */}

        <section id="statistik" className="scroll-mt-28 mt-8">

          <StatisticsPanel
            data={history}
          />

        </section>



        {/* =================================
            ANALISIS SPASIAL
        ================================= */}

        {nodesWithStatus && (

          <section id="spasial" className="scroll-mt-28 mt-8">

            <div className="mb-5">

              <h2 className="text-2xl font-bold">
                Analisis Spasial Antar-Node
              </h2>

              <p className="mt-1 max-w-3xl text-sm text-slate-400">
                Perubahan kualitas air dari node hulu
                menuju masing-masing cabang jaringan
                irigasi.
              </p>

            </div>


            <div className="grid gap-5 lg:grid-cols-2">

              <DeltaPanel
                title="N0 → N1"
                upstream={nodesWithStatus.N0}
                downstream={nodesWithStatus.N1}
              />

              <DeltaPanel
                title="N0 → N2"
                upstream={nodesWithStatus.N0}
                downstream={nodesWithStatus.N2}
              />

            </div>

          </section>

        )}
        




        {/* =================================
            KINERJA SISTEM IOT
        ================================= */}

        <section id="iot" className="scroll-mt-28 mt-8">

          <IoTPerformancePanel
            nodes={nodesWithStatus}
            history={history}
            intervalMinutes={5}
          />

        </section>




        {/* =================================
            PETA NODE
        ================================= */}

        <section id="peta" className="scroll-mt-28 mt-8">

          <NodeMap
            nodes={nodesWithStatus}
          />

        </section>



        {/* =================================
            AI / DETEKSI ANOMALI
        ================================= */}

        <section id="ai" className="scroll-mt-28 mt-8">

          <AnomalyPanel
            analysis={analysis}
            syncState={analysisSyncState}
            dataQuality={latestDataQuality}
          />

        </section>



        {/* =================================
            RIWAYAT DATA + FILTER + EXPORT
        ================================= */}

        <section id="riwayat" className="scroll-mt-28 mt-8">

          <HistoryExplorer
            data={history}
            historyLimit={historyLimit}
            hasMoreHistory={hasMoreHistory}

            onLoadMore={() =>
              setHistoryLimit(
                (current) => current + 60
              )
            }

            onLoadLess={() =>
              setHistoryLimit(
                (current) =>
                  Math.max(
                    60,
                    current - 60
                  )
              )
            }

            onResetHistory={() =>
              setHistoryLimit(60)
            }
          />

        </section>



        {/* =================================
            FOOTER
        ================================= */}

        <footer className="mt-12 border-t border-slate-800 pt-6">

          <div className="flex flex-col gap-2 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">

            <p>
              TASNIM — Multi-Node IoT-Web
            </p>

            <p>
              Sistem Surveilans Kualitas Air Irigasi
            </p>

          </div>

        </footer>


      </div>

    </main>

  )

}

export default App