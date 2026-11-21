/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

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
    // Бекенд API: змініть ціль, коли буде відомий порт бекенду.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
})
