import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import TasnimRoot from './TasnimRoot.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TasnimRoot />
  </StrictMode>,
)
