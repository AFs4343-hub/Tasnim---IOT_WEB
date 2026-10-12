import { useEffect, useMemo, useState } from 'react'
import App from './App.jsx'
import { historyRows, latestNodes } from './services/hardwareV2View'
import HardwareV2QualitySummary from './components/HardwareV2QualitySummary'
import OperationalMonitorDemo from './components/OperationalMonitorDemo'

const USERS = ['admin', 'manager', 'viewer']
const EMPTY_DEMO = Object.freeze({ nodes: null, history: null, analysis: null })

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
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!session) return
    let active = true
    const refresh = () => requestDemo('snapshot?limit=240', {
      headers: { Authorization: 'Bearer ' + session.token },
    }).then(data => {
      if (active) { setSnapshot(data); setMessage('') }
    }).catch(error => {
      if (!active) return
      setSnapshot(null)
      setMessage(error.message)
      if (/login|ditolak/i.test(error.message)) setSession(null)
    })
    refresh()
    const timer = setInterval(refresh, 30_000)
    return () => { active = false; clearInterval(timer) }
  }, [session, reload])

  const readiness = useMemo(() => ({
    nodes: latestNodes(snapshot?.nodes),
    rows: historyRows(snapshot?.history, 240),
  }), [snapshot])

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
  }

  return <div className="min-h-screen bg-slate-950 text-white">
    <div className="sticky top-0 z-[2600] border-b border-amber-700/40 bg-slate-900 px-4 py-2">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-amber-300">
            DEMO EMULATOR — website TAS[N]IM asli
          </p>
          <p className="text-xs text-slate-400">
            Semua data di bawah sintetis; tidak tersambung Firebase LIVE.
          </p>
        </div>
        {session && <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>Role: <strong className="text-cyan-300">{session.role}</strong></span>
          <button type="button" onClick={() => setReload(n => n + 1)}
            className="rounded-lg border border-slate-600 px-3 py-1.5">Refresh</button>
          <button type="button" onClick={logout}
            className="rounded-lg border border-slate-600 px-3 py-1.5">Keluar</button>
        </div>}
      </div>
    </div>

    {session && snapshot && <details className="mx-auto max-w-7xl px-4 pt-4">
      <summary className="cursor-pointer text-sm text-cyan-300">
        Lihat pemeriksaan kesiapan data N0/N1/N2 (demo)
      </summary>
      <div className="mt-3">
        <HardwareV2QualitySummary nodes={readiness.nodes} rows={readiness.rows}/>
      </div>
    </details>}

    {session && snapshot && <details className="mx-auto max-w-7xl px-4 pt-3">
      <summary className="cursor-pointer text-sm text-cyan-300">
        Lihat status AI Supervisor dan peringatan operasional (demo)
      </summary>
      <div className="mt-3">
        <OperationalMonitorDemo nodes={readiness.nodes} rows={readiness.rows}
          rawStatus={snapshot.operational_status}/>
      </div>
    </details>}

    {session && message && <p role="alert"
      className="mx-auto mt-4 max-w-7xl rounded-lg border border-rose-700 p-4 text-sm text-rose-300">
      {message}
    </p>}

    {/* Reuse the EXACT existing dashboard and its sections. In demo mode,
        App suppresses every LIVE Firebase listener and receives sanitized
        emulator data only. */}
    <App demoSnapshot={session && snapshot ? snapshot : EMPTY_DEMO}/>

    {!session && <div className="fixed inset-0 z-[3000] flex items-center justify-center overflow-y-auto bg-slate-950/85 p-4 backdrop-blur-sm">
      <section aria-label="Login demo TAS[N]IM"
        className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <p className="text-xs font-semibold tracking-widest text-cyan-400">TASNIM — LOGIN DEMO</p>
        <h2 className="mt-2 text-2xl font-bold">Masuk ke website TAS[N]IM</h2>
        <p className="mt-3 text-sm text-slate-400">
          Setelah login, tampilan asli Monitoring, Grafik, Statistik,
          Spasial, IoT, Peta, AI, dan Riwayat akan terbuka.
          Hanya data sintetis dari Firebase Emulator.
        </p>
        <form onSubmit={login} className="mt-5 space-y-4">
          <label className="block text-sm">Akun demo
            <select value={email} onChange={event => setEmail(event.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 p-3">
              {USERS.map(role => <option key={role} value={role + '@tasnim-auth-demo.invalid'}>
                {role.toUpperCase()} — {role}@tasnim-auth-demo.invalid
              </option>)}
            </select>
          </label>
          <label className="block text-sm">Kata sandi
            <input type="password" autoComplete="off" required value={password}
              onChange={event => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 p-3"/>
          </label>
          {message && <p role="alert" className="text-sm text-rose-300">{message}</p>}
          <button type="submit" disabled={pending}
            className="rounded-lg bg-cyan-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-50">
            {pending ? 'Memverifikasi akun…' : 'Masuk'}
          </button>
        </form>
        <p className="mt-4 text-xs text-amber-300">
          Demo lokal, bukan akun Firebase produksi. Jangan masukkan sandi asli.
        </p>
      </section>
    </div>}
  </div>
}
