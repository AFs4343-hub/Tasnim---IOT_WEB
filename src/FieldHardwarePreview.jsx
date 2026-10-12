import { useEffect, useState } from 'react'
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth'
import App from './App.jsx'
import { firebaseApp } from './services/firebase.js'

// Development only; the parent entry never mounts this in production.
const auth = getAuth(firebaseApp)

export default function FieldHardwarePreview() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => onAuthStateChanged(auth, current => {
    setUser(current)
    setChecking(false)
    setError('')
  }, () => {
    setUser(null)
    setChecking(false)
    setError('Firebase Authentication tidak tersedia.')
  }), [])

  const login = async e => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await signInWithEmailAndPassword(auth, email, password)
      setPassword('')
    } catch {
      setError('Login Firebase gagal. Periksa akun dan izin baca hardware_test.')
    } finally {
      setBusy(false)
    }
  }

  return <div className="min-h-screen bg-slate-950 text-white">
    <div className="border-b border-amber-600/40 bg-slate-900 px-5 py-3">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div>
          <strong className="text-amber-300">PRATINJAU FIREBASE ALAT ASLI — BACA SAJA</strong>
          <p className="text-xs text-slate-400">
            Mode pengembangan. Tidak menulis ke Firebase atau mengubah firmware.
          </p>
        </div>
        {user && <button type="button" onClick={() => signOut(auth)}
          className="rounded-lg border border-slate-600 px-4 py-2 text-sm">
          Keluar
        </button>}
      </div>
    </div>
    {checking && <p role="status" className="mx-auto max-w-lg p-8">Memeriksa login Firebase…</p>}
    {!checking && !user && <form onSubmit={login}
      className="mx-auto mt-10 max-w-md space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6">
      <h1 className="text-xl font-bold">Masuk untuk melihat data alat</h1>
      <p className="text-sm text-slate-400">
        Masuk dengan akun Firebase Authentication yang sudah diizinkan membaca hardware_test.
        Kata sandi tidak disimpan di repository.
      </p>
      <label className="block text-sm">Email
        <input type="email" required autoComplete="username" value={email}
          onChange={e => setEmail(e.target.value)}
          className="mt-1 w-full rounded-md bg-slate-950 p-3"/>
      </label>
      <label className="block text-sm">Kata sandi
        <input type="password" required autoComplete="current-password" value={password}
          onChange={e => setPassword(e.target.value)}
          className="mt-1 w-full rounded-md bg-slate-950 p-3"/>
      </label>
      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      <button disabled={busy} type="submit"
        className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">
        {busy ? 'Menghubungkan…' : 'Masuk'}
      </button>
    </form>}
    {!checking && user && <App />}
  </div>
}
