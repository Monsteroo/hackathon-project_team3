# VoiceCart AI (КошикШІ) — Team 3

Голосовий AI-помічник: перетворює запит («все на сирники і кава, без цукру, до 400 грн») на найвигідніший продуктовий кошик у найближчих супермаркетах. Ідея, ринок і юніт-економіка описані в [PRODUCT_CONCEPT.md](PRODUCT_CONCEPT.md), ролі команди — в [README.md](README.md).

## Стек

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, httpx
- PostgreSQL 16 на Supabase (локально той самий Postgres 16)
- uv для залежностей, pytest, ruff

## Структура

```
backend/                 # один FastAPI-сервіс, поділений на модулі учасників
  app/
    main.py config.py db.py types.py migrate.py   # тонке спільне ядро
    catalog/             # Учасник 2 — магазини, товари, ціни, порівняння кошика
    agent/               # Учасник 5 — розбір запиту (LLM) і 3 варіанти кошика
  tests/                 # тести спільного ядра
docs/
  stores.md / stores.csv # 443 магазини Zakaz.ua + Сільпо з онлайн-каталогом: store_id, адреса, координати
mocks/                   # реальні приклади відповідей API для фронту й агента
```

Кожен учасник тримає свій код в окремому модулі `backend/app/<module>/`: роутер, схеми, моделі, сервіс, міграції й тести разом. Інші модулі використовують лише `service.py` і `schemas.py` чужого модуля. Деталі — у скілі `fastapi-backend`.

## Команди (з `backend/`)

```bash
uv sync                                  # залежності
cp .env.example .env                     # потім вписати DATABASE_URL
uv run python -m app.migrate             # застосувати SQL-міграції всіх модулів
uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
uv run pytest
uv run ruff check . && uv run ruff format .
uv run python -m app.catalog.etl --help  # ETL цін вручну (той самий джоб, що й уночі)
```

## Нічний ETL

- Планувальник APScheduler у процесі FastAPI щодня о **03:00 за Києвом** (`ETL_CRON`, `SCHEDULER_TIMEZONE`) запускає `app.catalog.jobs.nightly_etl`. Цей джоб завантажує магазини, товари й ціни з Zakaz.ua і Сільпо для міста `ETL_CITY`.
- Запуск відбувається, лише поки працює сервер. Кілька серверів одночасно не зашкодять: pg_advisory_lock пропускає зайві запуски, а upsert робить повтор безпечним.
- `GET /catalog/etl/status` показує розклад, наступний запуск, `prices_updated_at` (для UI) і журнал `etl_runs`.
- Схема БД — у [docs/db-schema.md](docs/db-schema.md).

## Контракти між учасниками

Це домовленості команди. Не змінюй їх мовчки: спершу онови `mocks/` і скажи користувачу, що саме змінилося.

- **Магазин:** `store_id` + `chain`. Для Zakaz.ua `store_id` — його `id` (`"482010105"`), для Сільпо — `branchId` (uuid). Значення `chain`: `silpo`, `novus`, `auchan`, `metro`, `ultramarket`, `ekomarket`, `megamarket`, `tavriav`.
- **Позиція кошика** (від агента до каталогу): `{category | gtin | query, need, unit: "g"|"ml"|"pcs", exclude: [tags]}`.
- **Канонічні категорії (демо):** `milk, kefir, curd, sour_cream, butter, cheese, eggs, flour, sugar, vanilla_sugar, buckwheat, rice, pasta, sunflower_oil, bread, coffee_ground, coffee_beans, tea, bananas, apples`.
- **Теги складу:** `sugar`, `palm_oil`, `lactose`, `private_label`.
- **Авторизація:** кожен запит до `/catalog/*`, `/agent/*` і `/health/db` має містити заголовок `X-API-Key` з одним із ключів `API_KEYS` (`backend/.env`). Без ключа — 401, без налаштованих ключів — 503. Відкриті лише `/health` і `/docs`.
- **API каталогу** (prefix `/catalog`, приклади відповідей у `mocks/`):
  - `GET /stores?city=Київ&chain=&with_prices=true` повертає доступні магазини з `store_id`, координатами й `offers_count`.
  - `GET /prices?q=молоко галичина 2,5&store_ids=a,b&category=&exclude=sugar,palm_oil&limit=20` повертає товари, назва яких містить усі слова запиту. Для кожного товару в масиві `prices` є ціни в запитаних магазинах: ціна, ₴/кг, акція, наявність. `store_ids` можна передати повторюваним параметром або через кому. Без `store_ids` пошук іде по всіх магазинах.
  - `GET /etl/status` — стан нічного ETL.
  - Заплановано `POST /basket/compare`.
  - Відстані каталог не рахує: агент бере їх у модуля геолокації і склеює з цінами за `store_id`.
- **API агента** (prefix `/agent`, приклади в `mocks/16_*`, `mocks/17_*`, деталі в `backend/app/agent/README.md`):
  - `POST /parse` `{text}` → розбір: позиції з `category` і обмеження (`budget_uah`, `exclude` тегами складу, `travel_mode`, `radius_km`, `preferred_chains`). Для екрана «Я зрозумів так».
  - `POST /basket` — або `{text, raw_text?, lat, lng, mode?, radius_km?}` (агент розбирає текст; поля — рівно з `VoiceResult`), або `{items: [{label?, category | gtin | query, need, unit, exclude}], budget_uah?, lat, lng, mode?, radius_km?}` — підтверджений список з екрана 2, без LLM. Відповідь: до 3 кошиків (`nearest`, `cheapest`, `smart_split`) з цінами каталогу, `missing` з причиною, `explanation`, а також `stores` — усі магазини в радіусі з сумою кошика, відсортовані від найдешевшого, з прапорцями `cheapest` (підсвітити) і `nearest`.
  - Магазини поруч агент бере з `geo.service.find_nearby` (маршрути Valhalla); якщо geo впав — оцінка за прямою з `catalog.list_stores`.
  - Ланцюжок фронту: голос → `/voice/transcribe` (набраний текст іде як є) → `/agent/parse` (екран 2) → GPS → `/agent/basket` → маршрут `/geo/route` до обраного магазину. `/voice/parse-text` прибрано: текст розбирає агент.

## Правила даних

- Гроші зберігаються в `numeric(10,2)` / `Decimal`, а в JSON віддаються числом у гривнях з двома знаками після коми. `unit_price` — ціна в ₴/кг, ₴/л або ₴/шт.
- GTIN нормалізований до 13 цифр без нулів на початку.
- Невідомий склад (типово для Сільпо) **не дорівнює чистому складу**. Якщо фільтр складу не вдалося перевірити, товар не проходить, і це видно в `missing_items` з причиною.
- Відсутні товари (`in_stock=false`, `stock<=0`) у кошик не потрапляють.

## Безпека

- Секрети (`DATABASE_URL`, ключі Supabase, `API_KEYS`) зберігаються лише в `backend/.env`, а він у `.gitignore`. У коді, моках і документації замість ключа пиши `<API_KEY>`.
- API захищене ключем (`app/auth.py`, заголовок `X-API-Key`). Новий модуль додавай рядком у `MODULES` в `app/main.py`: його роутер автоматично отримає перевірку ключа. `ENABLED_MODULES` вмикає лише частину модулів (каталог деплоїться окремо: `backend/render.yaml`).
- Фронт звертається тільки до FastAPI, не до Supabase напряму. На всіх таблицях увімкнено RLS (див. скіл `supabase-postgres`).

## Мова й стиль

- Тексти для користувача (UI, пояснення агента) — українською. Код, ідентифікатори, коміти, `detail` у помилках API — англійською.
- Коміти маленькі й осмислені. Робота йде в гілках `feature/<тема>` через PR у `main`.

## Хакатон

- Code freeze о **17:50**. До цього `main` має запускатися з чистого клону за командами вище.
- README має описати етапи розробки, ролі, архітектуру й trade-offs, вартість і те, як команда використовувала AI-інструменти.
- Не тягни в репо код, написаний до старту хакатону (11:00): це заборонено правилами.

## Скіли проєкту (`.claude/skills/`)

- `fastapi-backend` — структура модулів, ендпоінти, схеми, тести.
- `supabase-postgres` — підключення до Supabase, міграції, upsert, pg_trgm, RLS.
- `grocery-price-apis` — API Zakaz.ua та Сільпо: ендпоінти, поля, нормалізація, пастки в даних.
