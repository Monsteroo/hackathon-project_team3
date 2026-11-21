"""Проміжні записи ETL: те, що парсери віддають завантажувачу. Не залежать від БД."""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from app.catalog.etl.normalize import COMPOSITION_TAGS, is_internal_code


@dataclass
class StoreRec:
    id: str
    source: str
    chain: str
    name: str
    city: str | None
    address: str | None
    lat: float | None
    lng: float | None
    has_pickup: bool
    is_active: bool = True


@dataclass
class ProductRec:
    source: str
    gtin: str | None
    source_key: str | None  # запасний ідентифікатор, коли публічного GTIN немає ("zakaz:<ean>", "silpo:<slug>")
    title: str
    category: str
    pack_qty: Decimal
    pack_unit: str
    brand: str | None = None
    alt_gtins: list[str] = field(default_factory=list)
    fat_pct: Decimal | None = None
    ingredients: str | None = None
    composition_known: bool = False
    tags: list[str] = field(default_factory=list)
    nutrition: dict | None = None
    img_url: str | None = None

    @property
    def key(self) -> str:
        return self.gtin or self.source_key or ""


@dataclass
class OfferRec:
    store_id: str
    source_sku: str
    product_key: str
    title_raw: str
    source_category: str | None
    price: Decimal
    old_price: Decimal | None
    promo_percent: int | None
    promo_until: date | None
    unit_price: Decimal | None
    in_stock: bool
    stock: int | None
    url: str | None


def merge_products(records: list[ProductRec]) -> list[ProductRec]:
    """Зводить записи одного товару (той самий GTIN з різних мереж) в один.

    Склад береться з того джерела, де він відомий (зазвичай Zakaz), а назва — із Zakaz, бо в ній є вага.
    """
    merged: dict[str, ProductRec] = {}
    for rec in records:
        if not rec.key:
            continue
        cur = merged.get(rec.key)
        if cur is None:
            merged[rec.key] = replace(rec, alt_gtins=list(rec.alt_gtins), tags=list(rec.tags))
            continue
        if rec.source == "zakaz" and cur.source != "zakaz":
            cur.title, cur.source = rec.title, rec.source
        structural = (set(cur.tags) | set(rec.tags)) - COMPOSITION_TAGS
        if rec.composition_known and not cur.composition_known:
            cur.ingredients, cur.composition_known = rec.ingredients, True
            cur.nutrition = rec.nutrition or cur.nutrition
            cur.tags = sorted(structural | (set(rec.tags) & COMPOSITION_TAGS))
        else:
            cur.tags = sorted(structural | (set(cur.tags) & COMPOSITION_TAGS))
        cur.alt_gtins = sorted((set(cur.alt_gtins) | set(rec.alt_gtins)) - {cur.gtin})
        for name in ("brand", "img_url", "fat_pct", "nutrition"):
            if getattr(cur, name) is None:
                setattr(cur, name, getattr(rec, name))
    return list(merged.values())


class GtinIndex:
    """Будь-який публічний штрихкод товару -> канонічний GTIN товару в БД.

    Мережі знають той самий товар під різними кодами: Сільпо віддає для молока «Галичина» 5 штрихкодів
    і може вважати основним `4820222760386`, а Zakaz знає лише `4820222760249`. Без індексу це два різні
    товари, і порівняння цін між мережами для них не працює.
    """

    def __init__(self) -> None:
        self._codes: dict[str, tuple[int, str]] = {}
        self._next_rank = 0

    def add(self, gtin: str, alt_gtins: list[str]) -> None:
        """Додає товар. Перший доданий має пріоритет, тож спершу додавай кращі (зі складом, з більшою кількістю цін)."""
        rank = self._next_rank
        self._next_rank += 1
        for code in (gtin, *alt_gtins):
            if code and not is_internal_code(code) and code not in self._codes:
                self._codes[code] = (rank, gtin)

    def resolve(self, product: ProductRec) -> ProductRec:
        """Переводить товар на канонічний GTIN, якщо будь-який із його кодів уже відомий."""
        if not product.gtin:
            return product
        codes = [product.gtin, *product.alt_gtins]
        hits = [self._codes[c] for c in codes if c in self._codes]
        if hits:
            canonical = min(hits)[1]
            if canonical != product.gtin:
                product.gtin = canonical
                product.alt_gtins = sorted(set(codes) - {canonical})
        return product
