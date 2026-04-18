import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev server proxy to forward API and WS requests to backend (port 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward REST API calls
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/api')
      },
      // Forward websocket connections (if any use /ws)
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true
      }
    }
  }
})
