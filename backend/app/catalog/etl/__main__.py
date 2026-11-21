"""CLI: uv run python -m app.catalog.etl [--city Київ] [--sources zakaz,silpo] [--categories milk,curd] ..."""

import argparse
import asyncio
import json
import logging
import sys

from app.catalog.etl.runner import SOURCES, run_etl
from app.db import engine


def _csv(value: str | None) -> list[str] | None:
    return [part.strip() for part in value.split(",") if part.strip()] if value else None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.catalog.etl",
        description="Завантажити магазини, товари й ціни з Zakaz.ua і Сільпо в БД (той самий джоб, що й о 03:00).",
    )
    parser.add_argument("--city", help='місто українською; за замовчуванням ETL_CITY ("Київ")')
    parser.add_argument("--sources", default=",".join(SOURCES), help="джерела через кому: zakaz,silpo")
    parser.add_argument("--categories", help="ключі категорій через кому (за замовчуванням усі), напр. milk,curd")
    parser.add_argument("--zakaz-store-limit", type=int, help="лише перші N магазинів Zakaz (для швидкого прогону)")
    parser.add_argument("--silpo-branch-limit", type=int, help="лише перші N філій Сільпо (для швидкого прогону)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    async def _run() -> dict:
        try:
            return await run_etl(
                trigger="manual",
                city=args.city,
                sources=_csv(args.sources),
                categories=_csv(args.categories),
                zakaz_store_limit=args.zakaz_store_limit,
                silpo_branch_limit=args.silpo_branch_limit,
            )
        finally:
            await engine.dispose()

    result = asyncio.run(_run())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") in ("ok", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
