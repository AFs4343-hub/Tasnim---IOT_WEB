import { useState } from 'react'


function StatisticsPanel({
  data = []
}) {

  const [parameter, setParameter] =
    useState('ph')


  const parameterInfo = {

    ph: {
      label: 'pH',
      unit: '',
      digits: 2
    },

    tds: {
      label: 'TDS',
      unit: 'ppm',
      digits: 1
    },

    turbidity: {
      label: 'Turbiditas',
      unit: 'NTU',
      digits: 1
    }

  }


  const current =
    parameterInfo[parameter]


  const calculateStats = (values) => {

    const cleanValues =
      values.filter(
        (value) =>
          Number.isFinite(value)
      )


    const n =
      cleanValues.length


    if (n === 0) {

      return {
        n: 0,
        mean: null,
        min: null,
        max: null,
        std: null
      }

    }


    const mean =
      cleanValues.reduce(
        (sum, value) =>
          sum + value,
        0
      ) / n


    const min =
      Math.min(...cleanValues)


    const max =
      Math.max(...cleanValues)


    let std = 0


    // Simpangan baku sampel (n - 1)
    if (n > 1) {

      const variance =
        cleanValues.reduce(
          (sum, value) =>
            sum +
            Math.pow(
              value - mean,
              2
            ),
          0
        ) / (n - 1)


      std =
        Math.sqrt(variance)

    }


    return {
      n,
      mean,
      min,
      max,
      std
    }

  }


  const getNodeStats = (node) => {

    const key =
      `${node}_${parameter}`


    const values =
      data.map(
        (record) =>
          record[key] != null
            ? Number(record[key])
            : NaN
      )


    return calculateStats(values)

  }


  const formatValue = (value) => {

    if (value === null) {
      return '—'
    }


    const formatted =
      Number(value).toFixed(
        current.digits
      )


    return current.unit
      ? `${formatted} ${current.unit}`
      : formatted

  }


  const nodeStats = {

    N0: getNodeStats('N0'),
    N1: getNodeStats('N1'),
    N2: getNodeStats('N2')

  }


  function NodeStatistics({
    node,
    location,
    stats
  }) {

    return (

      <div className="rounded-xl border border-slate-800 bg-slate-950 p-5">


        <div className="mb-4">

          <p className="text-xs text-slate-500">
            {location}
          </p>

          <h3 className="mt-1 text-lg font-semibold text-white">
            {node}
          </h3>

        </div>


        <div className="grid grid-cols-2 gap-3">


          <div className="rounded-lg bg-slate-900 p-3">

            <p className="text-xs text-slate-500">
              Rata-rata
            </p>

            <p className="mt-1 font-semibold text-white">
              {formatValue(stats.mean)}
            </p>

          </div>


          <div className="rounded-lg bg-slate-900 p-3">

            <p className="text-xs text-slate-500">
              Simpangan Baku
            </p>

            <p className="mt-1 font-semibold text-white">
              {formatValue(stats.std)}
            </p>

          </div>


          <div className="rounded-lg bg-slate-900 p-3">

            <p className="text-xs text-slate-500">
              Minimum
            </p>

            <p className="mt-1 font-semibold text-white">
              {formatValue(stats.min)}
            </p>

          </div>


          <div className="rounded-lg bg-slate-900 p-3">

            <p className="text-xs text-slate-500">
              Maksimum
            </p>

            <p className="mt-1 font-semibold text-white">
              {formatValue(stats.max)}
            </p>

          </div>


        </div>


        <p className="mt-4 text-xs text-slate-500">
          n = {stats.n} data
        </p>


      </div>

    )

  }


  return (

    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">


      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">


        <div>

          <h2 className="text-xl font-bold">
            Statistik Deskriptif
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Ringkasan data historis {current.label}
            pada N0, N1, dan N2.
          </p>

        </div>



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



      {data.length === 0 ? (

        <div className="flex min-h-48 items-center justify-center">

          <p className="text-sm text-slate-500">
            Belum ada data historis untuk dihitung.
          </p>

        </div>

      ) : (

        <div className="grid gap-4 lg:grid-cols-3">


          <NodeStatistics
            node="N0"
            location="Hulu / Baseline"
            stats={nodeStats.N0}
          />


          <NodeStatistics
            node="N1"
            location="Cabang Irigasi 1"
            stats={nodeStats.N1}
          />


          <NodeStatistics
            node="N2"
            location="Cabang Irigasi 2"
            stats={nodeStats.N2}
          />


        </div>

      )}



      <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/60 p-4">

        <p className="text-xs leading-5 text-slate-500">
          Simpangan baku pada panel ini dihitung sebagai
          simpangan baku sampel menggunakan pembagi n − 1.
          Statistik dihitung dari data history yang sedang
          dimuat pada dashboard.
        </p>

      </div>


    </div>

  )

}


export default StatisticsPanel
