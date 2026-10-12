import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { createDemoBridgePlugin } from './dev/tasnimDemoBridge.js'

export default defineConfig(({ command }) => ({
  plugins: [
    react(),
    tailwindcss(),
    ...(command === 'serve' ? [createDemoBridgePlugin()].filter(Boolean) : []),
  ],
}))
