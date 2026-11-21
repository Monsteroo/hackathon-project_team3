/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Одне зі значень API_KEYS з backend/.env. У бандлі не секретний (див. tools/geo-voice-testbench/HANDOFF.md). */
  readonly VITE_API_KEY?: string
  /** `kyiv-center` — замість GPS завжди центр Києва (тимчасовий мок, src/features/location/position.ts). */
  readonly VITE_MOCK_LOCATION?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
