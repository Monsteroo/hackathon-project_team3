# HANDOFF: «Голос + Геолокація» для фронтенду

Ця папка — **тестовий стенд**, а не продуктовий UI: одна сторінка без стилів, щоб перевірити бекенд там,
де curl не допоможе (мікрофон, GPS). На Vercel не деплоїться (`tools/` у `.vercelignore`).

Запуск: бекенд `.venv/bin/uvicorn backend.app:app --port 8000`, потім тут `npm ci && npm run dev`
(→ http://localhost:5173, `/api` проксіюється на :8000). Мікрофон і GPS працюють лише на `localhost` або HTTPS.

## Що забрати у продуктовий фронт

| Файл | Що дає | Як використати |
|---|---|---|
| `src/api.js` | `api.transcribe(blob)`, `api.parseText(text, source)`, `api.geocode(q, {suggest, near})`, `api.reverse({lat,lng})`, `api.nearby({lat,lng,mode,radiusKm,storeIds})`, `api.route({lat,lng,storeId,mode})`; помилки → `ApiError {code, message, status, fallback}` | Скопіювати як є |
| `src/hooks/useVoiceRecorder.js` | Запис з мікрофона: `{start, stop, status, elapsed, error, supported, maxSeconds}`; автостоп на 60 с; webm/opus (Chrome) або mp4 (Safari); українські тексти помилок доступу | `useVoiceRecorder({ onStop: blob => api.transcribe(blob) })` |
| `src/hooks/useWebSpeech.js` | Запасне розпізнавання в браузері (`uk-UA`), якщо `/api/transcribe` повернув `fallback: true` | `useWebSpeech({ onResult: t => api.parseText(t, "web_speech") })` |
| `src/hooks/useGeolocation.js` | `locate()` → `Promise<{lat,lng,accuracy}>`, українські помилки | Після `locate()` → `api.reverse()` для підпису адреси |

Ланцюжок запасних варіантів для голосу: `/api/transcribe` → якщо `error.fallback` → Web Speech → ручне поле
(`/api/parse-text`, `source: "manual"`). Поле для ручного вводу має бути завжди.

## Контракти endpoints (реальні відповіді, скорочено)

Помилки завжди однакові: голос — `{"error": {"code", "message", "fallback"}}`, гео — `{"detail": {"code", "message"}}`.
`message` уже українською, його можна показувати користувачу як є.

### `POST /api/transcribe` (multipart `audio`, ≤ 60 с, < 4 MB)
```json
{
  "text": "мені треба молоко галичина 1 л, 20 яєць і каву якоб з монарх, бюджет 250 грн",
  "raw_text": "Ну мені треба молоко галичина літр, два десятки яєць і каву якоб з монарх, бюджет 250 гривень, далеко йти не хочу.",
  "mode": "walk",
  "radius_km": 1.0,
  "duration_s": 10.03,
  "source": "groq_whisper",
  "cleanup": {"model": "qwen/qwen3.8-27b", "guard": "ok", "new_words": [], "tokens": 510}
}
```
- `text` → агенту (Учасник 5); `raw_text` — для показу «що ми почули».
- `mode` (`walk`/`car`/`null`) і `radius_km` (`null` = не згадано) → у `/api/stores/nearby`. Якщо `null` — залишайте поточний перемикач.
- `cleanup.guard: "rejected"` означає, що LLM спробувала щось додати і ми віддали сирий текст. Можна показати «текст без обробки».
- Коди помилок: `stt_rate_limited` (429), `stt_unavailable`, `stt_timeout`, `stt_not_configured` (усі з `fallback: true`); `no_speech`, `audio_empty`, `audio_too_large` (`fallback: false` — попросіть повторити).

### `POST /api/parse-text` `{"text": "...", "source": "manual" | "web_speech"}`
Та сама відповідь, що й у `/api/transcribe`, але `duration_s: null`.

### `GET /api/geocode?q=Хрещатик 22` (`&suggest=true` — підказки під час набору, з паузою ~300 мс)
```json
{"results": [{"label": "вулиця Хрещатик, 22, Київ", "full": "22, вулиця Хрещатик, …, Київ, 01001, Україна",
              "lat": 50.4498465, "lng": 30.5230925, "source": "nominatim"}]}
```
Лише Київ: адреса в іншому місті → **422** `outside_service_area` «Поки працюємо лише по Києву»; не знайдено →
**404** `not_found_in_service_area`; сервіс недоступний → **503** `geocoder_unavailable`.

### `GET /api/reverse?lat=50.4498&lng=30.5231`
```json
{"label": "вулиця Хрещатик, 22, Київ", "full": "…", "lat": 50.4498, "lng": 30.5231, "source": "nominatim"}
```
Поза Києвом → 422 `outside_service_area`.

### `GET /api/stores/nearby?lat&lng&mode=walk|car&radius_km&store_ids=id1,id2`
```json
{
  "origin": {"lat": 50.4498, "lng": 30.5231}, "mode": "walk",
  "radius_km": 2.0, "radius_expanded": false, "routing": "valhalla",
  "recommended_id": "zakaz:48246401", "recommended_reason": "nearest_with_online_prices",
  "count": 19,
  "stores": [{
    "id": "osm:n1234", "alt_ids": [], "chain": "novus", "chain_name": "NOVUS",
    "name": "NOVUS", "city": "Київ", "address": "майдан Незалежності, 1",
    "lat": 50.4505, "lng": 30.5240, "place_id": "50.4505,30.5240",
    "has_online_prices": false, "online_catalog": false, "has_pickup": false,
    "confirmed": false, "in_radius": true,
    "straight_km": 0.12, "distance_km": 0.2, "duration_min": 2.5, "estimated": false,
    "maps_urls": {"walking": "https://www.google.com/maps/dir/?api=1&…&travelmode=walking",
                  "driving": "…travelmode=driving", "transit": "…travelmode=transit"}
  }]
}
```
- `stores` уже відсортовані за `duration_min`. Це всі магазини в радіусі **плюс** до 5 найближчих магазинів із цінами поза радіусом (`in_radius: false`), щоб завжди було куди прокласти маршрут.
- `recommended_id`: з `store_ids` (від агента) — найближчий серед них (`confirmed_offer`); без них — найближчий з `has_online_prices` (`nearest_with_online_prices`). Маршрут за замовчуванням будуйте до нього.
- Стани маркера: обраний / рекомендований / `has_online_prices || confirmed` (є ціни) / решта (без онлайн-цін).
- `place_id` однаковий для магазинів в одній будівлі (Megamarket + Ultramarket + За Раз), тож маркери варто групувати.
- `estimated: true` означає, що Valhalla недоступний і показано оцінку за прямою. Позначайте як «≈».
- Значення за замовчуванням: пішки 2 км, авто 10 км; якщо в радіусі порожньо, радіус подвоюється (`radius_expanded: true`). Поза Києвом → 422.

### `GET /api/route?lat&lng&store_id&mode`
```json
{"store_id": "zakaz:48246401", "mode": "walk", "distance_km": 6.92, "duration_min": 82.5, "estimated": false,
 "coordinates": [[50.44985, 30.52309], "…300 точок [lat, lng]…"],
 "maps_urls": {"walking": "…", "driving": "…", "transit": "…"}}
```
`coordinates` — готова лінія для Leaflet `Polyline` (`[lat, lng]`). При `estimated: true` це пряма з двох точок.
Громадський транспорт — лише кнопкою з `maps_urls.transit` (час рахує Google).

### `GET /api/stores`
Усі магазини Києва (238) без відстаней — для оглядової карти до вибору точки.
