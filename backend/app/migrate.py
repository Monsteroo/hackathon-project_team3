"""Застосовує SQL-міграції модулів з app/<module>/migrations/NNN_*.sql.

Запуск з backend/:  uv run python -m app.migrate

Кожен файл виконується в окремій транзакції і записується в schema_migrations
як "<module>/<file>". Уже застосовані файли не редагуй: додай новий.
"""

import asyncio
from pathlib import Path

import asyncpg

from app.config import get_settings

APP_DIR = Path(__file__).parent

# Модулі, на які можуть спиратися інші, застосовуються першими. Решта йде за алфавітом.
MODULE_ORDER = ["catalog"]

# Довільне число для pg_advisory_lock, щоб двоє учасників не мігрували одночасно.
LOCK_ID = 7_202_611


def discover() -> list[tuple[str, Path]]:
    modules = sorted(p.parent.name for p in APP_DIR.glob("*/migrations") if p.is_dir())
    ordered = [m for m in MODULE_ORDER if m in modules] + [m for m in modules if m not in MODULE_ORDER]
    return [
        (f"{module}/{path.name}", path)
        for module in ordered
        for path in sorted((APP_DIR / module / "migrations").glob("*.sql"))
    ]


async def migrate() -> list[str]:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn, ssl="require" if settings.db_ssl else None)
    try:
        await conn.execute("select pg_advisory_lock($1)", LOCK_ID)
        await conn.execute(
            """
            create table if not exists schema_migrations (
                version text primary key,
                applied_at timestamptz not null default now()
            );
            alter table schema_migrations enable row level security;
            """
        )
        applied = {row["version"] for row in await conn.fetch("select version from schema_migrations")}
        done: list[str] = []
        for version, path in discover():
            if version in applied:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute("insert into schema_migrations (version) values ($1)", version)
            done.append(version)
        return done
    finally:
        await conn.close()


def main() -> None:
    done = asyncio.run(migrate())
    print("\n".join(f"applied {v}" for v in done) if done else "nothing to apply")


if __name__ == "__main__":
    main()
