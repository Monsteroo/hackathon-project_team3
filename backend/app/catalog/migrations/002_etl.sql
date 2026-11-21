-- ETL: запасний ідентифікатор товару без публічного GTIN і журнал запусків.

-- "zakaz:<ean>" / "silpo:<slug>" для товарів без публічного штрихкоду (вагові, внутрішні коди магазину).
alter table products add column if not exists source_key text unique;

create table if not exists etl_runs (
    id           bigint generated always as identity primary key,
    started_at   timestamptz not null default now(),
    finished_at  timestamptz,
    status       text not null check (status in ('running', 'ok', 'failed')),
    trigger      text not null default 'manual' check (trigger in ('schedule', 'manual')),
    stats        jsonb not null default '{}',
    error        text
);
create index if not exists etl_runs_started_idx on etl_runs (started_at desc);

alter table etl_runs enable row level security;
