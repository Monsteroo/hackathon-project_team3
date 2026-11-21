"""Сільпо: реальні магазини (branches), ціни й залишки по кожному. Деталі API — скіл grocery-price-apis."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

from app.catalog.etl.categories import Category
from app.catalog.etl.http import Http
from app.catalog.etl.normalize import build_tags, money, parse_fat, parse_pack, pick_gtins, strip_html, unit_price
from app.catalog.etl.records import OfferRec, ProductRec, StoreRec

BASE_URL = "https://sf-ecom-api.silpo.ua/v1/uk"
DEFAULT_BRANCH = "00000000-0000-0000-0000-000000000000"  # каталог за замовчуванням, не реальний магазин
IMG_URL = "https://images.silpo.ua/products/300x300/{icon}"
PAGE_SIZE = 100


@dataclass
class SilpoDetail:
    gtin: str | None
    alt_gtins: list[str] = field(default_factory=list)
    ingredients: str | None = None
    nutrition: dict | None = None


def parse_branch(raw: dict) -> StoreRec | None:
    if not raw.get("latitude") or not raw.get("longitude"):
        return None
    if "delete_filia" in f"{raw.get('addressFull')} {raw.get('cityFull')}":
        return None
    return StoreRec(
        id=raw["branchId"],
        source="silpo",
        chain="silpo",
        name=f"Сільпо №{raw.get('externalId')}",
        city=raw.get("cityFull") or None,
        address=raw.get("addressFull"),
        lat=float(raw["latitude"]),
        lng=float(raw["longitude"]),
        has_pickup=bool(raw.get("hasPickup")),
    )


async def fetch_branches(http: Http, city: str | None) -> list[StoreRec]:
    branches: list[StoreRec] = []
    offset, total = 0, None
    while total is None or offset < total:
        data = await http.get_json(f"{BASE_URL}/branches", params={"limit": 100, "offset": offset})
        items = data.get("items") or []
        if not items:
            break
        total = data.get("total") or 0
        offset += len(items)
        branches.extend(b for b in map(parse_branch, items) if b)
    return [b for b in branches if city is None or b.city == city]


async def search(http: Http, branch_id: str, category: Category) -> list[dict]:
    data = await http.get_json(
        f"{BASE_URL}/branches/{branch_id}/products",
        params={
            "limit": PAGE_SIZE,
            "offset": 0,
            "deliveryType": "DeliveryHome",
            "search": category.query,
            "includeChildCategories": "true",
            "sortBy": "productsList",
            "sortDirection": "desc",
        },
    )
    return data.get("items") or []


def parse_detail(raw: dict) -> SilpoDetail:
    gtin, alt_gtins = pick_gtins(raw.get("barcodes") or [])
    groups = {g.get("key"): g.get("attributes") or [] for g in raw.get("attributeGroups") or []}
    texts = [
        str((attr.get("value") or {}).get("title") or "")
        for key in ("ingredients", "composition")
        for attr in groups.get(key, [])
    ]
    nutrition = {
        (attr.get("attribute") or {}).get("title") or "": (attr.get("value") or {}).get("title")
        for attr in groups.get("nutrient", [])
    }
    return SilpoDetail(
        gtin=gtin,
        alt_gtins=alt_gtins,
        ingredients=strip_html(" ".join(t for t in texts if t)) or None,
        nutrition=nutrition or None,
    )


async def fetch_detail(http: Http, slug: str) -> SilpoDetail | None:
    try:
        return parse_detail(await http.get_json(f"{BASE_URL}/branches/{DEFAULT_BRANCH}/products/{slug}"))
    except httpx.HTTPError:
        return None


def parse_item(
    item: dict, branch_id: str, category: Category, detail: SilpoDetail | None
) -> tuple[ProductRec, OfferRec] | None:
    base_title = item.get("title") or ""
    slug = item.get("slug")
    if not slug or not category.matches(base_title):
        return None
    if item.get("weighted") or item.get("ratio") == "кг":
        # Ваговий: `price` — за кг, а displayPrice — за 100 г (displayRatio "100г").
        price = money(item.get("price") or 0)
        old = item.get("oldPrice")
        pack_qty, pack_unit, title = Decimal(1000), "g", base_title
    else:
        price = money(item.get("displayPrice") or item.get("price") or 0)
        old = item.get("displayOldPrice")
        pack_qty, pack_unit = parse_pack(item.get("displayRatio"))
        title = f"{base_title} {item.get('displayRatio') or ''}".strip()
    if price <= 0 or not pack_qty or not pack_unit:
        return None
    old_price = money(old) if old else None
    if old_price is not None and old_price <= price:
        old_price = None

    gtin = detail.gtin if detail else None
    ingredients = detail.ingredients if detail else None
    brand = item.get("brandTitle")
    product = ProductRec(
        source="silpo",
        gtin=gtin,
        source_key=None if gtin else f"silpo:{slug}",
        title=title,
        category=category.key,
        pack_qty=pack_qty,
        pack_unit=pack_unit,
        brand=brand,
        alt_gtins=list(detail.alt_gtins) if detail else [],
        fat_pct=parse_fat(title),
        ingredients=ingredients,
        composition_known=bool(ingredients),
        tags=build_tags(category.key, title, brand, ingredients),
        nutrition=detail.nutrition if detail else None,
        img_url=IMG_URL.format(icon=item["icon"]) if item.get("icon") else None,
    )
    stock = item.get("stock")
    offer = OfferRec(
        store_id=branch_id,
        source_sku=slug,
        product_key=product.key,
        title_raw=title,
        source_category=item.get("sectionSlug"),
        price=price,
        old_price=old_price,
        promo_percent=round((1 - price / old_price) * 100) if old_price else None,
        promo_until=None,
        unit_price=unit_price(price, pack_qty, pack_unit),
        in_stock=bool(stock and stock > 0),
        stock=int(stock) if stock is not None else None,
        url=f"https://silpo.ua/product/{slug}",
    )
    return product, offer


async def fetch_branch_items(http: Http, branch_id: str, categories: list[Category]) -> tuple[list[tuple], int]:
    """Сирі товари філії: [(category, item)] з відсіяним «не тим» і кількість категорій з помилкою."""
    results = await asyncio.gather(*(search(http, branch_id, c) for c in categories), return_exceptions=True)
    items = [
        (cat, item)
        for cat, res in zip(categories, results, strict=True)
        if not isinstance(res, BaseException)
        for item in res
        if item.get("slug") and cat.matches(item.get("title") or "")
    ]
    return items, sum(isinstance(res, BaseException) for res in results)
