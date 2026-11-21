---
name: fastapi-backend
description: Конвенції бекенду VoiceCart у backend/ (FastAPI, async SQLAlchemy 2, Pydantic v2, uv, pytest) і його поділ на модулі учасників (app/catalog, app/geo, app/agent…). Використовуй щоразу, коли додаєш або змінюєш ендпоінт, роутер, Pydantic-схему, сервісну функцію, залежність, налаштування, новий модуль чи тести в backend/ — навіть якщо FastAPI прямо не названо ("додай API для агента", "віддай це фронту", "напиши тест на ендпоінт", "add an endpoint", "expose this to the UI").
---

# FastAPI-бекенд VoiceCart

Один FastAPI-сервіс, поділений на модулі учасників. Спільне ядро тонке, вся предметна логіка живе в модулях. Так кожен учасник працює у своїй папці й не конфліктує з іншими в git.

## Структура

```
backend/
  pyproject.toml          # залежності, ruff, pytest (керує uv)
  .env.example            # скопіювати в .env (.env не комітимо)
  app/
    main.py               # create_app(): CORS, /health, підключення роутерів модулів
    config.py             # Settings (pydantic-settings) + get_settings()
    db.py                 # async engine, SessionDep, Base
    types.py              # спільні типи (Money)
    migrate.py            # застосовує app/<module>/migrations/*.sql
    scheduler.py          # APScheduler: фонові задачі модулів (cron у процесі FastAPI)
    catalog/              # Учасник 2: магазини, товари, ціни, порівняння кошика
      router.py           # HTTP-шар, prefix /catalog
      schemas.py          # Pydantic-моделі = контракт із командою
      models.py           # SQLAlchemy ORM (дзеркало migrations/)
      service.py          # бізнес-логіка; публічні функції для інших модулів
      jobs.py             # фонові задачі модуля: register(scheduler)
      etl/                # нічний ETL: python -m app.catalog.etl
      migrations/NNN_*.sql
      tests/
  tests/                  # тести спільного ядра
```

## Правила модулів

- **Модуль — це папка `app/<name>/` з усім своїм:** роутер, схеми, моделі, сервіс, міграції, тести. Новий модуль підключається одним рядком `app.include_router(...)` у `app/main.py`.
- **Інші модулі беруть лише публічне:** функції з `service.py` і схеми з `schemas.py`. Наприклад, агент викликає `await app.catalog.service.compare_basket(session, request)`. Чужі `models.py` не імпортуй і SQL у чужі таблиці не пиши. Тоді власник модуля може міняти схему БД, не ламаючи інших.
- **Роутер тонкий:** валідує вхід, викликає сервіс, повертає схему. Логіку з сервісу легко тестувати без HTTP, і агент викликає її напряму, без зайвого HTTP-кола.
- **Роутер модуля захищений API-ключем:** `app.include_router(router, dependencies=[Depends(require_api_key)])` з `app/auth.py`. Клієнт передає заголовок `X-API-Key`, ключі задаються в `API_KEYS`. Не роби окремих перевірок ключа в ендпоінтах. У тестах ключі ставить `backend/conftest.py` (`test-api-key`), тож HTTP-тести мають передавати цей заголовок.

## Ендпоінти

```python
from fastapi import APIRouter
from app.db import SessionDep
from app.catalog import service
from app.catalog.schemas import StoreOut

router = APIRouter(prefix="/catalog", tags=["catalog"])

@router.get("/stores", response_model=list[StoreOut])
async def list_stores(session: SessionDep, city: str | None = None) -> list[StoreOut]:
    return await service.list_stores(session, city=city)
```

- Пиши тільки `async def` з `AsyncSession`. Зовнішні HTTP-запити роби через `httpx.AsyncClient`, а не `requests`: блокуючий виклик зупиняє event loop, і чекають усі інші запити до сервісу.
- Завжди вказуй `response_model` або типізований return. Це те, що Учасники 3 і 5 бачать у `/docs`, і за цим вони пишуть свій код.
- Помилки віддавай через `HTTPException(status_code=..., detail="...")`. 404 — коли ресурсу немає, 422 FastAPI віддає сам. `detail` пиши англійською, бо його читає код. Текст для людини формує UI.

## Схеми (Pydantic v2)

- **Схеми — це контракт між учасниками.** Додавати поля можна. Перейменовувати чи видаляти — лише після домовленості з командою. Після зміни онови приклад відповіді в `mocks/`.
- ORM-об'єкт перетворюється на схему так: `model_config = ConfigDict(from_attributes=True)`, а далі `StoreOut.model_validate(row)`.
- **Гроші в коді й у БД — це `Decimal`.** Pydantic v2 серіалізує `Decimal` у JSON як рядок (`"74.99"`), а фронт чекає число. Тому для цін використовуй `Money` з `app/types.py`: у JSON він стає числом.
- Назви полів — snake_case англійською. Значення для людей (назви товарів, адреси) — як у джерелі, українською.

## Фонові задачі (cron у процесі FastAPI)

- Планувальник APScheduler живе в спільному ядрі (`app/scheduler.py`) і стартує в `lifespan`. Модуль описує свої задачі в `app/<module>/jobs.py` функцією `register(scheduler)`, а в `app/main.py` її додають у список `start_scheduler([...])`.
- Розклад задавай через `CronTrigger.from_crontab(..., timezone=settings.scheduler_timezone)` (за замовчуванням `Europe/Kyiv`) і виноси в налаштування (`ETL_CRON="0 3 * * *"`).
- **Задача має бути безпечною для паралельного запуску.** Планувальник стартує в кожному процесі: в кожного учасника, що підняв сервер, і в кожного воркера uvicorn. Тому ETL бере `pg_try_advisory_lock` і пропускає запуск, якщо lock зайнятий. Крім того, він ідемпотентний (upsert).
- Задача виконується, лише поки працює сервер. Пропущений запуск дозволено доганяти протягом `misfire_grace_time` (година).
- Ту саму логіку завжди можна запустити з CLI (`python -m app.<module>.…`). Так її простіше дебажити, ніж чекати 03:00.

## Налаштування

- Усе береться з env через `get_settings()`. Нову змінну додай у `Settings` і в `.env.example` з коментарем.
- Секрети живуть лише в `backend/.env`. Значення за замовчуванням у коді — тільки для локальної розробки.

## Тести

- Запускаються з `backend/` командою `uv run pytest`. Тести модуля лежать у `app/<module>/tests/`.
- Чисті функції (парсинг ваги, ціна за кг, теги складу) тестуй напряму, без БД. Вони є основою evals і мають проходити за секунди.
- HTTP-тести пиши через `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
- Тести, яким потрібна БД, мають пропускатися (`pytest.skip`), якщо БД недоступна: Postgres піднятий не в усіх у команді.

## Команди (з backend/)

```bash
uv sync                                  # залежності + .venv
uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
uv run pytest
uv run ruff check . && uv run ruff format .
uv run python -m app.migrate             # застосувати нові SQL-міграції
```

## Перед тим як сказати «готово»

- `uv run ruff check .` і `uv run pytest` проходять.
- Новий ендпоінт видно в `/docs`, і він повертає те, що описано в схемі. Перевір через `curl`, а не лише в тестах.
- Якщо змінився контракт, онови `mocks/` і скажи про це користувачу, щоб він передав команді.
