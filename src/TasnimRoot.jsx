import { Suspense, lazy } from 'react'
import SetupNotice from './components/SetupNotice.jsx'
import StartupErrorBoundary from './components/StartupErrorBoundary.jsx'
import { missingFirebaseConfig } from './services/firebaseConfigCheck.js'

// Dimuat terpisah agar error inisialisasi Firebase tampil sebagai pesan,
// bukan layar putih.
const TasnimEntry = lazy(() => import('./TasnimEntry.jsx'))
const missing = missingFirebaseConfig(import.meta.env)

export default function TasnimRoot() {
  if (missing.length) return <SetupNotice missing={missing} />
  return (
    <StartupErrorBoundary>
      <Suspense fallback={<p className="min-h-screen bg-slate-950 p-6 text-slate-300">Memuat TAS[N]IM…</p>}>
        <TasnimEntry />
      </Suspense>
    </StartupErrorBoundary>
  )
}
