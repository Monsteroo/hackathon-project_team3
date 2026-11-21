/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Одне зі значень API_KEYS з backend/.env. У бандлі не секретний (див. tools/geo-voice-testbench/HANDOFF.md). */
  readonly VITE_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
