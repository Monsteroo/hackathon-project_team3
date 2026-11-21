/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/** Адреса бекенду для проксі. Інший порт — `BACKEND_URL=http://localhost:8010 npm run dev`. */
const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // MapLibre 6 вантажить воркер як окремий ESM-файл поруч із бандлом;
  // pre-bundling Vite ламає цей шлях.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  build: {
    // Чанк MapLibre ~1 MB і вантажиться лише на /results.
    chunkSizeWarningLimit: 1200,
  },
  server: {
    port: 5173,
    // Бекенд FastAPI (backend/, порт 8000): модулі без префікса /api.
    proxy: {
      '/catalog': { target: backend, changeOrigin: true },
      '/geo': { target: backend, changeOrigin: true },
      '/voice': { target: backend, changeOrigin: true },
      '/agent': { target: backend, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Тести перевіряють справжню геолокацію, навіть якщо в .env.local увімкнено мок.
    env: { VITE_MOCK_LOCATION: '' },
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
})
