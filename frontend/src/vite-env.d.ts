/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Одне зі значень API_KEYS з backend/.env. У бандлі не секретний (див. tools/geo-voice-testbench/HANDOFF.md). */
  readonly VITE_API_KEY?: string
  /** Порожній локально (працює Vite proxy); у продакшені на Render задається хост/URL бекенду. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
