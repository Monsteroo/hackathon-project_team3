"""Zakaz.ua: Novus, Auchan, Metro, Ultramarket, ЕКО Маркет, Megamarket та ін. Деталі API — скіл grocery-price-apis."""

import asyncio
from datetime import date
from decimal import Decimal

from app.catalog.etl.categories import Category
from app.catalog.etl.http import Http
from app.catalog.etl.normalize import build_tags, kopecks, parse_fat, parse_pack, pick_gtins, strip_html, unit_price
from app.catalog.etl.records import OfferRec, ProductRec, StoreRec

BASE_URL = "https://stores-api.zakaz.ua"
HEADERS = {"Accept-Language": "uk"}
PAGE_SIZE = 100
MAX_PAGES = 2  # далі пошук видає вже нерелевантне

NON_GROCERY = frozenset({"alcohub", "okwine", "winetime", "masterzoo", "biotus", "cosmos"})
CITY_NAMES = {
    "kiev": "Київ",
    "lviv": "Львів",
    "odesa": "Одеса",
    "kharkiv": "Харків",
    "dnipro": "Дніпро",
    "rivne": "Рівне",
    "zhytomyr": "Житомир",
    "vinnytsia": "Вінниця",
    "poltava": "Полтава",
    "chernivtsi": "Чернівці",
    "ivanofrankivsk": "Івано-Франківськ",
    "kryvyyrig": "Кривий Ріг",
}


def parse_store(raw: dict) -> StoreRec | None:
    if raw.get("retail_chain") in NON_GROCERY or not raw.get("is_active", True):
        return None
    address = raw.get("address") or {}
    coords = address.get("coords") or {}
    return StoreRec(
        id=str(raw["id"]),
        source="zakaz",
        chain=raw["retail_chain"],
        name=raw.get("name") or str(raw["id"]),
        city=CITY_NAMES.get(raw.get("city"), raw.get("city")),
        address=", ".join(p for p in (address.get("street"), address.get("building")) if p) or None,
        lat=coords.get("lat"),
        lng=coords.get("lng"),
        has_pickup="pickup" in (raw.get("delivery_types") or []),
    )


async def fetch_stores(http: Http, city: str | None) -> list[StoreRec]:
    raw = await http.get_json(f"{BASE_URL}/stores/", headers=HEADERS)
    stores = [s for s in map(parse_store, raw) if s]
    return [s for s in stores if city is None or s.city == city]


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def parse_item(item: dict, store_id: str, category: Category) -> tuple[ProductRec, OfferRec] | None:
    title = item.get("title") or ""
    ean = str(item.get("ean") or "")
    if not ean or not category.matches(title) or (item.get("price") or 0) <= 0:
        return None
    price = kopecks(item["price"])
    if item.get("unit") == "kg":  # ваговий товар: ціна за кг
        pack_qty, pack_unit = Decimal(1000), "g"
    else:
        pack_qty, pack_unit = parse_pack(title)
        if pack_qty is None and item.get("weight"):
            pack_qty, pack_unit = Decimal(str(item["weight"])), "g"
    if not pack_qty or not pack_unit:
        return None

    gtin, alt_gtins = pick_gtins([ean, *(item.get("eans") or [])])
    ingredients = strip_html(" ".join(item.get("ingredients") or []))
    brand = (item.get("producer") or {}).get("trademark")
    discount = item.get("discount") or {}
    promo = bool(discount.get("status"))
    old_price = kopecks(discount["old_price"]) if promo and discount.get("old_price") else None
    if old_price is not None and old_price <= price:
        old_price = None

    product = ProductRec(
        source="zakaz",
        gtin=gtin,
        source_key=None if gtin else f"zakaz:{ean}",
        title=title,
        category=category.key,
        pack_qty=pack_qty,
        pack_unit=pack_unit,
        brand=brand,
        alt_gtins=alt_gtins,
        fat_pct=parse_fat(title, item.get("fat")),
        ingredients=ingredients or None,
        composition_known=bool(ingredients),
        tags=build_tags(category.key, title, brand, ingredients),
        nutrition=item.get("nutrition_facts") or None,
        img_url=(item.get("img") or {}).get("s350x350"),
    )
    offer = OfferRec(
        store_id=store_id,
        source_sku=ean,
        product_key=product.key,
        title_raw=title,
        source_category=item.get("category_id"),
        price=price,
        old_price=old_price,
        promo_percent=discount.get("value") if old_price else None,
        promo_until=_date(discount.get("due_date")) if old_price else None,
        unit_price=unit_price(price, pack_qty, pack_unit),
        in_stock=bool(item.get("in_stock")),
        stock=None,
        url=item.get("web_url"),
    )
    return product, offer


async def _search_category(http: Http, store_id: str, category: Category) -> list[tuple[ProductRec, OfferRec]]:
    pairs: list[tuple[ProductRec, OfferRec]] = []
    for page in range(1, MAX_PAGES + 1):
        data = await http.get_json(
            f"{BASE_URL}/stores/{store_id}/products/search/",
            params={"q": category.query, "per_page": PAGE_SIZE, "page": page},
            headers=HEADERS,
        )
        results = data.get("results") or []
        pairs.extend(p for p in (parse_item(item, store_id, category) for item in results) if p)
        if not results or page * PAGE_SIZE >= (data.get("count") or 0):
            break
    return pairs


async def fetch_store_offers(
    http: Http, store: StoreRec, categories: list[Category]
) -> tuple[list[tuple[ProductRec, OfferRec]], int]:
    """Товари магазину за всіма категоріями. Повертає (пари товар+ціна, кількість категорій з помилкою)."""
    results = await asyncio.gather(*(_search_category(http, store.id, c) for c in categories), return_exceptions=True)
    pairs = [pair for res in results if not isinstance(res, BaseException) for pair in res]
    return pairs, sum(isinstance(res, BaseException) for res in results)
