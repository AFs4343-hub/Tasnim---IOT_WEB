import TrendChart from './components/TrendChart'
import NodeCard from './components/NodeCard'

function App() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">

      <div className="mx-auto max-w-7xl px-6 py-10">

        {/* Header */}
        <header className="mb-10">
          <p className="text-sm font-semibold tracking-widest text-cyan-400">
            MULTI-NODE IoT-WEB
          </p>

          <h1 className="mt-2 text-5xl font-bold">
            TASNIM
          </h1>

          <p className="mt-3 max-w-3xl text-slate-400">
            Surveilans Kualitas Air Irigasi Budidaya Ikan melalui
            pemantauan multi-node secara real-time.
          </p>
        </header>

        {/* Status sistem */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-5">

          <div className="flex items-center justify-between">

            <div>
              <p className="text-sm text-slate-400">
                Status Sistem
              </p>

              <h2 className="mt-1 text-xl font-semibold">
                Monitoring Aktif
              </h2>
            </div>

            <div className="flex items-center gap-2 text-emerald-400">
              <span className="h-3 w-3 rounded-full bg-emerald-400"></span>
              Online
            </div>

          </div>

        </section>

        {/* Node monitoring */}
        <section>

          <div className="mb-5">
            <h2 className="text-2xl font-bold">
              Monitoring Node
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Data kualitas air pada setiap titik jaringan irigasi.
            </p>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">

            <NodeCard
              node="N0"
              location="Hulu / Baseline"
              ph="7.21"
              tds="201"
              turbidity="8"
              status="Normal"
            />

            <NodeCard
              node="N1"
              location="Cabang Irigasi 1"
              ph="7.18"
              tds="204"
              turbidity="9"
              status="Normal"
            />

            <NodeCard
              node="N2"
              location="Cabang Irigasi 2"
              ph="6.82"
              tds="238"
              turbidity="18"
              status="Normal"
            />

          </div>

        </section>

        {/* Grafik tren */}
        <section className="mt-8">
          <TrendChart />
        </section>

      </div>

    </main>
  )
}

export default App