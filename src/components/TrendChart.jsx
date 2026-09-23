import { useState } from 'react'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'


function TrendChart({ data = [] }) {

  // Parameter yang sedang ditampilkan
  const [parameter, setParameter] = useState('ph')


  // Informasi parameter
  const parameterInfo = {

    ph: {
      label: 'pH',
      unit: ''
    },

    tds: {
      label: 'TDS',
      unit: 'ppm'
    },

    turbidity: {
      label: 'Turbiditas',
      unit: 'NTU'
    }

  }


  const current =
    parameterInfo[parameter]


  return (

    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">


      {/* =========================
          HEADER GRAFIK
      ========================== */}

      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">


        <div>

          <h2 className="text-xl font-bold">
            Tren Kualitas Air
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Perbandingan {current.label} N0, N1,
            dan N2 terhadap waktu.
          </p>

        </div>



        {/* =========================
            PILIH PARAMETER
        ========================== */}

        <div className="flex flex-wrap gap-2">


          <button

            onClick={() =>
              setParameter('ph')
            }

            className={`rounded-lg px-4 py-2 text-sm transition ${
              parameter === 'ph'
                ? 'bg-cyan-400 font-semibold text-slate-950'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >

            pH

          </button>



          <button

            onClick={() =>
              setParameter('tds')
            }

            className={`rounded-lg px-4 py-2 text-sm transition ${
              parameter === 'tds'
                ? 'bg-cyan-400 font-semibold text-slate-950'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >

            TDS

          </button>



          <button

            onClick={() =>
              setParameter('turbidity')
            }

            className={`rounded-lg px-4 py-2 text-sm transition ${
              parameter === 'turbidity'
                ? 'bg-cyan-400 font-semibold text-slate-950'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >

            Turbiditas

          </button>


        </div>

      </div>



      {/* =========================
          KONDISI DATA KOSONG
      ========================== */}

      {data.length === 0 ? (

        <div className="flex h-80 items-center justify-center">

          <p className="text-slate-500">
            Belum ada data historis Firebase.
          </p>

        </div>

      ) : (


        /* =========================
            GRAFIK
        ========================== */

        <div className="h-80 w-full">


          <ResponsiveContainer
            width="100%"
            height="100%"
          >

            <LineChart
              data={data}
            >


              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#334155"
              />


              <XAxis
                dataKey="time"
                stroke="#94a3b8"
              />


              <YAxis
                stroke="#94a3b8"
              />


              <Tooltip

                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '12px'
                }}

                labelStyle={{
                  color: '#cbd5e1'
                }}

                formatter={(value) => [
                  `${value}${current.unit ? ` ${current.unit}` : ''}`
                ]}

              />


              <Legend />


              {/* =====================
                  NODE N0
              ====================== */}

              <Line
                type="monotone"
                dataKey={`N0_${parameter}`}
                name="N0"
                stroke="#22d3ee"
                strokeWidth={3}
                dot={false}
              />


              {/* =====================
                  NODE N1
              ====================== */}

              <Line
                type="monotone"
                dataKey={`N1_${parameter}`}
                name="N1"
                stroke="#34d399"
                strokeWidth={3}
                dot={false}
              />


              {/* =====================
                  NODE N2
              ====================== */}

              <Line
                type="monotone"
                dataKey={`N2_${parameter}`}
                name="N2"
                stroke="#f59e0b"
                strokeWidth={3}
                dot={false}
              />


            </LineChart>

          </ResponsiveContainer>


        </div>

      )}


    </div>

  )

}


export default TrendChart