import { useEffect, useState } from 'react'

import {
  ref,
  onValue,
  query,
  orderByKey,
  limitToLast
} from 'firebase/database'

import { database } from './services/firebase'

import TrendChart from './components/TrendChart'
import NodeCard from './components/NodeCard'
import DeltaPanel from './components/DeltaPanel'
import AnomalyPanel from './components/AnomalyPanel'
import HistoryTable from './components/HistoryTable'


function App() {

  // =========================================
  // STATE FIREBASE
  // =========================================

  // Data terbaru N0, N1, dan N2
  const [nodes, setNodes] = useState(null)

  // Data historis
  const [history, setHistory] = useState([])

  // Status koneksi Firebase
  const [firebaseStatus, setFirebaseStatus] =
    useState('connecting')

  // Waktu terakhir data terbaru diterima
  const [lastUpdate, setLastUpdate] =
    useState(null)


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

            status:
              data?.N0?.latest
                ? 'Online'
                : 'Tidak Ada Data',

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

            status:
              data?.N1?.latest
                ? 'Online'
                : 'Tidak Ada Data',

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

            status:
              data?.N2?.latest
                ? 'Online'
                : 'Tidak Ada Data',

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


                // Untuk label sumbu grafik
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
                // N0
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


                // =====================
                // N1
                // =====================

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


                // =====================
                // N2
                // =====================

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
                  )

              }

            })


            // Urutkan timestamp lama → baru
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
  // DATA UNTUK HISTORY TABLE
  // =========================================

  const historyData = history

    .flatMap((record) => {

      const formattedTime =
        new Date(
          record.timestamp
        ).toLocaleString('id-ID')


      // Satu timestamp Firebase
      // dipecah menjadi tiga baris:
      // N0, N1, N2

      return [

        {
          time: formattedTime,
          node: 'N0',

          ph:
            record.N0_ph,

          tds:
            record.N0_tds,

          turbidity:
            record.N0_turbidity,

          status: 'Normal'
        },


        {
          time: formattedTime,
          node: 'N1',

          ph:
            record.N1_ph,

          tds:
            record.N1_tds,

          turbidity:
            record.N1_turbidity,

          status: 'Normal'
        },


        {
          time: formattedTime,
          node: 'N2',

          ph:
            record.N2_ph,

          tds:
            record.N2_tds,

          turbidity:
            record.N2_turbidity,

          status: 'Normal'
        }

      ]

    })

    // Data terbaru tampil di atas tabel
    .reverse()



  // =========================================
  // STATUS SISTEM
  // =========================================

  const systemOnline =
    firebaseStatus === 'online'



  return (

    <main className="min-h-screen bg-slate-950 text-white">

      <div className="mx-auto max-w-7xl px-6 py-10">


        {/* =================================
            HEADER
        ================================= */}

        <header className="mb-10">

          <p className="text-sm font-semibold tracking-widest text-cyan-400">
            MULTI-NODE IoT-WEB
          </p>

          <h1 className="mt-2 text-5xl font-bold">
            TASNIM
          </h1>

          <p className="mt-3 max-w-3xl text-slate-400">
            Surveilans Kualitas Air Irigasi Budidaya Ikan
            melalui pemantauan multi-node secara real-time.
          </p>

        </header>



        {/* =================================
            STATUS SISTEM
        ================================= */}

        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-5">

          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">


            <div>

              <p className="text-sm text-slate-400">
                Status Sistem
              </p>


              <h2 className="mt-1 text-xl font-semibold">

                {firebaseStatus === 'connecting'
                  ? 'Menghubungkan ke Firebase...'

                  : firebaseStatus === 'online'
                  ? 'Monitoring Aktif'

                  : firebaseStatus === 'empty'
                  ? 'Database Kosong'

                  : 'Koneksi Bermasalah'}

              </h2>


              {lastUpdate && (

                <p className="mt-2 text-xs text-slate-500">

                  Update terakhir:{' '}

                  {lastUpdate
                    .toLocaleTimeString('id-ID')}

                </p>

              )}

            </div>



            <div
              className={`flex items-center gap-2 ${
                systemOnline
                  ? 'text-emerald-400'
                  : 'text-amber-400'
              }`}
            >

              <span
                className={`h-3 w-3 rounded-full ${
                  systemOnline
                    ? 'bg-emerald-400'
                    : 'bg-amber-400'
                }`}
              />


              <span className="font-medium">

                {systemOnline
                  ? 'Firebase Online'
                  : 'Menunggu Data'}

              </span>

            </div>


          </div>

        </section>



        {/* =================================
            ERROR FIREBASE
        ================================= */}

        {firebaseStatus === 'error' && (

          <section className="mb-8 rounded-2xl border border-red-500/30 bg-red-500/10 p-5">

            <h2 className="font-semibold text-red-400">
              Gagal terhubung ke Firebase
            </h2>

            <p className="mt-2 text-sm text-slate-400">
              Periksa konfigurasi .env, firebase.js,
              databaseURL, dan Firebase Realtime
              Database Rules.
            </p>

          </section>

        )}



        {/* =================================
            LOADING FIREBASE
        ================================= */}

        {firebaseStatus === 'connecting' && (

          <section className="mb-8 rounded-2xl border border-cyan-500/30 bg-slate-900 p-5">

            <p className="text-cyan-400">
              Mengambil data N0, N1, dan N2 dari Firebase...
            </p>

          </section>

        )}



        {/* =================================
            MONITORING NODE
        ================================= */}

        {nodes && (

          <section>

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
                {...nodes.N0}
              />

              <NodeCard
                {...nodes.N1}
              />

              <NodeCard
                {...nodes.N2}
              />

            </div>

          </section>

        )}



        {/* =================================
            GRAFIK RIWAYAT
        ================================= */}

        <section className="mt-8">

          <TrendChart
            data={history}
          />

        </section>



        {/* =================================
            ANALISIS SPASIAL
        ================================= */}

        {nodes && (

          <section className="mt-8">

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
                upstream={nodes.N0}
                downstream={nodes.N1}
              />

              <DeltaPanel
                title="N0 → N2"
                upstream={nodes.N0}
                downstream={nodes.N2}
              />

            </div>

          </section>

        )}



        {/* =================================
            AI / DETEKSI ANOMALI
        ================================= */}

        <section className="mt-8">

          <AnomalyPanel
            status="Menunggu AI"
            node="-"
            score={null}
            message="Random Forest dan Isolation Forest belum dihubungkan ke dashboard. Z-score akan digunakan sebagai analisis statistik pendukung."
          />

        </section>



        {/* =================================
            RIWAYAT DATA
        ================================= */}

        <section className="mt-8">

          <HistoryTable
            data={historyData}
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