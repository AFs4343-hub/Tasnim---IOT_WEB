import { StrictMode, Suspense, lazy, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import tasnimConfig from '../tasnim.config.json'

// Candidate view is not exposed in any standard build. Explicit build-time
// opt-in is required; simulation remains the source and default view.
const candidateEnabled = import.meta.env.VITE_TASNIM_HARDWARE_V2_PREVIEW === 'YES'
  && tasnimConfig.activeDataRoot === 'simulation'
  && tasnimConfig.mode === 'SIMULATION'
const HardwareV2Candidate = lazy(() => import('./HardwareV2Candidate.jsx'))

function TasnimEntry() {
  const [view, setView] = useState('simulation')
  return (
    <>
      {candidateEnabled && (
        <div className="relative z-[3000] flex flex-wrap items-center justify-center gap-3 border-b border-amber-600/30 bg-slate-900 p-3 text-sm text-white">
          <strong className="text-amber-300">Pengembangan lokal — pratinjau hardware V2</strong>
          <button type="button" onClick={() => setView('simulation')}
            aria-pressed={view === 'simulation'}
            className="rounded-lg border border-slate-600 px-3 py-1 aria-pressed:bg-cyan-600">
            Dashboard simulasi
          </button>
          <button type="button" onClick={() => setView('hardware')}
            aria-pressed={view === 'hardware'}
            className="rounded-lg border border-slate-600 px-3 py-1 aria-pressed:bg-cyan-600">
            Hardware V2 (login)
          </button>
        </div>
      )}
      {candidateEnabled && view === 'hardware'
        ? <Suspense fallback={<p className="p-6">Memuat pratinjau hardware…</p>}>
          <HardwareV2Candidate />
        </Suspense>
        : <App />}
    </>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TasnimEntry />
  </StrictMode>,
)
