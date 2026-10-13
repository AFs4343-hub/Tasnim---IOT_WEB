import { useMemo, useState } from 'react'

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

import {
  witaDate, witaDateTime, witaDayKey, witaTime,
} from '../services/timeFormat.js'


// Informasi parameter
const PARAMETERS = {
  ph: { label: 'pH', unit: '' },
  tds: { label: 'TDS', unit: 'ppm' },
  turbidity: { label: 'Turbiditas', unit: 'NTU' }
}

// Rentang tampilan grafik (jumlah record terakhir).
// Data alat = 1 record per 5 menit → 24 = 2 jam, 72 = 6 jam.
const RANGES = [
  { id: 24, label: '2 jam' },
  { id: 72, label: '6 jam' },
  { id: 0, label: 'Semua' }
]

const NODE_LINES = [
  { node: 'N0', color: '#22d3ee' },
  { node: 'N1', color: '#34d399' },
  { node: 'N2', color: '#f59e0b' }
]


function ToggleButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        active
          ? 'bg-cyan-400 font-semibold text-slate-950'
          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
      }`}
    >
      {children}
    </button>
  )
}


function TrendChart({ data = [] }) {

  // Parameter yang sedang ditampilkan
  const [parameter, setParameter] = useState('ph')
  const [range, setRange] = useState(24)

  const current = PARAMETERS[parameter]

  const chartData = useMemo(() => {
    const visible = range ? data.slice(-range) : data
    const multiDay = new Set(
      visible.map(row => witaDayKey(row.timestamp))
    ).size > 1

    return visible.map(row => ({
      ...row,
      axisLabel: multiDay
        ? `${witaDate(row.timestamp)} ${witaTime(row.timestamp)}`
        : witaTime(row.timestamp)
    }))
  }, [data, range])

  const hasValues = chartData.some(row =>
    NODE_LINES.some(({ node }) => row[`${node}_${parameter}`] != null)
  )


  return (

    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      {/* HEADER GRAFIK */}
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">

        <div>
          <h2 className="text-xl font-bold">
            Tren Kualitas Air
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Perbandingan {current.label} N0, N1, dan N2 terhadap waktu (WITA).
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:items-end">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Parameter">
            {Object.entries(PARAMETERS).map(([id, info]) => (
              <ToggleButton
                key={id}
                active={parameter === id}
                onClick={() => setParameter(id)}
              >
                {info.label}
              </ToggleButton>
            ))}
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Rentang waktu">
            {RANGES.map(option => (
              <ToggleButton
                key={option.id}
                active={range === option.id}
                onClick={() => setRange(option.id)}
              >
                {option.label}
              </ToggleButton>
            ))}
          </div>
        </div>

      </div>


      {/* KONDISI DATA KOSONG */}
      {chartData.length === 0 || !hasValues ? (

        <div className="flex h-80 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-800 text-center">
          <p className="text-slate-400">
            Belum ada data historis untuk ditampilkan.
          </p>
          <p className="max-w-md text-xs text-slate-500">
            Grafik terisi otomatis dari history 5 menit di Firebase
            atau dari file CSV/JSON yang dibuka.
          </p>
        </div>

      ) : (

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>

              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />

              <XAxis
                dataKey="axisLabel"
                stroke="#94a3b8"
                tick={{ fontSize: 12 }}
                minTickGap={24}
              />

              <YAxis
                stroke="#94a3b8"
                tick={{ fontSize: 12 }}
                domain={['auto', 'auto']}
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '12px'
                }}
                labelStyle={{ color: '#cbd5e1' }}
                labelFormatter={(_label, payload) =>
                  payload?.[0]?.payload?.timestamp
                    ? witaDateTime(payload[0].payload.timestamp, { seconds: false })
                    : _label
                }
                formatter={(value, name) => [
                  `${value}${current.unit ? ` ${current.unit}` : ''}`,
                  name
                ]}
              />

              <Legend />

              {NODE_LINES.map(({ node, color }) => (
                <Line
                  key={node}
                  type="monotone"
                  dataKey={`${node}_${parameter}`}
                  name={node}
                  stroke={color}
                  strokeWidth={2.5}
                  dot={chartData.length <= 30 ? { r: 2 } : false}
                  connectNulls={false}
                />
              ))}

            </LineChart>
          </ResponsiveContainer>
        </div>

      )}

    </div>

  )

}

export default TrendChart
