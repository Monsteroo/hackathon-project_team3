# Модуль agent (Учасник 5)

Текст запиту («все на сирники і кава, без цукру, до 400 грн») → до трьох варіантів кошика з цінами каталогу.

```text
фронт: /voice/transcribe ─► VoiceResult {text, raw_text, mode, radius_km} ─┐
       GPS ─► {lat, lng} ──────────────────────────────────────────────────┴─► POST /agent/basket
агент: text ─► Parse (LLM) ─► geo.find_nearby ─► catalog.search_prices ─► Optimize ─► 3 кошики + пояснення
```

| Файл | Що робить |
|---|---|
| `router.py` | `POST /agent/parse`, `POST /agent/basket` (з `X-API-Key`) |
| `schemas.py` | контракт з фронтом: `ParsedRequest`, `BasketOut` |
| `llm.py` | Claude (Anthropic SDK) або Gemini/Groq/Grok (OpenAI-сумісний API), системний промпт |
| `parser.py` | LLM + запасний парсер на правилах (якщо LLM недоступна: 429, 503, таймаут, немає ключа) |
| `service.py` | пайплайн: магазини в радіусі, пошук цін, пояснення |
| `optimizer.py` | кількість пачок, «менша пачка», nearest / cheapest / smart_split — чистий Python без БД |
| `evals/` | 33 запити для оцінки кроку Parse + скрипт прогону |

## API

- `POST /agent/parse` `{"text": "..."}` → `ParsedRequest`: позиції (`name`, `category`, `quantity`, `unit`, `brand`, `optional`) і обмеження (`budget_uah`, `exclude: [sugar|palm_oil|lactose]`, `travel_mode`, `radius_km`, `preferred_chains`). До БД не звертається. Для екрана «Я зрозумів так».
- `POST /agent/basket` — два режими:
  - **текст** `{"text", "lat", "lng", "raw_text"?, "mode"?, "radius_km"?, "city"?}` (поля з `VoiceResult` передавайте як є): агент розбирає текст через Claude;
  - **список з екрана 2** `{"items": [{label?, category? | gtin? | query?, need, unit, exclude}], "budget_uah"?, "lat", "lng", "mode"?, "radius_km"?}`: уже підтверджений і відредагований людиною список, **без виклику LLM** (`parser: "items"`). `exclude` — на рівні позиції (`sugar`, `palm_oil`, `lactose`, `private_label`); `gtin` — точний товар, вибраний з каталогу.
  - Відповідь однакова: `parsed`, `parser` (`llm` | `rules` | `items`), `baskets` (до 3: `nearest`, `cheapest`, `smart_split`), `explanation`, `warnings`.
  - `stores` — **усі магазини в радіусі**, де знайшлася хоч одна позиція: `store`, `lines`, `total`, `found`, `missing`, `within_budget`. Відсортовано: повніший кошик → дешевший → ближчий. `cheapest: true` — перший у списку (підсвітити), `nearest: true` — найменший час у дорозі. Розглядається до 20 найближчих магазинів кожної мережі (`AGENT_STORES_PER_CHAIN`). Без `text` і без `items` — 422; БД недоступна — 503.

Приклади відповідей: [`mocks/16_agent_parse.json`](../../../mocks/16_agent_parse.json), [`mocks/17_agent_basket.json`](../../../mocks/17_agent_basket.json).

## Налаштування (`backend/.env`)

| Змінна | За замовчуванням | |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` або `openai_compat` |
| `ANTHROPIC_API_KEY` | — | console.anthropic.com → API Keys |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | `claude-haiku-5-5` дешевша, `claude-opus-5-5` сильніша |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Gemini | для `openai_compat` |
| `AGENT_RADIUS_WALK_KM`, `AGENT_RADIUS_CAR_KM` | 1.5 / 5 | радіус лише для запасного режиму без geo (у geo свій: 2 / 10 км) |

Без ключа агент працює на парсері на правилах: API не падає, але рецепти не розкладаються (`parser: "rules"` і попередження у відповіді).

## Рішення й обмеження

- **LLM лише розбирає мову.** Ціни, кількість пачок, бюджет і вибір магазинів рахує Python: передбачувано, тестовано, без вигаданих цифр. Пояснення — шаблон з порахованих чисел, без другого виклику LLM.
- **Магазини поруч — з модуля geo** (Учасник 1): маршрути Valhalla, радіус команди (пішки 2 км, авто 10 км), до 2 найближчих магазинів кожної мережі з цінами. Якщо в радіусі порожньо — найближчі з цінами до 30 км з попередженням. Якщо geo впав — запасна оцінка за прямою × 1.3 з `catalog.list_stores`.
- **`mode` і `radius_km` з голосу головніші** за те, що агент витягнув з тексту: модуль voice уже їх розібрав.
- **Без категорії — лише товари, що так і називаються.** Пошук без категорії приймає товар, лише якщо його назва починається зі слова запиту: «зелень» не знайде «Сир … з зеленою цибулею», «картопля» — чіпси. Краще чесне «немає поруч», ніж чужий товар у кошику.
- **Кілька ID одного магазину** (`alt_store_ids` з geo): ціни шукаються за всіма й приписуються основному.
- **Склад фільтрує каталог** (`exclude`): невідомий склад не проходить. У `missing` видно причину: `not_found` або `filtered_by_composition`.
- **Вартість розбору** на Sonnet 5.5: ~3.5 тис. вхідних і ~350 вихідних токенів ≈ $0.01 і 2–4 с на запит.

## Тести й евали (з `backend/`)

```bash
uv run pytest app/agent                                   # без БД, мережі й LLM: каталог із mocks/
uv run python -m app.agent.evals.run_eval --rules         # базова лінія, безкоштовно
uv run python -m app.agent.evals.run_eval                 # модель з .env (платно: ~$0.35 за прогін на Sonnet)
uv run python -m app.agent.evals.run_eval --provider anthropic --model claude-haiku-5-5
```
