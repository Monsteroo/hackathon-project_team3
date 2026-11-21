-- Модуль catalog: магазини, товари, ціни в магазинах, сирі відповіді API.

create extension if not exists pg_trgm;

-- Магазин мережі. id: для Zakaz.ua його store id ("482010105"), для Сільпо branchId (uuid).
create table if not exists stores (
    id          text primary key,
    source      text not null check (source in ('zakaz', 'silpo')),
    chain       text not null,                 -- silpo, novus, auchan, metro, ultramarket, ekomarket, ...
    name        text not null,
    city        text,                          -- українською: "Київ", "Львів"
    address     text,
    lat         double precision,
    lng         double precision,
    has_pickup  boolean not null default false,
    is_active   boolean not null default true,
    updated_at  timestamptz not null default now()
);
create index if not exists stores_city_chain_idx on stores (city, chain);

-- Товар незалежно від магазину. Однаковий GTIN означає той самий товар у різних мережах.
create table if not exists products (
    id                 bigint generated always as identity primary key,
    gtin               text unique,                    -- EAN-13 без нулів на початку; null, якщо коду немає
    alt_gtins          text[] not null default '{}',   -- інші коди товару (у Сільпо їх кілька)
    title              text not null,
    brand              text,
    category           text,                           -- канонічна категорія: milk, curd, eggs, ...
    pack_qty           numeric(10, 3),                 -- 950
    pack_unit          text check (pack_unit in ('g', 'ml', 'pcs')),
    fat_pct            numeric(5, 2),
    ingredients        text,
    composition_known  boolean not null default false,  -- false = склад не перевірено, а не "чистий"
    tags               text[] not null default '{}',   -- sugar, palm_oil, lactose, private_label
    nutrition          jsonb,
    img_url            text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists products_category_idx on products (category);
create index if not exists products_tags_idx on products using gin (tags);
create index if not exists products_alt_gtins_idx on products using gin (alt_gtins);
create index if not exists products_title_trgm_idx on products using gin (title gin_trgm_ops);

-- Ціна товару в конкретному магазині на момент завантаження.
create table if not exists offers (
    store_id         text not null references stores (id) on delete cascade,
    source_sku       text not null,                   -- id товару в джерелі (Zakaz ean/sku, Сільпо slug)
    product_id       bigint not null references products (id) on delete cascade,
    title_raw        text not null,
    source_category  text,                            -- категорія мережі: "curd-auchan", "uht-milk"
    price            numeric(10, 2) not null,         -- ₴ за пачку
    old_price        numeric(10, 2),
    promo_percent    smallint,
    promo_until      date,
    unit_price       numeric(10, 2),                  -- ₴ за кг / л / шт
    in_stock         boolean not null default true,
    stock            integer,                         -- кількість (лише Сільпо)
    url              text,
    fetched_at       timestamptz not null default now(),
    primary key (store_id, source_sku)
);
create index if not exists offers_product_idx on offers (product_id);

-- Сирі відповіді API: щоб переписати парсер, не завантажуючи дані знову.
create table if not exists raw_items (
    id          bigint generated always as identity primary key,
    source      text not null,
    store_id    text,
    kind        text not null,                        -- stores | search | category | detail
    payload     jsonb not null,
    fetched_at  timestamptz not null default now()
);
create index if not exists raw_items_source_kind_idx on raw_items (source, kind, fetched_at);

-- Supabase відкриває таблиці public через REST з anon-ключем. Ми його не використовуємо:
-- RLS без політик закриває цей доступ, а бекенд (власник таблиць) RLS обходить.
alter table stores    enable row level security;
alter table products  enable row level security;
alter table offers    enable row level security;
alter table raw_items enable row level security;
