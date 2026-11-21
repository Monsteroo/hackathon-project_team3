import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Локально бекенд: .venv/bin/uvicorn backend.app:app --reload (порт 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
