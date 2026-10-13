import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import TasnimEntry from './TasnimEntry.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TasnimEntry />
  </StrictMode>,
)
