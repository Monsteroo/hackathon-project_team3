# HANDOFF: модулі `geo` і `voice` для фронтенду

Бекенд — спільний FastAPI-сервіс команди (`backend/`, `uv run uvicorn app.main:app`, порт 8000). Наші модулі:
`backend/app/geo/` (магазини поруч, маршрути, геокодинг) і `backend/app/voice/` (голос → текст).
Реальні відповіді: `mocks/09_*` … `mocks/15_*`. Інтерактивно: http://localhost:8000/docs.

Ця папка — **тестовий стенд**, а не продуктовий UI: одна сторінка без стилів, щоб перевірити мікрофон і GPS.
Запуск: `cp` значення `API_KEYS` з `backend/.env` у `tools/geo-voice-testbench/.env.local` як `VITE_API_KEY=…`
(файл ігнорується git), потім `npm ci && npm run dev` → http://localhost:5174.

## Що зробити у фронті (`frontend/`)

1. **Проксі Vite.** Зараз `frontend/vite.config.ts` проксює лише `/api`, а бекенд віддає `/catalog`, `/geo`, `/voice`
   без префікса `/api`. Додайте:
   ```ts
   proxy: {
     '/catalog': { target: 'http://localhost:8000', changeOrigin: true },
     '/geo': { target: 'http://localhost:8000', changeOrigin: true },
     '/voice': { target: 'http://localhost:8000', changeOrigin: true },
   },
   ```
2. **Ключ.** Кожен запит до `/geo/*`, `/voice/*`, `/catalog/*` має заголовок `X-API-Key: <API_KEY>`
   (без нього — 401). Ключ передайте через `VITE_API_KEY` у `frontend/.env.local`. **У бандлі він не секретний**:
   від зловживань платним Groq захищає ліміт 10 запитів/хв з одного IP на `/voice/*` (`VOICE_RATE_LIMIT_PER_MIN`).
3. **Забрати зі стенду** (JS, легко перенести в TS — див. нижче):

| Файл | Що дає |
|---|---|
| `src/api.js` | `api.transcribe(blob)`, `api.parseText(text, source)`, `api.geocode(q, {suggest, near})`, `api.reverse({lat,lng})`, `api.nearby({lat,lng,mode,radiusKm,storeIds})`, `api.route({lat,lng,storeId,mode})`; заголовок ключа; помилки → `ApiError {code, message, status, fallback}` |
| `src/hooks/useVoiceRecorder.js` | Мікрофон: `{start, stop, status, elapsed, error, supported, maxSeconds}`, автостоп 60 с, webm/opus (Chrome) або mp4 (Safari), українські тексти помилок доступу |
| `src/hooks/useWebSpeech.js` | Запасне розпізнавання в браузері (`uk-UA`), коли `/voice/transcribe` повернув `fallback: true` |
| `src/hooks/useGeolocation.js` | `locate()` → `Promise<{lat,lng,accuracy}>`, українські помилки; далі `api.reverse()` для підпису адреси |

Ланцюжок для голосу: `/voice/transcribe` → якщо `detail.fallback` → Web Speech → ручне поле (`/voice/parse-text`,
`source: "manual"`). Поле ручного вводу має бути завжди. Мікрофон і GPS працюють лише на `localhost` або HTTPS.

**Перенесення хуків у TS:** перейменувати `.js` → `.ts`, додати типи з розділу нижче; у `useVoiceRecorder` —
`useRef<MediaRecorder | null>`, `useRef<MediaStream | null>`, `onStop?: (blob: Blob) => void`; у `useWebSpeech` —
оголосити `window.SpeechRecognition | window.webkitSpeechRecognition` (немає в lib.dom) через `declare global` або
`(window as any)`; у `api.ts` — `request<T>(…): Promise<T>` і повернути типи `NearbyResponse`, `RouteResponse`, …

## TypeScript-типи

```ts
export type Mode = 'walk' | 'car'
export type StoreSource = 'zakaz' | 'silpo' | 'osm'

export interface MapsUrls { walking: string; driving: string; transit: string }

export interface Store {
  store_id: string            // Zakaz: "482010105", Сільпо: uuid — як у /catalog; OSM без цін: "osm:n123"
  source: StoreSource
  chain: string               // silpo | novus | auchan | metro | ultramarket | ekomarket | megamarket | zaraz | epicentr
  chain_name: string          // «Сільпо», «NOVUS» — для показу
  name: string
  city: string
  address: string
  lat: number
  lng: number
  place_id: string            // однаковий для магазинів в одній будівлі → групуйте маркери
  alt_store_ids: string[]     // інші ID того ж магазину (дві філії Сільпо за однією адресою)
  has_online_prices: boolean  // offers_count >= 50 у каталозі
  offers_count: number | null
  online_catalog: boolean
  has_pickup: boolean
}

export interface NearbyStore extends Store {
  confirmed: boolean          // був серед переданих store_ids
  in_radius: boolean          // false — магазин з цінами поза радіусом, доданий, щоб було куди вести
  straight_km: number
  distance_km: number
  duration_min: number
  estimated: boolean          // Valhalla недоступний — оцінка за прямою, показуйте «≈»
  maps_urls: MapsUrls
}

export interface NearbyResponse {
  origin: { lat: number; lng: number }
  mode: Mode
  radius_km: number
  radius_expanded: boolean    // у радіусі було порожньо — радіус подвоєно
  routing: 'valhalla' | 'mixed' | 'estimated'
  recommended_store_id: string | null   // маршрут за замовчуванням будуйте сюди
  recommended_reason: 'confirmed_offer' | 'nearest_with_online_prices' | null
  unknown_store_ids: string[]
  count: number
  stores: NearbyStore[]       // уже відсортовані за duration_min
}

export interface RouteResponse {
  store_id: string
  source: StoreSource
  chain: string
  mode: Mode
  distance_km: number
  duration_min: number
  estimated: boolean          // true → geometry — пряма з двох точок
  geometry: { type: 'LineString'; coordinates: [number, number][] }  // [lng, lat] — готово для MapLibre
  maps_urls: MapsUrls
}

export interface Place {
  label: string               // «вулиця Хрещатик, 22, Київ»
  full: string
  lat: number
  lng: number
  source: 'nominatim' | 'photon' | 'coords'   // coords — адресу не знайдено, label = "50.44980, 30.52310"
}
export interface GeocodeResponse { results: Place[] }

export interface VoiceResult {
  text: string                // очищений запит → агенту
  raw_text: string            // що почули — показати користувачу
  mode: Mode | null           // null — не згадано, лишити перемикач як є
  radius_km: number | null    // null — дефолт /geo (пішки 2 км, авто 10 км)
  duration_s: number | null
  source: 'groq_whisper' | 'manual' | 'web_speech'
  cleanup: {
    model: string | null
    guard: 'ok' | 'rejected' | 'skipped' | 'llm_unavailable'  // rejected → text = raw_text
    new_words: string[]
    issues: Record<string, unknown[]>
    tokens: number
  }
}

// Помилки (три форми — розрізняйте за типом detail)
export interface GeoErrorDetail { code: string; message: string }                    // { detail: {...} }
export interface VoiceErrorDetail { code: string; message: string; fallback: boolean } // { detail: {...} }
export interface ValidationErrorItem { type: string; loc: (string | number)[]; msg: string; input?: unknown }
export type ApiErrorBody =
  | { detail: GeoErrorDetail | VoiceErrorDetail }   // наші модулі
  | { detail: ValidationErrorItem[] }               // 422 валідації FastAPI (масив)
  | { detail: string }                              // 401 без ключа, 503 без API_KEYS
```

## Endpoints

| Метод і шлях | Параметри | Відповідь |
|---|---|---|
| `GET /geo/stores/nearby` | `lat, lng, mode=walk\|car, radius_km?, store_ids?` (через кому; сирі ID з `/catalog` або `zakaz:`/`silpo:`) | `NearbyResponse` (мок 09, 10) |
| `GET /geo/route` | `lat, lng, store_id, mode` | `RouteResponse` (мок 11) |
| `GET /geo/geocode` | `q` (≥ 2 символи), `suggest?` (підказки під час набору, пауза ~300 мс), `lat?, lng?` (зміщення) | `GeocodeResponse` (мок 12) |
| `GET /geo/reverse` | `lat, lng` | `Place` |
| `GET /geo/stores` | — | `{count, stores: Store[]}` — усі 238 магазинів Києва для оглядової карти |
| `POST /voice/transcribe` | multipart `audio` (≤ 60 с, ≤ 1.5 MB) | `VoiceResult` (мок 15) |
| `POST /voice/parse-text` | JSON `{text, source: "manual"\|"web_speech"}` | `VoiceResult` (мок 14) |

Лише Київ: точка або адреса поза Києвом → 422 `outside_service_area` (мок 13).

## Коди помилок → текст для UI

`detail.message` англійською (правило команди), українське повідомлення показує фронт за `code`:

| HTTP | `code` | `fallback` | Текст для користувача |
|---|---|---|---|
| 422 | `outside_service_area` | — | Поки працюємо лише по Києву |
| 404 | `not_found_in_service_area` | — | Адресу не знайдено в Києві. Уточніть вулицю й номер будинку |
| 503 | `geocoder_unavailable` | — | Пошук адреси тимчасово недоступний. Спробуйте кнопку геолокації |
| 404 | `store_not_found` | — | Магазин не знайдено |
| 429 | `stt_rate_limited` | true | Розпізнавання перевантажене — спробуйте в браузері або введіть текстом |
| 502 | `stt_unavailable` | true | Розпізнавання голосу недоступне — спробуйте в браузері або введіть текстом |
| 504 | `stt_timeout` | true | Розпізнавання не відповіло вчасно |
| 503 | `stt_not_configured` | true | Розпізнавання голосу не налаштоване |
| 400 | `audio_unsupported` | true | Не вдалося прочитати запис |
| 422 | `no_speech` | false | Не почули мови. Спробуйте ще раз ближче до мікрофона |
| 400 | `audio_empty` | false | Порожній запис |
| 413 | `audio_too_large` / `audio_too_long` | false | Запис задовгий (максимум 60 с) |
| 429 | `rate_limited` | false | Забагато запитів. Спробуйте за хвилину |
| 401 | (рядок) | — | Помилка доступу до API (перевірте `VITE_API_KEY`) |
| 422 | (масив) | — | Перевірте введені дані |
