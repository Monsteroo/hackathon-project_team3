"""Запис результатів ETL у БД пачками через upsert: повторний запуск оновлює рядки, а не дублює їх."""

from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import case, delete, exists, func, literal_column, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.etl.normalize import search_text
from app.catalog.etl.records import GtinIndex, OfferRec, ProductRec, StoreRec
from app.catalog.etl.silpo import SilpoDetail
from app.catalog.models import EtlRun, Offer, Product, Store

BATCH = 300  # asyncpg приймає не більше 32767 параметрів на запит: рядки x колонки


def _chunks(items: list, size: int = BATCH) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


# ---------- магазини ----------

_STORE_FIELDS = ("source", "chain", "name", "city", "address", "lat", "lng", "has_pickup", "is_active")


async def upsert_stores(session: AsyncSession, stores: list[StoreRec]) -> None:
    for chunk in _chunks([asdict(s) for s in stores]):
        stmt = insert(Store).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Store.id],
            set_={**{f: stmt.excluded[f] for f in _STORE_FIELDS}, "updated_at": func.now()},
        )
        await session.execute(stmt)


async def set_stores_active(session: AsyncSession, store_ids: list[str], active: bool) -> None:
    if store_ids:
        await session.execute(
            update(Store).where(Store.id.in_(store_ids)).values(is_active=active, updated_at=func.now())
        )


# ---------- товари ----------


def _product_row(p: ProductRec) -> dict:
    return {
        "gtin": p.gtin,
        "source_key": None if p.gtin else p.source_key,
        "alt_gtins": p.alt_gtins,
        "title": p.title,
        "brand": p.brand,
        "category": p.category,
        "pack_qty": p.pack_qty,
        "pack_unit": p.pack_unit,
        "fat_pct": p.fat_pct,
        "ingredients": p.ingredients,
        "composition_known": p.composition_known,
        "tags": p.tags,
        "nutrition": p.nutrition,
        "img_url": p.img_url,
        "search_text": search_text(p.title, p.brand),
    }


async def upsert_products(session: AsyncSession, products: list[ProductRec]) -> dict[str, int]:
    """Повертає {product.key: products.id}. Записи мають бути вже зведені merge_products (унікальні ключі)."""
    ids: dict[str, int] = {}
    groups = (
        (Product.gtin, [p for p in products if p.gtin]),
        (Product.source_key, [p for p in products if not p.gtin and p.source_key]),
    )
    for conflict_column, group in groups:
        for chunk in _chunks(group):
            stmt = insert(Product).values([_product_row(p) for p in chunk])
            new = stmt.excluded
            stmt = stmt.on_conflict_do_update(
                index_elements=[conflict_column],
                set_={
                    # Назва зі Zakaz (з вагою) не перезаписується назвою Сільпо без складу.
                    "title": case((new.composition_known, new.title), else_=Product.title),
                    # Коди з усіх мереж накопичуються, щоб наступні прогони зводили товар за будь-яким із них.
                    "alt_gtins": literal_column(
                        "array(select distinct unnest(products.alt_gtins || excluded.alt_gtins) order by 1)"
                    ),
                    "brand": func.coalesce(new.brand, Product.brand),
                    "category": func.coalesce(Product.category, new.category),
                    "pack_qty": func.coalesce(new.pack_qty, Product.pack_qty),
                    "pack_unit": func.coalesce(new.pack_unit, Product.pack_unit),
                    "fat_pct": func.coalesce(new.fat_pct, Product.fat_pct),
                    # Склад не затираємо порожнім: Сільпо його майже не віддає, а Zakaz віддає.
                    "ingredients": func.coalesce(new.ingredients, Product.ingredients),
                    "composition_known": or_(new.composition_known, Product.composition_known),
                    "tags": case((new.composition_known, new.tags), else_=Product.tags),
                    "nutrition": func.coalesce(new.nutrition, Product.nutrition),
                    "img_url": func.coalesce(Product.img_url, new.img_url),
                    # Назви з різних мереж накопичуються: товар знайдеться за будь-якою з них.
                    "search_text": case(
                        (Product.search_text.is_(None), new.search_text),
                        (func.strpos(Product.search_text, new.search_text) > 0, Product.search_text),
                        else_=Product.search_text + " | " + new.search_text,
                    ),
                    "updated_at": func.now(),
                },
            ).returning(Product.id, Product.gtin, Product.source_key)
            for product_id, gtin, source_key in (await session.execute(stmt)).all():
                ids[gtin or source_key] = product_id
    return ids


async def gtin_index(session: AsyncSession) -> GtinIndex:
    """Індекс штрихкодів з БД. Кращі товари (зі складом, з більшою кількістю цін) мають пріоритет."""
    stmt = (
        select(Product.gtin, Product.alt_gtins)
        .outerjoin(Offer, Offer.product_id == Product.id)
        .where(Product.gtin.is_not(None))
        .group_by(Product.id)
        .order_by(Product.composition_known.desc(), func.count(Offer.store_id).desc(), Product.id)
    )
    index = GtinIndex()
    for gtin, alt_gtins in (await session.execute(stmt)).all():
        index.add(gtin, list(alt_gtins or []))
    return index


async def delete_orphan_products(session: AsyncSession) -> int:
    """Товари без жодної ціни (наприклад, дублікати, чиї ціни перейшли на канонічний товар)."""
    result = await session.execute(delete(Product).where(~exists().where(Offer.product_id == Product.id)))
    return result.rowcount or 0


async def known_silpo_details(session: AsyncSession) -> dict[str, SilpoDetail]:
    """Slug товарів Сільпо, які вже є в БД: для них не треба знову тягнути картку заради штрихкоду."""
    stmt = (
        select(Offer.source_sku, Product.gtin, Product.alt_gtins)
        .join(Product, Product.id == Offer.product_id)
        .join(Store, Store.id == Offer.store_id)
        .where(Store.source == "silpo")
        .distinct()
    )
    return {
        slug: SilpoDetail(gtin=gtin, alt_gtins=list(alt or []))
        for slug, gtin, alt in (await session.execute(stmt)).all()
    }


# ---------- ціни ----------

_OFFER_FIELDS = (
    "product_id",
    "title_raw",
    "source_category",
    "price",
    "old_price",
    "promo_percent",
    "promo_until",
    "unit_price",
    "in_stock",
    "stock",
    "url",
)


async def upsert_offers(session: AsyncSession, offers: list[OfferRec], product_ids: dict[str, int]) -> int:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for o in offers:
        key = (o.store_id, o.source_sku)
        product_id = product_ids.get(o.product_key)
        if key in seen or product_id is None:  # той самий товар у двох категоріях: лишаємо перший
            continue
        seen.add(key)
        rows.append({"store_id": o.store_id, "source_sku": o.source_sku, **asdict(o), "product_id": product_id})
    for chunk in _chunks(rows):
        values = [{k: r[k] for k in ("store_id", "source_sku", *_OFFER_FIELDS)} for r in chunk]
        stmt = insert(Offer).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Offer.store_id, Offer.source_sku],
            set_={**{f: stmt.excluded[f] for f in _OFFER_FIELDS}, "fetched_at": func.now()},
        )
        await session.execute(stmt)
    return len(rows)


async def mark_unseen_offers(session: AsyncSession, store_id: str, since: datetime) -> int:
    """Товари, яких цього разу не було у видачі магазину, позначаємо відсутніми, а не лишаємо зі старою ціною."""
    result = await session.execute(
        update(Offer)
        .where(Offer.store_id == store_id, Offer.fetched_at < since, Offer.in_stock.is_(True))
        .values(in_stock=False)
    )
    return result.rowcount or 0


# ---------- журнал запусків ----------


async def start_run(session: AsyncSession, trigger: str) -> tuple[int, datetime]:
    """Відкриває запис запуску. Викликається під pg_advisory_lock, тож інших живих запусків немає, і всі
    записи 'running' — це перервані процеси (вбиті, впав ноутбук). Закриваємо їх, щоб статус не брехав."""
    await session.execute(
        update(EtlRun)
        .where(EtlRun.status == "running")
        .values(status="failed", error="interrupted: the ETL process stopped before finishing", finished_at=func.now())
    )
    result = await session.execute(
        insert(EtlRun).values(status="running", trigger=trigger).returning(EtlRun.id, EtlRun.started_at)
    )
    run_id, started_at = result.one()
    return run_id, started_at


async def finish_run(session: AsyncSession, run_id: int, status: str, stats: dict, error: str | None) -> None:
    await session.execute(
        update(EtlRun)
        .where(EtlRun.id == run_id)
        .values(status=status, stats=stats, error=error, finished_at=func.now())
    )


async def totals(session: AsyncSession) -> dict[str, int]:
    products = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    offers = (await session.execute(select(func.count()).select_from(Offer))).scalar_one()
    return {"products_total": products, "offers_total": offers}
