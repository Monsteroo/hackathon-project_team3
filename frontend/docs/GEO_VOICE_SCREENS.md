# Geo + Voice: що готово для кожного екрана

Бекенд модулів `geo` і `voice` уже є в `main` (`backend/app/geo/`, `backend/app/voice/`). Фронт їх поки не
викликає. Цей файл — план підключення по екранах з [design/BRIEF.md](../design/BRIEF.md): що вже дає бекенд,
що є у фронті зараз і що треба зробити.

Джерела:

- [docs/VOICE_GEO.md](../../docs/VOICE_GEO.md) — архітектура, дані, компроміси.
- [tools/geo-voice-testbench/HANDOFF.md](../../tools/geo-voice-testbench/HANDOFF.md) — TS-типи, endpoints, коди помилок.
- `tools/geo-voice-testbench/src/` — робочий JS-код (клієнт API і хуки), який переносимо в TS.
- `mocks/09_*` … `mocks/15_*` — реальні відповіді бекенду.

**Обмеження демо: лише Київ.** Точка або адреса поза Києвом → 422 `outside_service_area`.

---

## Крок 0. Спільна база (зробити першою)

Без цього кроку жоден екран не дістанеться до бекенду.

| Файл | Що зробити | Звідки взяти |
|---|---|---|
| `vite.config.ts` | Додати проксі `/geo`, `/voice`, `/catalog` → `http://localhost:8000`. Зараз проксюється лише `/api`, якого бекенд не має | HANDOFF, розділ «Що зробити у фронті», п. 1 |
| `.env.local` (не комітиться) | `VITE_API_KEY=<API_KEY>` — значення з `API_KEYS` у `backend/.env`. Без ключа бекенд віддає 401 | HANDOFF, п. 2 |
| `src/vite-env.d.ts` | Оголосити `VITE_API_KEY` в `ImportMetaEnv` | — |
| `src/lib/api/types.ts` (новий) | `Mode`, `Store`, `NearbyStore`, `NearbyResponse`, `RouteResponse`, `Place`, `GeocodeResponse`, `VoiceResult`, типи помилок | HANDOFF, розділ «TypeScript-типи» (готовий код) |
| `src/lib/api/client.ts` (новий) | `request<T>()` із заголовком `X-API-Key`, клас `ApiError {code, message, status, fallback}`. Методи: `transcribe`, `geocode`, `reverse`, `nearby`, `route` | `tools/geo-voice-testbench/src/api.js` |
| `src/lib/api/errors.ts` (новий) | Мапа `code → український текст` для UI. `detail.message` від бекенду англійською, його не показуємо | HANDOFF, таблиця «Коди помилок → текст для UI» |

Ключ у бандлі не секретний. Від зловживань Groq захищає ліміт 10 запитів/хв з IP на `/voice/*`.

---

## Екран 0 — Онбординг (`/welcome`)

**Файли:** `src/pages/OnboardingPage.tsx`, новий `src/features/geo/useGeolocation.ts`.

**Зараз:** заглушка `ScreenStub`.

**Що дає бекенд:**

- `GET /geo/reverse?lat&lng` → `Place.label`, наприклад «вулиця Хрещатик, 22, Київ». Підпис під кнопкою геолокації.
- Точка поза Києвом → 422 `outside_service_area`. Показати «Поки працюємо лише по Києву».

**Що зробити:**

1. Перенести `tools/geo-voice-testbench/src/hooks/useGeolocation.js` → `src/features/geo/useGeolocation.ts`.
   Хук повертає `{status, error, locate}`, де `locate()` — `Promise<{lat, lng, accuracy}>`. Українські помилки вже є.
2. Кнопка «Дозволити геолокацію» → `locate()` → `api.reverse()` → зберегти координати й підпис адреси
   (див. «Спільний стан» нижче).
3. Кнопка «Дозволити мікрофон» → `navigator.mediaDevices.getUserMedia({audio: true})` і одразу зупинити треки.
   Мета — лише отримати дозвіл.
4. Відмова в геолокації → поле адреси з `api.geocode(q, {suggest: true})`. Пауза ~300 мс між запитами,
   мінімум 2 символи.

**Мок:** `12_geo_geocode.json`, `13_geo_error_outside_service_area.json`.

---

## Екран 1 — Запит (`/`)

**Файли:** `src/pages/RequestPage.tsx`, `src/features/voice/useSpeechRecognition.ts`, новий
`src/features/voice/useVoiceRecorder.ts`, новий `src/features/voice/useVoiceInput.ts`,
`src/components/CitySelect/CitySelect.tsx`.

**Зараз:**

- Голос іде лише через Web Speech у браузері (`useSpeechRecognition`). Бекенд не викликається.
- `VoiceButton` і `VoiceStatus` вже мають стани `idle | listening | processing | error | blocked | unsupported`
  і індикатор гучності `levelRef`.
- Сабміт робить `navigate('/confirm', { state: { query, cityId } })`.
- `CitySelect` бере сирий `navigator.geolocation` і шукає найближче місто з `CITIES` (5 міст).

**Що дає бекенд:**

- `POST /voice/transcribe` (multipart `audio`, ≤ 60 с, ≤ 1.5 MB) → `VoiceResult`:
  `text` (очищений, для агента), `raw_text` (що почули), `mode` (`walk | car | null`),
  `radius_km` (`number | null`). Whisper large-v3 дає кращу українську, ніж Web Speech, і працює у Firefox.
- Набраний текст (ручний ввід, Web Speech) на бекенд окремо не йде: `localVoiceResult(text, source)` на фронті, розбір — агентом (`/agent/parse`). `/voice/parse-text` прибрано.
  Для ручного вводу й результату Web Speech.
- Помилка з `fallback: true` означає: бекенд не впорався, треба перейти на Web Speech.

**Ланцюжок голосу:**

1. Запис через `MediaRecorder` → `api.transcribe(blob)`.
2. Якщо `ApiError.fallback === true` → запасний шлях: наявний `useSpeechRecognition`.
3. Поле ручного вводу доступне завжди.

**Що зробити:**

1. Перенести `tools/geo-voice-testbench/src/hooks/useVoiceRecorder.js` → `src/features/voice/useVoiceRecorder.ts`.
   Хук повертає `{supported, status, elapsed, error, start, stop, maxSeconds}`, автостоп на 60 с,
   webm/opus (Chrome) або mp4 (Safari). Підказки для TS є в HANDOFF.
2. У хуку зі стенду немає індикатора гучності. Перенести `startMeter`/`stopMeter` з `useSpeechRecognition.ts`,
   щоб `VoiceButton` і далі пульсував.
3. `useVoiceInput.ts` — обгортка, яка повертає ту саму форму, що й `useSpeechRecognition`
   (`state`, `error`, `toggle`, `cancel`, `levelRef`), і всередині вирішує: бекенд або Web Speech.
   Тоді `RequestPage` змінюється мінімально. Стан `processing` = чекаємо відповідь `/voice/transcribe`.
4. `useWebSpeech.js` зі стенду переносити не треба. Його роль уже виконує `useSpeechRecognition.ts`.
5. Сабміт: якщо текст набрано вручну, зібрати `localVoiceResult(text, 'manual')`. Далі передати на `/confirm`
   увесь `VoiceResult`, а не лише рядок:
   `navigate('/confirm', { state: { voice: VoiceResult, cityId } })`.
6. Показати `raw_text` у полі, а `text` віддати далі. Альтернатива: показати `text` одразу. Вирішити з дизайном.
7. Помилки `/voice/*` → текст із `errors.ts` у `VoiceStatus`.

**Розбіжність із містами:** `CITIES` має 5 міст, бекенд обслуговує лише Київ. Варіанти: прибрати інші міста
з `CITIES` на час демо або показувати «Поки працюємо лише по Києву» при виборі іншого міста.

**Мок:** `14_voice_parse_text.json`, `15_voice_transcribe.json`.

---

## Екран 2 — «Я зрозумів так» (`/confirm`)

**Файли:** `src/pages/ConfirmPage.tsx`.

**Зараз:** заглушка, показує `state.query`.

**Що дає бекенд:**

- `VoiceResult.mode` → перемикач «пішки / авто». `null` означає «не згадано»: лишити значення за замовчуванням.
- `VoiceResult.radius_km` → обмеження «відстань». `null` → дефолт `/geo`: пішки 2 км, авто 10 км.
  Приклад: «далеко йти не хочу» → `mode: "walk"`, `radius_km: 1`.
- Розбір тексту на продукти, кількості, бюджет і алергени робить агент (Учасник 5). Geo + Voice цього не дає.

**Що зробити:**

1. Читати `state.voice` (`VoiceResult`) замість `state.query`.
2. Обмеження «відстань»: режим + радіус, попередньо заповнені з `mode` і `radius_km`.
3. Передати `mode` і `radius_km` далі на `/results`.

---

## Екран 3 — Карта + 3 варіанти (`/results`)

**Файли:** `src/pages/ResultsPage.tsx`, `src/components/StoreMap/StoreMap.tsx`, новий `src/features/geo/useNearbyStores.ts`.

**Зараз:** `StoreMap` (MapLibre, тайли OpenFreeMap) показує статичний центр Києва без маркерів.

**Що дає бекенд:**

- `GET /geo/stores/nearby?lat&lng&mode&radius_km&store_ids` → `NearbyResponse`:
  - `stores` вже відсортовані за `duration_min`. Кожен має `distance_km`, `duration_min`, `in_radius`,
    `estimated` (показувати «≈») і `maps_urls`.
  - `recommended_store_id` — куди будувати маршрут за замовчуванням.
  - `radius_expanded: true` — у радіусі було порожньо, радіус подвоєно. Варто сказати про це користувачу.
  - `place_id` однаковий для магазинів в одній будівлі. Групувати маркери за ним.
  - `store_ids` — ID магазинів, де агент знайшов кошик (сирі ID з `/catalog`). Без них повертаються всі
    магазини поруч.
- `GET /geo/route?lat&lng&store_id&mode` → `RouteResponse.geometry` — GeoJSON `LineString` у форматі
  `[lng, lat]`, готовий для MapLibre. `estimated: true` → пряма з двох точок.
- `GET /geo/stores` — усі 238 магазинів Києва для оглядової карти.

**Що зробити:**

1. `useNearbyStores({lat, lng, mode, radiusKm, storeIds})` → `api.nearby()`, стани завантаження й помилки.
2. `StoreMap`: нові props `origin`, `stores`, `route?`, `selectedId?`, `onSelect?`. Маркери магазинів
   (групувати за `place_id`) і маркер користувача. Лінія маршруту — `source` + `layer` типу `line`.
3. Клік на магазин або картку → `api.route()` → оновити лінію.
4. Картка «Найближчий» = перший у `stores` (або `recommended_store_id`). Час і відстань — через `src/lib/format.ts`.
5. Порожній результат → стан «Немає магазинів поруч» з BRIEF.

**Залежність:** ціни й 3 варіанти кошика (Найвигідніший, Smart Split) дає агент і каталог, не geo.
Поки агента немає, екран можна будувати на `nearby` без `store_ids` і моках каталогу.

**Мок:** `09_geo_stores_nearby_walk.json`, `10_geo_stores_nearby_confirmed.json`, `11_geo_route_walk.json`.

---

## Екран 4 — Деталі кошика (`/basket/:optionId`)

Geo + Voice тут не потрібні. Дані — від агента й каталогу.

---

## Екран 5 — У магазині (`/store/:optionId`)

**Файли:** `src/pages/InStorePage.tsx`.

**Що дає бекенд:** `maps_urls` у `NearbyStore` і `RouteResponse`: `{walking, driving, transit}` — готові
посилання Google Maps. Громадський транспорт доступний лише посиланням, час на ньому рахує Google.

**Що зробити:** кнопка «Маршрут» → `window.open(maps_urls.walking | driving)` відповідно до `mode`.
Можна дати вибір з трьох варіантів.

---

## Екран 6 — Paywall

Geo + Voice не потрібні.

---

## Спільний стан між екранами

Координати користувача потрібні на екранах 0, 1, 3 і 5. Запропонований варіант:

- `src/lib/useLocation.ts` за зразком `src/lib/useCity.ts` (`useSyncExternalStore` + `localStorage`).
- Зберігає `{lat, lng, label, source: 'gps' | 'address'}`.

`VoiceResult` (`text`, `mode`, `radius_km`) передається через `navigate(..., { state })`, як зараз `query`.

---

## Стани з BRIEF → що відповідає бекенд

| Стан | Звідки сигнал |
|---|---|
| Голос не розпізнано / тиша | 422 `no_speech`, 400 `audio_empty` |
| Розпізнавання недоступне | `fallback: true` (`stt_rate_limited`, `stt_unavailable`, `stt_timeout`, `stt_not_configured`, `audio_unsupported`) → Web Speech |
| Браузер не підтримує голос | `useVoiceRecorder.supported === false` і немає Web Speech → лише поле |
| Мікрофон заборонено | `NotAllowedError` з `useVoiceRecorder` (текст уже є в хуку) |
| Геолокацію заборонено | `useGeolocation` → поле адреси через `/geo/geocode` |
| Поза Києвом | 422 `outside_service_area` |
| Адресу не знайдено | 404 `not_found_in_service_area` |
| Немає магазинів поруч | `NearbyResponse.count === 0` |
| Немає мережі | `ApiError.code === 'network'` |
| Забагато запитів | 429 `rate_limited` |

---

## Порядок реалізації

1. Крок 0: проксі, ключ, `types.ts`, `client.ts`, `errors.ts`.
2. Екран 1: `useVoiceRecorder.ts` → `useVoiceInput.ts` → `RequestPage.tsx`.
3. `useGeolocation.ts` + `useLocation.ts` → Екран 0 і `CitySelect`.
4. Екран 2: `mode` / `radius_km`.
5. Екран 3: `useNearbyStores.ts` → `StoreMap.tsx` → `ResultsPage.tsx`.
6. Екран 5: кнопка «Маршрут».

## Як перевіряти

- Бекенд: з `backend/` запустити `uv run uvicorn app.main:app --reload`. У `backend/.env` мають бути
  `API_KEYS` і `GROQ_API_KEY`.
- Фронт: `npm run dev` → http://localhost:5173. Мікрофон і GPS працюють лише на `localhost` або HTTPS.
- Перед комітом: `npm run typecheck && npm run lint && npm test && npm run build`.
