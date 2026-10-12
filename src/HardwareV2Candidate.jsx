import { useEffect, useMemo, useState } from 'react'
import {
  getAuth, getIdTokenResult, onIdTokenChanged,
  signInWithEmailAndPassword, signOut,
} from 'firebase/auth'
import { ref, onValue, query, orderByKey, limitToLast } from 'firebase/database'
import { firebaseApp, database } from './services/firebase'
import HardwareV2QualitySummary from './components/HardwareV2QualitySummary'
import {
  analysisStatus, getRoleFromClaims, historyRows, latestNodes, NODE_IDS, wita,
} from './services/hardwareV2View'

const auth = getAuth(firebaseApp)
const SENSOR_FIELDS = ['ph', 'tds', 'turbidity']
const PARAM_LABELS = { ph: 'pH', tds: 'TDS (ppm)', turbidity: 'Turbiditas (NTU)' }
const INITIAL = { latest: null, history: [], analysis: null, state: 'connecting', error: null }

function Measurement({ data, field }) {
  const value = data?.[field]
  return <span>{typeof value === 'number' && Number.isFinite(value) ? value.toFixed(field === 'ph' ? 2 : 1) : '—'}</span>
}

function SignInPanel({ onSignIn, pending, error }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const submit = async (event) => {
    event.preventDefault()
    await onSignIn(email, password)
    setPassword('')
  }
  return (
    <section className="mx-auto max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6">
      <h2 className="text-xl font-semibold">Masuk untuk melihat hardware V2</h2>
      <p className="mt-2 text-sm text-slate-400">
        Akses hanya untuk akun Firebase yang memiliki custom claim
        tasnim_role = admin, manager, atau viewer. Tidak ada akses tulis dari browser.
      </p>
      <form className="mt-5 space-y-4" onSubmit={submit}>
        <label className="block text-sm text-slate-300">
          Email
          <input className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
            type="email" autoComplete="username" required value={email}
            onChange={e => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm text-slate-300">
          Kata sandi
          <input className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
            type="password" autoComplete="current-password" required value={password}
            onChange={e => setPassword(e.target.value)} />
        </label>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
        <button disabled={pending} type="submit"
          className="rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">
          {pending ? 'Memeriksa akun…' : 'Masuk'}
        </button>
      </form>
    </section>
  )
}

function HardwarePanel({ role, onSignOut }) {
  const [historyLimit, setHistoryLimit] = useState(60)
  const [snapshot, setSnapshot] = useState(INITIAL)

  useEffect(() => {
    let active = true
    let failed = false
    setSnapshot(INITIAL)

    const fail = (error) => {
      if (!active || failed) return
      failed = true
      const denied = error?.code === 'PERMISSION_DENIED' || error?.code === 'permission_denied'
      setSnapshot({
        latest: null, history: [], analysis: null, state: 'error',
        error: denied
          ? 'Izin baca ditolak oleh Firebase Rules. Periksa claim dan aturan database.'
          : 'Data hardware tidak dapat dimuat. Periksa koneksi dan konfigurasi Firebase.',
      })
    }

    const subscriptions = [
      onValue(ref(database, 'hardware_test/nodes'), snap => {
        if (!active || failed) return
        setSnapshot(s => ({ ...s, latest: latestNodes(snap.val()), state: 'connected' }))
      }, fail),
      onValue(query(ref(database, 'hardware_test/history'),
        orderByKey(), limitToLast(historyLimit + 1)), snap => {
        if (!active || failed) return
        setSnapshot(s => ({ ...s, history: historyRows(snap.val(), historyLimit), state: 'connected' }))
      }, fail),
      onValue(ref(database, 'hardware_test/analysis/latest'), snap => {
        if (!active || failed) return
        setSnapshot(s => ({ ...s, analysis: snap.val(), state: 'connected' }))
      }, fail),
    ]
    return () => {
      active = false
      subscriptions.forEach(unsubscribe => unsubscribe())
    }
  }, [historyLimit, role])

  const checkedAI = useMemo(
    () => analysisStatus(snapshot.analysis, snapshot.history),
    [snapshot.analysis, snapshot.history],
  )

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-900 p-4">
        <p className="text-sm">Akses: <strong>{role}</strong> · hanya baca · /hardware_test</p>
        <button onClick={onSignOut} className="rounded-lg border border-slate-600 px-3 py-2 text-sm">Keluar</button>
      </div>

      {snapshot.state === 'connecting' && <p role="status" className="mb-6 text-slate-300">Memuat telemetri hardware…</p>}
      {snapshot.error && <p role="alert" className="mb-6 rounded-lg border border-rose-500/40 p-4 text-rose-300">{snapshot.error}</p>}

      {snapshot.state !== 'error' && (
        <>
          <HardwareV2QualitySummary nodes={snapshot.latest} rows={snapshot.history} />
          <section className="grid gap-4 md:grid-cols-3" aria-label="Pengukuran terbaru per node">
            {NODE_IDS.map(node => {
              const measured = snapshot.latest?.[node]
              return (
                <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5" key={node}>
                  <h2 className="text-xl font-bold">{node}</h2>
                  <p className="mt-1 text-xs text-slate-400">
                    {node === 'N0' ? 'Hulu / baseline' : node === 'N1' ? 'Cabang 1' : 'Cabang 2'}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">Waktu ukur: {wita(measured?.timestamp)}</p>
                  <dl className="mt-4 space-y-2">
                    {SENSOR_FIELDS.map(field => (
                      <div className="flex justify-between gap-2" key={field}>
                        <dt className="text-sm text-slate-400">{PARAM_LABELS[field]}</dt>
                        <dd className="font-medium"><Measurement data={measured} field={field} /></dd>
                      </div>
                    ))}
                  </dl>
                  {!measured && <p className="mt-3 text-sm text-amber-300">Data V2 belum tersedia/valid.</p>}
                  {measured?.requiresReview && <p className="mt-3 text-sm text-amber-300">
                    Quality flags perlu review: {measured.flags.join(', ')}
                  </p>}
                </div>
              )
            })}
          </section>

          <section className="mt-7 rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-xl font-semibold">Hasil AI terbaru</h2>
            <p className="mt-2 text-sm text-amber-300">
              Model PROTOTYPE_SIMULATION — belum tervalidasi ilmiah dengan data lapangan.
            </p>
            <p className="mt-2 text-sm text-slate-300">
              {checkedAI.state === 'SLOT_ALIGNED_UNVERIFIED' ? 'Waktu hasil AI cocok dengan history lengkap, tetapi kecocokan isi sumber belum diverifikasi browser.'
                : checkedAI.state === 'STALE_OR_INCOMPLETE' ? 'Hasil AI tidak sinkron atau history terakhir belum lengkap.'
                  : checkedAI.state === 'UNTRUSTED_ANALYSIS' ? 'Metadata analisis belum cocok dengan kontrak V2.'
                    : 'Belum ada hasil analisis yang dapat dibaca.'}
            </p>
            {checkedAI.analysis && <p className="mt-2 text-sm">
              Slot: {wita(checkedAI.analysis.source_timestamp_ms)} ·
              Status model: {checkedAI.analysis.status === 'NORMAL' || checkedAI.analysis.status === 'ANOMALI'
                ? checkedAI.analysis.status : 'tidak diketahui'}
            </p>}
          </section>

          <section className="mt-7 rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-semibold">History V2 (5 menit)</h2>
              <button disabled={historyLimit >= 240} onClick={() => setHistoryLimit(x => Math.min(x + 60, 240))}
                className="rounded-lg border border-slate-600 px-3 py-2 text-sm disabled:opacity-40">
                Muat lebih banyak (maks. 240)
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Setiap slot terdiri dari tiga node. Data invalid ditampilkan sebagai “—”, bukan nol palsu.
              Waktu dalam WITA.
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead><tr className="border-b border-slate-700 text-slate-400">
                  <th className="p-2">Slot</th>
                  {NODE_IDS.map(n => <th key={n} className="p-2">{n} (pH / TDS / turb.)</th>)}
                  <th className="p-2">Kualitas</th>
                </tr></thead>
                <tbody>
                  {[...snapshot.history].reverse().map(row => (
                    <tr className="border-b border-slate-800" key={row.slot}>
                      <td className="whitespace-nowrap p-2">{wita(row.slot)}</td>
                      {NODE_IDS.map(n => <td className="whitespace-nowrap p-2" key={n}>
                        {SENSOR_FIELDS.map(f => (
                          <span key={f} className="mr-1"><Measurement data={row.nodes[n]} field={f}/>{f !== 'turbidity' ? ' /' : ''}</span>
                        ))}
                      </td>)}
                      <td className="p-2">{row.complete ? 'Lengkap (struktural)' : 'Tidak lengkap / perlu review'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {snapshot.history.length === 0 && snapshot.state === 'connected'
              && <p className="mt-3 text-sm text-amber-300">Belum ada history V2 yang tersedia.</p>}
          </section>
        </>
      )}
    </>
  )
}

export default function HardwareV2Candidate() {
  const [access, setAccess] = useState({ state: 'checking', role: null })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    let requestVersion = 0
    let forceFirstUserRefresh = true
    // Unlike onAuthStateChanged, this also rechecks claims when Firebase
    // refreshes an existing user's ID token. Database Rules remain the
    // authoritative enforcement boundary.
    const unsubscribe = onIdTokenChanged(auth, async user => {
      const version = ++requestVersion
      if (!active) return
      setAccess({ state: 'checking', role: null })
      if (!user) {
        setAccess({ state: 'signed-out', role: null })
        return
      }
      try {
        // Force only the first signed-in check: forcing on EVERY token
        // change would cause a self-triggered token refresh loop.
        const forceRefresh = forceFirstUserRefresh
        forceFirstUserRefresh = false
        const result = await getIdTokenResult(user, forceRefresh)
        if (!active || version !== requestVersion || auth.currentUser?.uid !== user.uid) return
        const role = getRoleFromClaims(result.claims)
        setAccess({ state: role ? 'ready' : 'forbidden', role })
      } catch {
        if (active && version === requestVersion) {
          setAccess({ state: 'error', role: null })
        }
      }
    })
    return () => {
      active = false
      requestVersion++
      unsubscribe()
    }
  }, [])

  const handleSignIn = async (email, password) => {
    setPending(true)
    setError(null)
    try {
      await signInWithEmailAndPassword(auth, email, password)
    } catch {
      setError('Login gagal. Periksa kredensial dan konfigurasi Firebase Authentication.')
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-white">
      <div className="mx-auto max-w-7xl">
        <p className="text-sm font-semibold tracking-wider text-cyan-300">TASNIM — CANDIDATE HARDWARE V2</p>
        <h1 className="mt-2 text-3xl font-bold">Pratinjau penelitian (hanya baca)</h1>
        <p className="mb-7 mt-2 max-w-3xl text-sm text-amber-300">
          Eksperimental. Membaca Firebase /hardware_test hanya setelah login dan pemeriksaan role.
          Tidak mengubah mode SIMULATION, database, firmware atau hasil sensor.
        </p>
        {access.state === 'checking' && <p role="status">Memverifikasi Firebase Authentication…</p>}
        {access.state === 'signed-out' && <SignInPanel onSignIn={handleSignIn} pending={pending} error={error}/>}
        {access.state === 'forbidden' && <section role="alert" className="rounded-xl border border-amber-700 p-5">
          Akun terautentikasi, tetapi tidak memiliki claim tasnim_role yang diizinkan.
          <button onClick={() => signOut(auth)} className="ml-3 underline">Keluar</button>
        </section>}
        {access.state === 'error' && <section role="alert" className="rounded-xl border border-rose-700 p-5">
          Verifikasi peran gagal. Tidak ada pembacaan data hardware dilakukan.
          <button onClick={() => signOut(auth)} className="ml-3 underline">Keluar</button>
        </section>}
        {access.state === 'ready' && <HardwarePanel role={access.role} onSignOut={() => signOut(auth)}/>}
      </div>
    </main>
  )
}
