import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Спільний бекенд: cd backend && uv run uvicorn app.main:app --reload (порт 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174, // 5173 зайнятий продуктовим фронтом команди
    proxy: {
      "/geo": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
    },
  },
});
