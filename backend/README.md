# VoiceCart AI — backend

Один FastAPI-сервіс, поділений на модулі учасників. Зараз у ньому є модуль `catalog` (Учасник 2): магазини, товари й ціни з Zakaz.ua і Сільпо, нічний ETL і пошук цін. Дані лежать у PostgreSQL: локальному або на Supabase.

## Що потрібно

- Python **3.12+** і [uv](https://docs.astral.sh/uv/) (`uv --version`)
- PostgreSQL 16: локально (Docker або Homebrew) або проєкт на Supabase

## Швидкий старт (локальна БД)

Усі команди виконуються з папки `backend/`.

**1. Залежності**

```bash
uv sync
```

**2. База даних.** Обери один варіант.

Docker (найпростіше, однаково в усіх):

```bash
docker run -d --name voicecart-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=voicecart -p 5432:5432 postgres:16
```

Homebrew (macOS):

```bash
brew install postgresql@16 && brew services start postgresql@16
```

```bash
createdb voicecart
```

Якщо Postgres із Homebrew не стартує з помилкою `postmaster became multithreaded during startup`, перед запуском виконай `export LC_ALL=en_US.UTF-8`.

**3. Налаштування**

```bash
cp .env.example .env
```

У `.env` за замовчуванням стоїть `postgresql+asyncpg://postgres:postgres@localhost:5432/voicecart`. Для Docker-варіанта нічого міняти не треба. Для Homebrew ім'я користувача зазвичай збігається з логіном на Mac: `postgresql+asyncpg://<твій_логін>@localhost:5432/voicecart`. Сам `.env` у git не потрапляє.

**4. Схема БД**

```bash
uv run python -m app.migrate
```

Команда застосовує нові файли з `app/<module>/migrations/*.sql`. Повторний запуск безпечний: друга спроба виведе `nothing to apply`.

**5. Дані.** Швидкий прогін на 2 магазини Zakaz, 2 філії Сільпо і 2 категорії займає близько 30 секунд:

```bash
uv run python -m app.catalog.etl --zakaz-store-limit 2 --silpo-branch-limit 2 --categories milk,curd
```

Повний прогін по Києву (27 магазинів Zakaz.ua, 160 філій Сільпо, 20 категорій) займає близько 13–15 хвилин, ~6000 запитів і ~60 МБ у БД:

```bash
uv run python -m app.catalog.etl
```

Усі параметри показує `uv run python -m app.catalog.etl --help`.

**6. Ключ API.** Згенеруй ключ і впиши його в `.env` як `API_KEYS=<ключ>`. Кілька ключів записуються через кому, окремо на фронт, агента й Postman.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**7. API**

```bash
uv run uvicorn app.main:app --reload
```

Документація й «спробувати запит» доступні на http://localhost:8000/docs. Корінь `/` перенаправляє туди. У Swagger натисни **Authorize** і встав ключ. Після зміни `.env` перезапусти сервер: `--reload` реагує лише на зміни в `.py`.

## Supabase

1. В Supabase відкрий **Project Settings → Database → Connect → Session pooler**. Direct-підключення на безкоштовному плані працює лише через IPv6 і з багатьох мереж не підключиться.
2. Впиши в `backend/.env`:

   ```
   DATABASE_URL=postgresql+asyncpg://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres
   DB_SSL=true
   ```

   - user — саме `postgres.<project-ref>`, а не `postgres`;
   - порт — `5432` (session mode), не `6543`;
   - пароль зі спецсимволами треба закодувати: `python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" 'пароль'`.
3. Виконай `uv run python -m app.migrate` і `uv run python -m app.catalog.etl`, так само як для локальної БД.

База на Supabase одна на всю команду, тому:
- **Не редагуй застосовані міграції**: додай нову з наступним номером.
- **Не запускай ETL паралельно з кимось.** Захист є: другий запуск отримає `skipped`, бо перший тримає `pg_advisory_lock`. Але чужий процес не вбивай, дочекайся кінця.
- Змінні оточення мають пріоритет над `.env`. Щоб на хвилинку попрацювати з локальною базою, коли в `.env` прописано Supabase: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voicecart DB_SSL=false uv run …`.

## Деплой (Render, безкоштовно)

Усе для деплою лежить у `backend/`: образ (`Dockerfile`, `.dockerignore`) і сервіс Render ([`render.yaml`](render.yaml)). Деплоїться лише модуль `catalog` (`ENABLED_MODULES=catalog` у `render.yaml`): на сервері будуть `/catalog/*` і `/health`, а `geo` і `voice` не імпортуються й не потребують своїх секретів. Безкоштовний план Render дає 0,1 CPU, 512 МБ RAM і 750 годин на місяць, яких вистачає на один сервіс 24/7. Без запитів сервіс засинає через 15 хвилин.

1. Злий зміни в `main`: Render деплоїть цю гілку.
2. Render → **New → Blueprint** → вибери цей репо → у полі **Blueprint Path** вкажи `backend/render.yaml`. Без цього Render шукатиме файл у корені й не знайде. Якщо репо належить іншому акаунту, його власник має дозволити GitHub-застосунок Render.
3. Render попросить значення змінних із `sync: false`:
   - `DATABASE_URL` — рядок Session pooler із Supabase, той самий, що в `backend/.env`;
   - `API_KEYS` — **новий** продакшен-ключ;
   - `CORS_ORIGINS` — адреса фронта, напр. `["https://<frontend>.onrender.com"]`.

   Решта (`DB_SSL`, `SCHEDULER_*`, `ETL_CRON`, `PORT`) уже задана в `render.yaml`.
4. Після деплою відкрий `https://<сервіс>.onrender.com/docs` → **Authorize** → ключ → `GET /catalog/stores`. Міграції застосовуються самі під час кожного старту.
5. **Не дай сервісу заснути**, інакше нічний ETL о 03:00 не стартує або обірветься посередині. На cron-job.org (безкоштовно) додай задачу `GET https://<сервіс>.onrender.com/health` кожні 10 хвилин. Вона використовує майже всі 750 безкоштовних годин, тож інших free-сервісів у цьому воркспейсі Render не має бути.
6. **Перевір, чи магазини пускають запити з Render.** ETL ми запускали лише з української IP, а з дата-центру у Франкфурті Zakaz.ua чи Сільпо можуть відповідати 403 або 429. Тимчасово постав у Render `ETL_CRON` на найближчі хвилини (час за Києвом, напр. `40 15 * * *`), дочекайся запуску й подивись `GET /catalog/etl/status`. Потім поверни `0 3 * * *`.
7. **План Б**, якщо магазини блокують Render: постав `SCHEDULER_ENABLED=false`, а ETL запускай із будь-якої машини, де `backend/.env` дивиться на Supabase (`uv run python -m app.catalog.etl`). API на Render віддаватиме ці дані.

Перевірити образ локально (з `backend/`):

```bash
docker build -t voicecart-backend .
```

```bash
docker run --rm -p 8000:10000 -e PORT=10000 -e ENABLED_MODULES=catalog -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/voicecart -e DB_SSL=false -e API_KEYS=local-test-key voicecart-backend
```

`.env` в образ не потрапляє (див. `.dockerignore`), тому всі налаштування передаються змінними оточення.

## Нічний ETL (03:00)

- Планувальник APScheduler живе всередині FastAPI і щодня о **03:00 за Києвом** запускає той самий ETL, що й команда `python -m app.catalog.etl`.
- **Запуск відбувається, лише поки працює сервер.** Якщо о 03:00 процес спав, джоб дожене пропущений запуск протягом години.
- Якщо працює кілька серверів (у кількох учасників або uvicorn `--workers N`), ETL однаково виконається один раз завдяки advisory lock.
- Налаштування: `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE`, `ETL_CRON` (crontab), `ETL_CITY`.
- Стан видно в `GET /catalog/etl/status`: наступний запуск, `prices_updated_at` для UI й журнал запусків.
- **Ліміт Zakaz.ua.** При частих запитах Zakaz.ua відповідає 429. ETL тоді ставить на паузу всі запити й наприкінці повторює магазини з помилками, тому прогін іноді триває довше.

## Авторизація

Кожен запит до `/catalog/*` і `/health/db` має містити заголовок `X-API-Key`. Відкриті без ключа лише `/health`, `/docs` і `/openapi.json`.

| Ситуація | Відповідь |
|---|---|
| ключа немає або він неправильний | `401 invalid or missing API key` |
| на сервері не задано `API_KEYS` | `503 API keys are not configured` (API не відкривається всім через помилку конфігурації) |

- Ключі задаються в `API_KEYS` через кому. Щоб відкликати ключ, прибери його зі списку й перезапусти сервер.
- Ключ, вшитий у браузерний фронт, видно будь-кому, хто відкриє DevTools. Для хакатону цього достатньо. У продукті фронт мав би ходити через свій бекенд або мати авторизацію користувачів.
- Код інших модулів, що викликає `app.catalog.service` напряму в Python (наприклад, агент), ключ не передає.

## API

| Запит | Що робить |
|---|---|
| `GET /catalog/stores?city=Київ&chain=silpo&with_prices=true` | Доступні магазини: `store_id`, мережа, адреса, координати, `offers_count` |
| `GET /catalog/prices?q=молоко галичина 2,5&store_ids=482010105,<branchId>&limit=20` | Товари, назва яких містить усі слова `q`, і їхні ціни в цих магазинах: ціна, ₴/кг, акція, наявність |
| `GET /catalog/etl/status` | Розклад і журнал нічного ETL |
| `POST /agent/parse` | Розбір тексту запиту агентом (LLM): позиції й обмеження |
| `POST /agent/basket` | Текст + координати → до 3 кошиків з цінами каталогу. Деталі: [`app/agent/README.md`](app/agent/README.md) |
| `GET /health` (без ключа), `GET /health/db` | Перевірка сервісу й підключення до БД |

Параметри `/catalog/prices`:

| Параметр | Обов'язковий | Що робить |
|---|---|---|
| `q` | так | назва товару, від 2 символів |
| `store_ids` | ні | через кому або повторюваним параметром; без нього пошук по всіх магазинах |
| `category` | ні | `milk`, `curd`, `eggs`, `coffee_ground` тощо |
| `exclude` | ні | `sugar`, `palm_oil`, `lactose`; товари з невідомим складом теж відсіюються |
| `in_stock_only` | ні | за замовчуванням `true` |
| `limit` | ні | від 1 до 100 |

Приклади запиту й відповіді, разом із curl для Postman, лежать у [`../mocks/`](../mocks/). Наприклад:

```bash
curl --location 'http://localhost:8000/catalog/prices?q=%D0%BC%D0%BE%D0%BB%D0%BE%D0%BA%D0%BE%20%D0%B3%D0%B0%D0%BB%D0%B8%D1%87%D0%B8%D0%BD%D0%B0&store_ids=482010105,48215610&limit=3' --header 'X-API-Key: <API_KEY>'
```

У Postman ключ зручно один раз задати в колекції: **Authorization → API Key**, Key `X-API-Key`, Value `{{apiKey}}`, Add to `Header`.

## Тести й лінтер

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format .
```

Тести не потребують ні БД, ні мережі: парсери й нормалізація перевіряються на скорочених реальних відповідях API.

## Змінні оточення

Повний список із коментарями — у [`.env.example`](.env.example).

| Змінна | За замовчуванням | Призначення |
|---|---|---|
| `DATABASE_URL` | локальний `voicecart` | рядок підключення SQLAlchemy (`postgresql+asyncpg://…`) |
| `DB_SSL` | `false` | `true` для Supabase |
| `DB_POOL_SIZE` | `5` | розмір пулу; ліміт з'єднань у Supabase невеликий |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | звідки фронт може звертатися до API |
| `API_KEYS` | порожньо (API закрите, 503) | ключі для `X-API-Key`, через кому |
| `SCHEDULER_ENABLED` | `true` | вмикає нічний ETL у процесі сервера |
| `SCHEDULER_TIMEZONE` | `Europe/Kyiv` | часовий пояс розкладу |
| `ETL_CRON` | `0 3 * * *` | розклад ETL у форматі crontab |
| `ETL_CITY` | `Київ` | місто, магазини якого завантажуються |
| `ETL_CONCURRENCY` | `5` | паралельні запити до API магазинів |
| `ETL_ZAKAZ_STORE_LIMIT`, `ETL_SILPO_BRANCH_LIMIT` | без обмежень | для швидких тестових прогонів |

## Типові проблеми

| Симптом | Що робити |
|---|---|
| `password authentication failed` / `Tenant or user not found` (Supabase) | user має бути `postgres.<project-ref>` |
| `nodename nor servname provided` / `Network is unreachable` | використовуй host Session pooler, а не `db.<ref>.supabase.co` |
| `prepared statement "__asyncpg_stmt_…" already exists` | порт `5432` (session pooler), не `6543` |
| `relation "products" does not exist` | не застосовано міграції: `uv run python -m app.migrate`; перевір, на яку БД дивиться `DATABASE_URL` |
| `401 invalid or missing API key` | додай заголовок `X-API-Key` з ключем з `API_KEYS` |
| `503 API keys are not configured` | задай `API_KEYS` у `backend/.env` і перезапусти сервер |
| `/catalog/stores` повертає порожній список | у БД ще немає цін, запусти ETL (`with_prices=false` покаже всі магазини) |
| Postgres із Homebrew не стартує (`postmaster became multithreaded`) | `export LC_ALL=en_US.UTF-8` |

## Структура

```
backend/
  app/
    main.py config.py db.py types.py migrate.py scheduler.py auth.py   # спільне ядро
    catalog/                  # Учасник 2: магазини, товари, ціни
      router.py schemas.py service.py models.py jobs.py
      etl/                    # нічний ETL: zakaz.py, silpo.py, normalize.py, runner.py
      migrations/             # 001_init.sql …
      tests/
    agent/                    # Учасник 5: розбір запиту (LLM), кошики, евали
  tests/                      # тести спільного ядра
```

Як додати свій модуль, описано в [CLAUDE.md](../CLAUDE.md) і в скілі `.claude/skills/fastapi-backend`. Схема БД — у [docs/db-schema.md](../docs/db-schema.md).
