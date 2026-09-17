import { useEffect, useState } from 'react'

import {
  ref,
  onValue,
  query,
  orderByKey,
  limitToLast
} from 'firebase/database'

import { database } from './services/firebase'
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


function App() {

  // =========================================
  // STATE FIREBASE
  // =========================================

  // Data terbaru N0, N1, dan N2
  const [nodes, setNodes] = useState(null)

  // Data historis
  const [history, setHistory] = useState([])

  // Hasil analisis AI realtime
  const [analysis, setAnalysis] = useState(null)

  // Status koneksi Firebase
  const [firebaseStatus, setFirebaseStatus] =
    useState('connecting')

  // Waktu terakhir data terbaru diterima
  const [lastUpdate, setLastUpdate] =
    useState(null)

  // Waktu saat ini untuk mengecek status Online/Offline node
  const [currentTime, setCurrentTime] =
    useState(Date.now())


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

    const nodesRef = ref(database, 'nodes')

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

            ph: Number(
              data?.N0?.latest?.ph ?? 0
            ),

            tds: Number(
              data?.N0?.latest?.tds ?? 0
            ),

            turbidity: Number(
              data?.N0?.latest?.turbidity ?? 0
            ),

            timestamp: Number(
              data?.N0?.latest?.timestamp ?? 0
            ),

            lastSeen: Number(
              data?.N0?.latest?.timestamp ?? 0
            ),

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

            ph: Number(
              data?.N1?.latest?.ph ?? 0
            ),

            tds: Number(
              data?.N1?.latest?.tds ?? 0
            ),

            turbidity: Number(
              data?.N1?.latest?.turbidity ?? 0
            ),

            timestamp: Number(
              data?.N1?.latest?.timestamp ?? 0
            ),

            lastSeen: Number(
              data?.N1?.latest?.timestamp ?? 0
            ),

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

            ph: Number(
              data?.N2?.latest?.ph ?? 0
            ),

            tds: Number(
              data?.N2?.latest?.tds ?? 0
            ),

            turbidity: Number(
              data?.N2?.latest?.turbidity ?? 0
            ),

            timestamp: Number(
              data?.N2?.latest?.timestamp ?? 0
            ),

            lastSeen: Number(
              data?.N2?.latest?.timestamp ?? 0
            ),

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


        setNodes(formattedNodes)

        setFirebaseStatus('online')

        setLastUpdate(new Date())


        console.log(
          'DATA FIREBASE:',
          formattedNodes
        )

      },


      (error) => {

        console.error(
          'Firebase Error:',
          error
        )

        setFirebaseStatus('error')

      }

    )


    return () => unsubscribe()

  }, [])



  // =========================================
  // MEMBACA DATA HISTORIS /history
  // =========================================

  useEffect(() => {

    // Ambil 60 timestamp terakhir
    const historyRef = query(
      ref(database, 'history'),
      orderByKey(),
      limitToLast(60)
    )


    const unsubscribe = onValue(

      historyRef,


      (snapshot) => {

        const data = snapshot.val()


        // Kalau history kosong
        if (!data) {

          setHistory([])

          return
        }


        const formattedHistory =
          Object.entries(data)

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
                  Number(
                    value?.N0?.ph ?? 0
                  ),

                N0_tds:
                  Number(
                    value?.N0?.tds ?? 0
                  ),

                N0_turbidity:
                  Number(
                    value?.N0?.turbidity ?? 0
                  ),

                N1_ph:
                  Number(
                    value?.N1?.ph ?? 0
                  ),

                N1_tds:
                  Number(
                    value?.N1?.tds ?? 0
                  ),

                N1_turbidity:
                  Number(
                    value?.N1?.turbidity ?? 0
                  ),

                N2_ph:
                  Number(
                    value?.N2?.ph ?? 0
                  ),

                N2_tds:
                  Number(
                    value?.N2?.tds ?? 0
                  ),

                N2_turbidity:
                  Number(
                    value?.N2?.turbidity ?? 0
                  ),


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


        setHistory(formattedHistory)


        console.log(
          'HISTORY FIREBASE:',
          formattedHistory
        )

      },


      (error) => {

        console.error(
          'History Firebase Error:',
          error
        )

      }

    )


    return () => unsubscribe()

  }, [])



  // =========================================
  // STATUS ONLINE / OFFLINE NODE
  // =========================================

  const getNodeStatus = (timestamp) => {

    if (!timestamp) {
      return 'Tidak Ada Data'
    }

    const difference =
      currentTime - Number(timestamp)

    // Batas sementara: 10 menit
    // Karena interval pengiriman direncanakan sekitar 5 menit.
    const offlineThreshold =
      10 * 60 * 1000

    if (difference <= offlineThreshold) {
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
  // FIREBASE REALTIME - HASIL AI
  // =========================================

  useEffect(() => {

    const analysisRef = ref(
      database,
      'analysis/latest'
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
        console.error(
          'AI Firebase Error:',
          error
        )
      }
    )

    return () => unsubscribe()

  }, [])



  return (

    <main className="min-h-screen bg-slate-950 text-white">

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-10">


        {/* =================================
            HEADER
        ================================= */}

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
            firebaseStatus={firebaseStatus}
            lastUpdate={lastUpdate}
            nodes={nodesWithStatus}
            historyCount={history.length}
          />

        </section>


        {/* =================================
            STATUS KONEKSI / EMPTY STATE
        ================================= */}

        <ConnectionStateBanner
          firebaseStatus={firebaseStatus}
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
          />

        </section>



        {/* =================================
            RIWAYAT DATA + FILTER + EXPORT
        ================================= */}

        <section id="riwayat" className="scroll-mt-28 mt-8">

          <HistoryExplorer
            data={history}
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