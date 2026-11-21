"""Публічні функції модуля catalog. Їх викликають роутер і інші модулі (наприклад, агент)."""

from collections import defaultdict

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.etl.normalize import COMPOSITION_TAGS, search_tokens
from app.catalog.jobs import NIGHTLY_ETL_JOB_ID
from app.catalog.models import EtlRun, Offer, Product, Store
from app.catalog.schemas import EtlRunOut, EtlStatusOut, PriceOut, PriceSearchOut, ProductPricesOut, StoreOut
from app.config import get_settings
from app.scheduler import get_scheduler

UNIT_PRICE_LABELS = {"g": "₴/кг", "ml": "₴/л", "pcs": "₴/шт"}


async def list_stores(
    session: AsyncSession, city: str | None = None, chain: str | None = None, with_prices: bool = True
) -> list[StoreOut]:
    """Активні магазини. З with_prices=True лише ті, для яких у БД є ціни, тобто з ними можна порівнювати."""
    counts = (
        select(Offer.store_id, func.count().label("n"))
        .where(Offer.in_stock.is_(True))
        .group_by(Offer.store_id)
        .subquery()
    )
    offers_count = func.coalesce(counts.c.n, 0)
    stmt = (
        select(Store, offers_count)
        .outerjoin(counts, counts.c.store_id == Store.id)
        .where(Store.is_active.is_(True))
        .order_by(Store.city, Store.chain, Store.name)
    )
    if city:
        stmt = stmt.where(Store.city == city)
    if chain:
        stmt = stmt.where(Store.chain == chain)
    if with_prices:
        stmt = stmt.where(offers_count > 0)
    rows = (await session.execute(stmt)).all()
    return [StoreOut.model_validate(store).model_copy(update={"offers_count": n}) for store, n in rows]


def _like_escape(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_prices(
    session: AsyncSession,
    query: str,
    store_ids: list[str] | None = None,
    category: str | None = None,
    exclude: list[str] | None = None,
    in_stock_only: bool = True,
    limit: int = 20,
) -> PriceSearchOut:
    """Товари, назва яких містить усі слова запиту, з цінами в запитаних магазинах (без store_ids — у всіх).

    exclude відсіює товари з цими тегами. Якщо серед них є теги складу (sugar, palm_oil), відсіюються
    й товари з невідомим складом: невідомий склад не можна вважати «без цукру».
    """
    tokens = search_tokens(query)
    if not tokens:
        raise ValueError("query has no searchable words")
    store_ids = list(dict.fromkeys(store_ids or []))
    exclude = list(dict.fromkeys(exclude or []))

    offer_filters = []
    if store_ids:
        offer_filters.append(Offer.store_id.in_(store_ids))
    if in_stock_only:
        offer_filters.append(Offer.in_stock.is_(True))

    # Порядок не залежить від локалі БД (у локалі C pg_trgm не бачить кирилиці): спершу товари, назва яких
    # починається з першого слова запиту, далі ті, що є в більшій кількості магазинів, коротші й дешевші за кг.
    starts_with_query = func.strpos(Product.search_text, tokens[0]) == 1
    stmt = (
        select(Product.id)
        .join(Offer, Offer.product_id == Product.id)
        .where(*(Product.search_text.like(f"%{_like_escape(t)}%", escape="\\") for t in tokens), *offer_filters)
        .group_by(Product.id)
        .order_by(
            starts_with_query.desc(),
            func.count(distinct(Offer.store_id)).desc(),
            func.length(Product.title),
            func.min(Offer.unit_price),
        )
        .limit(limit)
    )
    if category:
        stmt = stmt.where(Product.category == category)
    if exclude:
        stmt = stmt.where(~Product.tags.overlap(exclude))
        if COMPOSITION_TAGS & set(exclude):
            stmt = stmt.where(Product.composition_known.is_(True))
    product_ids = list((await session.scalars(stmt)).all())

    missing: list[str] = []
    if store_ids:
        found = set((await session.scalars(select(Store.id).where(Store.id.in_(store_ids)))).all())
        missing = [s for s in store_ids if s not in found]

    products_out: list[ProductPricesOut] = []
    if product_ids:
        products = {p.id: p for p in (await session.scalars(select(Product).where(Product.id.in_(product_ids))))}
        rows = (
            await session.execute(
                select(Offer, Store)
                .join(Store, Store.id == Offer.store_id)
                .where(Offer.product_id.in_(product_ids), *offer_filters)
                .order_by(Offer.price, Store.chain, Store.name)
            )
        ).all()
        prices: dict[int, list[PriceOut]] = defaultdict(list)
        for offer, store in rows:
            prices[offer.product_id].append(_price_out(offer, store, products[offer.product_id].pack_unit))
        products_out = [_product_out(products[pid], prices[pid]) for pid in product_ids if prices.get(pid)]

    return PriceSearchOut(
        query=query, tokens=tokens, store_ids=store_ids, missing_store_ids=missing, products=products_out
    )


def _price_out(offer: Offer, store: Store, pack_unit: str | None) -> PriceOut:
    return PriceOut(
        store_id=store.id,
        chain=store.chain,
        store_name=store.name,
        city=store.city,
        address=store.address,
        price=offer.price,
        old_price=offer.old_price,
        promo_percent=offer.promo_percent,
        promo_until=offer.promo_until,
        unit_price=offer.unit_price,
        unit_price_label=UNIT_PRICE_LABELS.get(pack_unit or "", "₴/кг"),
        in_stock=offer.in_stock,
        stock=offer.stock,
        url=offer.url,
        fetched_at=offer.fetched_at,
    )


def _product_out(product: Product, prices: list[PriceOut]) -> ProductPricesOut:
    unit_prices = [p.unit_price for p in prices if p.unit_price is not None]
    return ProductPricesOut(
        product_id=product.id,
        gtin=product.gtin,
        title=product.title,
        brand=product.brand,
        category=product.category,
        pack_qty=float(product.pack_qty) if product.pack_qty is not None else None,
        pack_unit=product.pack_unit,
        fat_pct=float(product.fat_pct) if product.fat_pct is not None else None,
        tags=list(product.tags or []),
        composition_known=product.composition_known,
        img_url=product.img_url,
        stores_count=len({p.store_id for p in prices}),
        min_price=min(p.price for p in prices),
        max_price=max(p.price for p in prices),
        min_unit_price=min(unit_prices) if unit_prices else None,
        prices=prices,
    )


async def etl_status(session: AsyncSession, limit: int = 5) -> EtlStatusOut:
    settings = get_settings()
    runs = (await session.scalars(select(EtlRun).order_by(EtlRun.started_at.desc()).limit(limit))).all()
    updated_at = (await session.execute(select(func.max(EtlRun.finished_at)).where(EtlRun.status == "ok"))).scalar_one()
    scheduler = get_scheduler()
    job = scheduler.get_job(NIGHTLY_ETL_JOB_ID) if scheduler else None
    return EtlStatusOut(
        schedule=settings.etl_cron,
        timezone=settings.scheduler_timezone,
        scheduler_running=bool(scheduler and scheduler.running),
        next_run_at=job.next_run_time if job else None,
        prices_updated_at=updated_at,
        last_runs=[EtlRunOut.model_validate(run) for run in runs],
    )
