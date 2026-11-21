# Схема БД (модуль catalog)

Джерело правди — SQL-міграції в [`backend/app/catalog/migrations/`](../backend/app/catalog/migrations/). Діаграму оновлюй разом із новою міграцією.

```mermaid
erDiagram
  STORES ||--o{ OFFERS : "продає"
  PRODUCTS ||--o{ OFFERS : "має ціни"

  STORES {
    text id PK "Zakaz store id або branchId Сільпо"
    text source "zakaz | silpo"
    text chain "silpo, novus, auchan..."
    text name
    text city "Київ"
    text address
    float lat
    float lng
    bool has_pickup
    bool is_active "false = немає онлайн-каталогу"
    timestamptz updated_at
  }

  PRODUCTS {
    bigint id PK
    text gtin UK "EAN-13, той самий товар у різних мережах"
    text source_key UK "zakaz:ean / silpo:slug, якщо GTIN немає"
    text_array alt_gtins
    text title
    text brand
    text category "milk, curd, eggs..."
    numeric pack_qty "950"
    text pack_unit "g | ml | pcs"
    numeric fat_pct
    text ingredients
    bool composition_known "false = склад невідомий"
    text_array tags "sugar, palm_oil, lactose, private_label"
    jsonb nutrition
    text img_url
    text search_text "назви з усіх мереж, для pg_trgm"
    timestamptz updated_at
  }

  OFFERS {
    text store_id PK, FK
    text source_sku PK "ean у Zakaz, slug у Сільпо"
    bigint product_id FK
    text title_raw
    numeric price "грн за пачку"
    numeric old_price
    smallint promo_percent
    date promo_until
    numeric unit_price "грн за кг / л / шт"
    bool in_stock
    int stock "лише Сільпо"
    text url
    timestamptz fetched_at
  }

  ETL_RUNS {
    bigint id PK
    text trigger "schedule | manual"
    text status "running | ok | failed"
    timestamptz started_at
    timestamptz finished_at
    jsonb stats
    text error
  }

  SCHEMA_MIGRATIONS {
    text version PK "catalog/001_init.sql"
    timestamptz applied_at
  }
```

- `offers` — це ціна конкретного товару в конкретному магазині. Одна пачка молока в 5 мережах дає 1 рядок у `products` і 5 у `offers`.
- `etl_runs` — журнал нічного ETL (03:00 за Києвом). З нього UI бере «ціни оновлено о …».
- `schema_migrations` — службова таблиця раннера міграцій. На всіх таблицях увімкнено RLS: публічний REST Supabase до них не має доступу.
- Сирі відповіді API в БД не зберігаємо: одна сторінка пошуку займає 150–360 КБ, і нічний прогін швидко з'їв би 500 МБ безкоштовного Supabase. Таблицю `raw_items` прибрано міграцією `004_drop_raw_items.sql`; для налагодження парсера сирі відповіді кладемо файлами в `backend/data/raw/` (є в `.gitignore`).
