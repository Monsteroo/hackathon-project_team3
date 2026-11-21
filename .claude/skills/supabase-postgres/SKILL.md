---
name: supabase-postgres
description: Як бекенд VoiceCart працює з PostgreSQL на Supabase — рядок підключення й пулер, налаштування asyncpg і SSL, SQL-міграції модулів, конвенції схеми, upsert і масове завантаження, індекси, пошук pg_trgm, RLS і ключі. Використовуй щоразу, коли пишеш SQL, змінюєш схему, додаєш міграцію, налаштовуєш DATABASE_URL, завантажуєш дані в БД або розбираєш помилки підключення чи prepared statements — навіть якщо Supabase прямо не названо ("postgres", "база", "таблиця", "міграція", "не підключається до БД").
---

# PostgreSQL на Supabase

## Підключення

Supabase показує адреси в **Project Settings → Database → Connect**. Хост і користувача копіюй звідти, не вгадуй.

| Варіант | Адреса | Коли |
|---|---|---|
| Direct | `db.<ref>.supabase.co:5432` | На безкоштовному плані працює лише через IPv6, тож з багатьох мереж не підключиться |
| **Session pooler** | хост пулера (напр. `aws-0-<region>.pooler.supabase.com`), порт `5432`, user `postgres.<ref>` | **Беремо для бекенду і ETL** |
| Transaction pooler | той самий хост, порт `6543` | Для serverless. Ламає prepared statements asyncpg |

`backend/.env`:

```
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<url-encoded-password>@<pooler-host>:5432/postgres
DB_SSL=true
```

- Пароль зі спецсимволами (`@ # / % :`) треба закодувати: `python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" 'pa@ss'`.
- `DB_SSL=true` додає `ssl="require"` у `connect_args` (див. `app/db.py`) і в runner міграцій.
- Пул тримай маленьким (`DB_POOL_SIZE` ≤ 5). У безкоштовного пулера ліміт клієнтів, а в одну базу ходять усі учасники плюс ETL.
- Безкоштовний план дає 500 MB. Проєкт засинає після 7 днів без активності, тож напередодні демо зайди в дашборд.

Якщо все ж потрібен transaction pooler (6543), prepared statements доведеться вимкнути:

```python
from uuid import uuid4
from sqlalchemy.pool import NullPool
create_async_engine(url, poolclass=NullPool, connect_args={
    "statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
})
```

## Типові помилки

| Симптом | Причина | Що робити |
|---|---|---|
| `nodename nor servname provided`, `Network is unreachable` | direct-хост лише з IPv6 | перейти на session pooler |
| `password authentication failed`, `Tenant or user not found` | для пулера user має бути `postgres.<ref>`, а не `postgres` | виправити user у URL |
| `prepared statement "__asyncpg_stmt_…__" already exists` | transaction pooler (6543) | порт 5432 або налаштування вище |
| `connection reset` / SSL-помилки | без SSL | `DB_SSL=true` |

## Міграції

- Кожен модуль тримає свої файли в `app/<module>/migrations/NNN_short_name.sql`. Команда `uv run python -m app.migrate` застосовує нові файли по порядку, кожен в окремій транзакції. Застосовані файли записуються в `schema_migrations` як `catalog/001_init.sql`.
- **Застосовану міграцію не редагуй, додай нову `002_…`.** База одна на всю команду. Змінений старий файл уже ніде не виконається, і локальна схема розійдеться з Supabase.
- Пиши ідемпотентно (`create table if not exists`, `create index if not exists`), щоб чиста локальна БД і Supabase отримували однакову схему.
- Можна обійтися без Python: вставити файл у Supabase → SQL Editor. Тоді вручну додай рядок у `schema_migrations`, інакше runner виконає файл ще раз.

## Конвенції схеми

- Назви — snake_case, таблиці в множині. Кожна таблиця належить одному модулю.
- **Гроші зберігай у `numeric(10,2)`, ніколи не у `float`/`real`.** З float `74.99 * 3` дає `224.97000000000003`, і суми кошика перестають сходитися з чеком.
- Час — `timestamptz`. Зовнішні id (store_id із Zakaz, branchId Сільпо) — `text`. В ORM `datetime` теж має бути з часовим поясом: це задано глобально в `Base.type_annotation_map` (`app/db.py`). Інакше asyncpg падає на порівнянні з `now()` з помилкою `can't subtract offset-naive and offset-aware datetimes`.
- GTIN/EAN — `text`, нормалізований до 13 цифр (див. скіл `grocery-price-apis`). Не число: інакше зникнуть нулі на початку.
- Теги — `text[]` з GIN-індексом. Сирі відповіді API в БД не зберігаємо (сотні МБ за ніч при ліміті 500 МБ), лише розібрані поля; `jsonb` — для невеликих структур на кшталт `nutrition` чи `stats`.
- Зовнішніх ключів між модулями не роби. Агент не посилається на таблиці каталогу, а отримує дані через `app.catalog.service`.

## Запис даних

ETL має бути повторюваним, тому використовуй upsert:

```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Offer).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=[Offer.store_id, Offer.source_sku],
    set_={c: stmt.excluded[c] for c in ("price", "old_price", "unit_price", "in_stock", "fetched_at")},
)
await session.execute(stmt)
await session.commit()
```

- Пиши пачками по 500–1000 рядків. Кожен запит до Supabase іде через інтернет (десятки мс), тож 20 тис. окремих INSERT займуть хвилини.
- Asyncpg приймає максимум 32767 параметрів на запит. Кількість рядків у пачці × кількість колонок має бути меншою.

## Читання

- Для порівняння кошика бери кандидатів одним запитом, наприклад `where store_id = any(:store_ids) and category = any(:categories)`. Вибір пачок роби в Python: так його простіше тестувати.
- **Пошук за назвою не має залежати від локалі БД.** Локальний Homebrew-кластер створено з локаллю `C`, і на ньому перевірено:
  - `lower('Галичина')` повертає `Галичина` без змін;
  - `show_trgm('молоко')` повертає `{}`;
  - `word_similarity` для кирилиці дорівнює 0, отже `similarity()` і оператор `%` не працюють.

  Тому `products.search_text` (нижній регістр, без лапок) рахує ETL у Python (`normalize.search_text`). Пошук іде через `search_text LIKE '%слово%'` для кожного слова запиту, слова теж нормалізуються в Python. Сортування — без trigram-функцій (див. `catalog.service.search_prices`). Не заповнюй колонки SQL-функцією `lower()` у міграціях. Перевірити локаль: `select datctype from pg_database where datname = current_database();`.

## Безпека

- `DATABASE_URL` з паролем і `service_role`-ключ зберігаються лише в `backend/.env`. Ні у фронт, ні в git вони не потрапляють.
- Supabase автоматично відкриває таблиці схеми `public` через свій REST API з публічним `anon`-ключем. Ми цим API не користуємося, тому кожна міграція вмикає `alter table … enable row level security;` без політик. REST-доступ так закрито, а наш бекенд як власник таблиць (`postgres`) RLS обходить.
- Фронт звертається тільки до FastAPI.

## Локальна розробка

Ті самі міграції ганяй на локальному Postgres 16: `postgresql+asyncpg://postgres:postgres@localhost:5432/voicecart`, `DB_SSL=false`. Можна і в Docker (`postgres:16`). Схема має бути однаковою локально й у Supabase.

На macOS Postgres із Homebrew може не стартувати з помилкою `postmaster became multithreaded during startup`. Тоді перед `pg_ctl start` задай `export LC_ALL=en_US.UTF-8`.
