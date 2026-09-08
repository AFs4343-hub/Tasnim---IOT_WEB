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

const data = [
  { time: '08:00', N0: 7.2, N1: 7.1, N2: 7.0 },
  { time: '09:00', N0: 7.2, N1: 7.2, N2: 6.9 },
  { time: '10:00', N0: 7.3, N1: 7.1, N2: 6.8 },
  { time: '11:00', N0: 7.2, N1: 7.0, N2: 6.7 },
  { time: '12:00', N0: 7.2, N1: 7.1, N2: 6.8 },
]

function TrendChart() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="mb-6">
        <h2 className="text-xl font-bold">
          Tren pH Antar-Node
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Perbandingan perubahan pH N0, N1, dan N2 terhadap waktu.
        </p>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>

            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />

            <XAxis
              dataKey="time"
              stroke="#94a3b8"
            />

            <YAxis
              domain={[6, 8]}
              stroke="#94a3b8"
            />

            <Tooltip />

            <Legend />

            <Line
              type="monotone"
              dataKey="N0"
              stroke="#22d3ee"
              strokeWidth={3}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="N1"
              stroke="#34d399"
              strokeWidth={3}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="N2"
              stroke="#f59e0b"
              strokeWidth={3}
              dot={false}
            />

          </LineChart>
        </ResponsiveContainer>
      </div>

    </div>
  )
}

export default TrendChart