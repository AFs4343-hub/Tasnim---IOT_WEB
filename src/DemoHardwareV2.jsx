import { useEffect, useMemo, useState } from 'react'
import { analysisStatus, historyRows, latestNodes, NODE_IDS, wita } from './services/hardwareV2View'
import HardwareV2QualitySummary from './components/HardwareV2QualitySummary'

const USERS = ['admin', 'manager', 'viewer']
const FIELDS = ['ph', 'tds', 'turbidity']

async function requestDemo(path, options) {
  const response = await fetch('/__tasnim_demo__/' + path, { cache: 'no-store', ...options })
  const result = await response.json()
  if (!response.ok) throw Error(result.error || 'Emulator tidak tersedia.')
  return result
}

export default function DemoHardwareV2() {
  const [email, setEmail] = useState('viewer@tasnim-auth-demo.invalid')
  const [password, setPassword] = useState('')
  const [session, setSession] = useState(null)
  const [snapshot, setSnapshot] = useState(null)
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [historyLimit, setHistoryLimit] = useState(60)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!session) return
    let active = true
    const refresh = () => requestDemo('snapshot?limit=' + historyLimit, {
      headers: { Authorization: 'Bearer ' + session.token },
    }).then(value => {
      if (active) { setSnapshot(value); setMessage('') }
    }).catch(error => {
      if (!active) return
      setSnapshot(null)
      setMessage(error.message)
      if (/login|ditolak/i.test(error.message)) setSession(null)
    })
    refresh()
    const timer = setInterval(refresh, 30_000)
    return () => { active = false; clearInterval(timer) }
  }, [session, historyLimit, reload])

  const parsed = useMemo(() => {
    if (!snapshot) return { nodes: null, rows: [], ai: null }
    const nodes = latestNodes(snapshot.nodes)
    const rows = historyRows(snapshot.history, historyLimit)
    return { nodes, rows, ai: analysisStatus(snapshot.analysis, rows) }
  }, [snapshot, historyLimit])

  async function login(event) {
    event.preventDefault()
    setPending(true)
    setMessage('')
    try {
      const value = await requestDemo('login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      setSession({ token: value.token, role: value.role })
      setPassword('')
    } catch (error) { setMessage(error.message) }
    finally { setPending(false) }
  }
  function logout() {
    setSession(null)
    setSnapshot(null)
    setPassword('')
    setMessage('')
    setHistoryLimit(60)
  }

  return <main className="min-h-screen bg-slate-950 px-4 py-10 text-white">
    <div className="mx-auto max-w-7xl">
      <p className="text-xs font-bold tracking-widest text-amber-300">TASNIM · FIREBASE EMULATOR SAJA</p>
      <h1 className="mt-2 text-3xl font-bold">Demo Login & Dashboard Hardware V2</h1>
      <p className="mt-2 max-w-3xl text-sm text-slate-300">
        Data sintetis untuk demonstrasi. Tidak terhubung Firebase LIVE,
        tidak memakai sensor fisik, dan dashboard tidak bisa menulis data.
      </p>

      {!session && <section className="mt-8 max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6">
        <h2 className="text-xl font-semibold">Masuk ke akun demo</h2>
        <form onSubmit={login} className="mt-5 space-y-4">
          <label className="block text-sm">Pilih akun
            <select value={email} onChange={e => setEmail(e.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 p-3">
              {USERS.map(r => <option key={r} value={r + '@tasnim-auth-demo.invalid'}>
                {r.toUpperCase()} — {r}@tasnim-auth-demo.invalid
              </option>)}
            </select>
          </label>
          <label className="block text-sm">Kata sandi demo
            <input type="password" autoComplete="off" required value={password}
              onChange={e => setPassword(e.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 p-3" />
          </label>
          <button disabled={pending} type="submit"
            className="rounded-lg bg-cyan-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-50">
            {pending ? 'Memeriksa…' : 'Masuk'}
          </button>
        </form>
        <p className="mt-4 text-xs text-amber-300">
          Akun demo hanya ada selama Emulator berjalan. Jangan gunakan sandi akun produksi.
        </p>
      </section>}

      {session && <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-900 p-4">
        <p>Login berhasil · role <strong className="text-cyan-300">{session.role}</strong></p>
        <div className="flex gap-2">
          <button onClick={() => setReload(n => n + 1)}
            className="rounded-lg border border-slate-600 px-3 py-2 text-sm">Muat ulang</button>
          <button onClick={logout} className="rounded-lg border border-slate-600 px-3 py-2 text-sm">Keluar</button>
        </div>
      </div>}

      {message && <p role="alert" className="mt-4 rounded-lg border border-rose-700 bg-rose-950/30 p-4 text-rose-300">{message}</p>}
      {session && !snapshot && !message && <p role="status" className="mt-5">Mengambil data RTDB Emulator…</p>}

      {session && snapshot && <>
        <div className="mt-6">
          <HardwareV2QualitySummary nodes={parsed.nodes} rows={parsed.rows} />
        </div>
        <section className="grid gap-4 md:grid-cols-3" aria-label="Pengukuran sintetis per node">
          {NODE_IDS.map(n => <article key={n} className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-2xl font-bold">{n}</h2>
            <p className="mt-2 text-sm text-slate-400">Waktu ukur: {wita(parsed.nodes?.[n]?.timestamp)}</p>
            <dl className="mt-4 space-y-3">
              {FIELDS.map(f => <div className="flex justify-between gap-2" key={f}>
                <dt className="text-sm text-slate-300">{f === 'ph' ? 'pH' : f === 'tds' ? 'TDS (ppm)' : 'Turbiditas (NTU)'}</dt>
                <dd className="font-semibold">{parsed.nodes?.[n]?.[f] ?? '—'}</dd>
              </div>)}
            </dl>
          </article>)}
        </section>
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-xl font-semibold">AI V2 — status pratinjau</h2>
          <p className="mt-2 text-sm text-amber-300">Prototipe berbasis simulasi, belum tervalidasi lapangan.</p>
          <p className="mt-2 text-sm text-slate-300">
            {parsed.ai?.state === 'SLOT_ALIGNED_UNVERIFIED'
              ? 'Waktu slot AI cocok dengan history, tetapi asal data dan akurasi AI belum diverifikasi.'
              : parsed.ai?.state === 'STALE_OR_INCOMPLETE'
                ? 'Slot terbaru belum lengkap atau hasil AI tidak sinkron.'
                : 'Analisis belum memenuhi kontrak pembacaan.'}
          </p>
        </section>
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">History 5 menit</h2>
            <button disabled={historyLimit >= 240}
              onClick={() => setHistoryLimit(n => Math.min(n + 60, 240))}
              className="rounded-lg border border-slate-600 px-3 py-2 text-sm disabled:opacity-50">Muat lebih banyak</button>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr className="border-b border-slate-700 text-slate-400">
                <th className="p-2">Slot WITA</th>
                {NODE_IDS.map(n => <th key={n} className="p-2">{n}: pH / TDS / Turb.</th>)}
                <th className="p-2">Kualitas</th>
              </tr></thead>
              <tbody>{[...parsed.rows].reverse().map(row => <tr key={row.slot} className="border-b border-slate-800">
                <td className="whitespace-nowrap p-2">{wita(row.slot)}</td>
                {NODE_IDS.map(n => <td key={n} className="whitespace-nowrap p-2">
                  {FIELDS.map(f => row.nodes[n]?.[f] ?? '—').join(' / ')}
                </td>)}
                <td className="p-2">{row.complete ? 'Lengkap' : 'Tidak lengkap'}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
      </>}
    </div>
  </main>
}
