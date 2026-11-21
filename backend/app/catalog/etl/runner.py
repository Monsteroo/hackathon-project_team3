"""Оркестрація ETL: магазини -> товари й ціни -> БД.

Одночасно працює лише один запуск (pg_advisory_lock). Тому планувальник у кожному процесі FastAPI
може спокійно стартувати задачу о 03:00: решта процесів побачать зайнятий lock і пропустять запуск.
"""

import asyncio
import logging
import time
from datetime import datetime

from sqlalchemy import text

from app.catalog.etl import load, silpo, zakaz
from app.catalog.etl.categories import Category
from app.catalog.etl.categories import select as select_categories
from app.catalog.etl.http import Http
from app.catalog.etl.records import GtinIndex, OfferRec, ProductRec, StoreRec, merge_products
from app.catalog.etl.silpo import SilpoDetail
from app.config import get_settings
from app.db import SessionLocal, engine

log = logging.getLogger("app.catalog.etl")

LOCK_KEY = 7_202_612
SOURCES = ("zakaz", "silpo")
ZAKAZ_PASSES = 2  # другий прохід лише по магазинах, де були помилки
ZAKAZ_RETRY_PAUSE_S = 60


async def run_etl(
    trigger: str = "manual",
    city: str | None = None,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    zakaz_store_limit: int | None = None,
    silpo_branch_limit: int | None = None,
) -> dict:
    settings = get_settings()
    unknown = set(sources or ()) - set(SOURCES)
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(sorted(unknown))}")
    options = {
        "city": city or settings.etl_city,
        "sources": tuple(sources or SOURCES),
        "categories": select_categories(categories),
        "zakaz_store_limit": zakaz_store_limit if zakaz_store_limit is not None else settings.etl_zakaz_store_limit,
        "silpo_branch_limit": silpo_branch_limit if silpo_branch_limit is not None else settings.etl_silpo_branch_limit,
    }

    async with engine.connect() as conn:
        lock_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        if not await lock_conn.scalar(text("select pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}):
            log.warning("another ETL run holds the lock, skipping")
            return {"status": "skipped", "reason": "another ETL run is in progress"}
        try:
            return await _locked_run(trigger, **options)
        finally:
            await lock_conn.execute(text("select pg_advisory_unlock(:key)"), {"key": LOCK_KEY})


async def _locked_run(
    trigger: str,
    city: str,
    sources: tuple[str, ...],
    categories: list[Category],
    zakaz_store_limit: int | None,
    silpo_branch_limit: int | None,
) -> dict:
    stats: dict = {
        "city": city,
        "sources": list(sources),
        "categories": len(categories),
        "stores_zakaz": 0,
        "stores_silpo": 0,
        "stores_failed": 0,
        "silpo_branches_without_catalog": 0,
        "offers_upserted": 0,
        "offers_marked_unavailable": 0,
    }
    started = time.monotonic()
    async with SessionLocal() as session:
        run_id, run_started = await load.start_run(session, trigger)
        await session.commit()
    log.info("ETL run %s started (%s): city=%s sources=%s", run_id, trigger, city, ",".join(sources))

    http = Http(concurrency=get_settings().etl_concurrency)
    status, error = "ok", None
    try:
        zakaz_stores = await zakaz.fetch_stores(http, city) if "zakaz" in sources else []
        silpo_branches = await silpo.fetch_branches(http, city) if "silpo" in sources else []
        zakaz_stores = zakaz_stores[:zakaz_store_limit] if zakaz_store_limit else zakaz_stores
        silpo_branches = silpo_branches[:silpo_branch_limit] if silpo_branch_limit else silpo_branches
        async with SessionLocal() as session:
            await load.upsert_stores(session, zakaz_stores + silpo_branches)
            await session.commit()
            index = await load.gtin_index(session)
        log.info("stores: zakaz=%d silpo=%d", len(zakaz_stores), len(silpo_branches))

        await _run_zakaz(http, zakaz_stores, categories, run_started, stats, index)
        await _run_silpo(http, silpo_branches, categories, run_started, stats, index)

        attempted = len(zakaz_stores) + len(silpo_branches)
        if attempted and stats["stores_failed"] == attempted:
            status, error = "failed", "all stores failed"
        else:
            async with SessionLocal() as session:
                stats["orphan_products_deleted"] = await load.delete_orphan_products(session)
                await session.commit()
    except Exception as exc:  # журнал запуску має закритися навіть при неочікуваній помилці
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        log.exception("ETL run %s failed", run_id)
    finally:
        await http.aclose()
        stats.update(http_requests=http.requests, http_failures=http.failures, http_rate_limited=http.rate_limited)
        stats["duration_s"] = round(time.monotonic() - started, 1)
        async with SessionLocal() as session:
            stats.update(await load.totals(session))
            await load.finish_run(session, run_id, status, stats, error)
            await session.commit()
    log.info("ETL run %s finished: %s %s", run_id, status, stats)
    return {"status": status, "run_id": run_id, **stats, **({"error": error} if error else {})}


async def _run_zakaz(
    http: Http,
    stores: list[StoreRec],
    categories: list[Category],
    run_started: datetime,
    stats: dict,
    index: GtinIndex,
) -> None:
    failed_by_store: dict[str, int] = {}
    pending = list(stores)
    for attempt in range(1, ZAKAZ_PASSES + 1):
        for store in pending:
            pairs, failed = await zakaz.fetch_store_offers(http, store, categories)
            saved = await _save(pairs, store.id, run_started, failed == 0, stats, index)
            failed_by_store[store.id] = failed
            log.info("zakaz %-12s %-32s %4d offers, %d categories failed", store.chain, store.name, saved, failed)
        pending = [s for s in pending if failed_by_store[s.id]]
        if not pending or attempt == ZAKAZ_PASSES:
            break
        # Найчастіше це ліміт запитів (429): даємо API охолонути й повторюємо лише магазини з помилками.
        log.warning("zakaz: %d stores had errors, retrying them in %ss", len(pending), ZAKAZ_RETRY_PAUSE_S)
        await asyncio.sleep(ZAKAZ_RETRY_PAUSE_S)
    stats["stores_zakaz"] += len(stores)
    stats["stores_failed"] += sum(n == len(categories) for n in failed_by_store.values())
    stats["stores_partial"] = sum(0 < n < len(categories) for n in failed_by_store.values())


async def _run_silpo(
    http: Http,
    branches: list[StoreRec],
    categories: list[Category],
    run_started: datetime,
    stats: dict,
    index: GtinIndex,
) -> None:
    if not branches:
        return
    async with SessionLocal() as session:
        known = await load.known_silpo_details(session)
    details: dict[str, SilpoDetail] = {}
    without_catalog: list[str] = []
    for branch in branches:
        items, failed = await silpo.fetch_branch_items(http, branch.id, categories)
        stats["stores_silpo"] += 1
        stats["stores_failed"] += failed == len(categories)
        if not items and not failed:
            without_catalog.append(branch.id)
            log.info("silpo %-44s no catalog", f"{branch.name} {branch.address}")
            continue
        # Штрихкод є лише в картці товару. Тягнемо її один раз на slug за весь запуск і не тягнемо зовсім,
        # якщо товар уже є в БД з минулих запусків.
        new_slugs = sorted({item["slug"] for _, item in items} - details.keys() - known.keys())
        fetched = await asyncio.gather(*(silpo.fetch_detail(http, slug) for slug in new_slugs))
        details.update({slug: d for slug, d in zip(new_slugs, fetched, strict=True) if d})
        pairs = [
            pair
            for cat, item in items
            if (pair := silpo.parse_item(item, branch.id, cat, details.get(item["slug"]) or known.get(item["slug"])))
        ]
        saved = await _save(pairs, branch.id, run_started, failed == 0, stats, index)
        log.info("silpo %-44s %4d offers, %d new cards", f"{branch.name} {branch.address}", saved, len(new_slugs))
    stats["silpo_branches_without_catalog"] = len(without_catalog)
    async with SessionLocal() as session:
        await load.set_stores_active(session, without_catalog, False)
        await session.commit()


async def _save(
    pairs: list[tuple[ProductRec, OfferRec]],
    store_id: str,
    run_started: datetime,
    mark_unseen: bool,
    stats: dict,
    index: GtinIndex,
) -> int:
    # Спершу зводимо коди до канонічного GTIN, а вже потім об'єднуємо записи того самого товару.
    for product, offer in pairs:
        index.resolve(product)
        offer.product_key = product.key
    products = merge_products([p for p, _ in pairs])
    async with SessionLocal() as session:
        product_ids = await load.upsert_products(session, products)
        saved = await load.upsert_offers(session, [o for _, o in pairs], product_ids)
        marked = await load.mark_unseen_offers(session, store_id, run_started) if mark_unseen else 0
        await session.commit()
    for product in products:
        if product.gtin:
            index.add(product.gtin, product.alt_gtins)
    stats["offers_upserted"] += saved
    stats["offers_marked_unavailable"] += marked
    return saved
