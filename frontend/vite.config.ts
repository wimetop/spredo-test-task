import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The frontend only ever talks to our backend; the CoinGecko key stays server-side.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
