"""Парсери відповідей API на скорочених реальних прикладах (2026-11-21), без мережі й БД."""

from datetime import date
from decimal import Decimal

from app.catalog.etl import silpo, zakaz
from app.catalog.etl.categories import BY_KEY
from app.catalog.etl.records import merge_products

ZAKAZ_MILK = {
    "ean": "04820222760249",
    "eans": ["04820222760249"],
    "title": "Молоко Галичина ультрапастеризоване 2,5% 950г",
    "price": 7499,
    "discount": {"status": False, "value": 0, "old_price": 7499, "due_date": None},
    "unit": "pcs",
    "weight": 950.0,
    "category_id": "uht-milk",
    "in_stock": True,
    "ingredients": ["Молоко коров'яче незбиране, молоко коров'яче знежирене.<br>"],
    "nutrition_facts": {"ingredient_sugars": "4.70г"},
    "fat": "2.5%",
    "producer": {"trademark": "Галичина"},
    "img": {"s350x350": "https://img3.zakaz.ua/x-s350x350.jpg"},
    "web_url": "https://novus.zakaz.ua/uk/products/moloko--04820222760249/",
}

ZAKAZ_PROMO_COFFEE = {
    "ean": "08711000572092",
    "title": "Кава мелена Jacobs Kronung Espresso 200г",
    "price": 3399,
    "discount": {"status": True, "value": 90, "old_price": 33900, "due_date": "2026-11-29"},
    "unit": "pcs",
    "weight": 200.0,
    "in_stock": True,
    "ingredients": [],
    "producer": {"trademark": "Jacobs"},
}

ZAKAZ_LOOSE_BANANA = {
    "ean": "auchan02202760000000",
    "title": "Банан",
    "price": 6990,
    "discount": {"status": False},
    "unit": "kg",
    "weight": None,
    "in_stock": True,
    "ingredients": [],
    "producer": {"trademark": None},
}

SILPO_CURD = {
    "title": "Сир кисломолочний Яготинський 5%",
    "slug": "syr-kyslomolochnyi-yagotynskyi-5-802382",
    "price": 114,
    "displayPrice": 114,
    "displayOldPrice": None,
    "displayRatio": "350г",
    "ratio": "шт",
    "weighted": False,
    "stock": 22,
    "brandTitle": "Яготинське",
    "icon": "95fbf05c.png",
    "sectionSlug": "syr-kyslomolochnyi-4988",
}

SILPO_BANANA = {
    "title": "Банан",
    "slug": "banan-1",
    "price": 87.35,
    "displayPrice": 8.74,
    "displayRatio": "100г",
    "ratio": "кг",
    "weighted": True,
    "stock": 185.2,
    "brandTitle": None,
}


def test_zakaz_item_to_product_and_offer():
    product, offer = zakaz.parse_item(ZAKAZ_MILK, "482010105", BY_KEY["milk"])
    assert product.gtin == "4820222760249"
    assert (product.pack_qty, product.pack_unit) == (Decimal(950), "g")
    assert product.composition_known and product.tags == ["lactose"]
    assert offer.price == Decimal("74.99") and offer.unit_price == Decimal("78.94")
    assert offer.old_price is None and offer.promo_percent is None


def test_zakaz_promo_is_kept():
    _, offer = zakaz.parse_item(ZAKAZ_PROMO_COFFEE, "482010105", BY_KEY["coffee_ground"])
    assert (offer.price, offer.old_price) == (Decimal("33.99"), Decimal("339.00"))
    assert (offer.promo_percent, offer.promo_until) == (90, date(2026, 11, 29))


def test_zakaz_loose_item_is_priced_per_kg_and_keyed_without_gtin():
    product, offer = zakaz.parse_item(ZAKAZ_LOOSE_BANANA, "48246401", BY_KEY["bananas"])
    assert product.gtin is None and product.key == "zakaz:auchan02202760000000"
    assert offer.unit_price == Decimal("69.90")


def test_zakaz_item_outside_category_is_skipped():
    assert zakaz.parse_item(ZAKAZ_MILK, "482010105", BY_KEY["curd"]) is None


def test_silpo_item_with_card_gets_gtin_and_pack_from_display_ratio():
    detail = silpo.parse_detail(
        {
            "barcodes": ["4823005207719", "0250014097576"],
            "attributeGroups": [{"key": "ingredients", "attributes": []}],
        }
    )
    product, offer = silpo.parse_item(SILPO_CURD, "branch-1", BY_KEY["curd"], detail)
    assert product.gtin == "4823005207719"
    assert product.title == "Сир кисломолочний Яготинський 5% 350г"
    assert not product.composition_known  # склад у Сільпо порожній: невідомо, а не «чисто»
    assert offer.unit_price == Decimal("325.71") and offer.stock == 22


def test_silpo_weighted_item_uses_price_per_kg():
    product, offer = silpo.parse_item(SILPO_BANANA, "branch-1", BY_KEY["bananas"], None)
    assert offer.price == Decimal("87.35") and offer.unit_price == Decimal("87.35")
    assert product.key == "silpo:banan-1"


def test_merge_takes_composition_from_zakaz_and_title_with_weight():
    zakaz_product, _ = zakaz.parse_item(ZAKAZ_MILK, "482010105", BY_KEY["milk"])
    silpo_item = {**SILPO_CURD, "title": "Молоко «Галичина» ультрапастеризоване 2,5%", "displayRatio": "950г"}
    silpo_product, _ = silpo.parse_item(silpo_item, "branch-1", BY_KEY["milk"], silpo.SilpoDetail(gtin="4820222760249"))
    [merged] = merge_products([silpo_product, zakaz_product])
    assert merged.title == "Молоко Галичина ультрапастеризоване 2,5% 950г"
    assert merged.composition_known and merged.ingredients.startswith("Молоко коров'яче")


def test_store_parsers():
    store = zakaz.parse_store(
        {
            "id": "48246401",
            "name": "Auchan Почайна DRIVE",
            "retail_chain": "auchan",
            "city": "kiev",
            "is_active": True,
            "address": {"street": "Степана Бандери", "building": "15А", "coords": {"lat": 50.48, "lng": 30.49}},
            "delivery_types": ["pickup", "plan"],
        }
    )
    assert (store.city, store.address, store.has_pickup) == ("Київ", "Степана Бандери, 15А", True)
    assert zakaz.parse_store({"id": "1", "retail_chain": "winetime", "is_active": True}) is None

    branch = silpo.parse_branch(
        {
            "branchId": "1ed43e73",
            "externalId": "1998",
            "cityFull": "Київ",
            "addressFull": "просп. Володимира Івасюка, 46",
            "latitude": "50.5202200000000000",
            "longitude": "30.5145200000000000",
            "hasPickup": True,
        }
    )
    assert (branch.name, branch.lat) == ("Сільпо №1998", 50.52022)
    assert silpo.parse_branch({"branchId": "x", "latitude": None, "longitude": None}) is None


def test_gtin_index_matches_silpo_and_zakaz_by_any_barcode():
    from app.catalog.etl.records import GtinIndex

    index = GtinIndex()
    index.add("4820222760249", [])  # молоко «Галичина» зі Zakaz
    detail = silpo.parse_detail(
        {"barcodes": ["0250012506247", "0250014744623", "14820222760246", "4820222760386", "4820222760249"]}
    )
    assert detail.gtin == "4820222760386"  # Сільпо вважає основним інший код
    silpo_item = {**SILPO_CURD, "title": "Молоко «Галичина» ультрапастеризоване 2,5%", "displayRatio": "950г"}
    product, _ = silpo.parse_item(silpo_item, "branch-1", BY_KEY["milk"], detail)
    index.resolve(product)
    assert product.gtin == "4820222760249"
    assert "4820222760386" in product.alt_gtins


def test_gtin_index_ignores_store_internal_codes():
    from app.catalog.etl.records import GtinIndex, ProductRec

    index = GtinIndex()
    index.add("4820000000001", ["0250012506247"])
    other = ProductRec(
        source="silpo",
        gtin="4820000000002",
        source_key=None,
        title="Інший товар",
        category="milk",
        pack_qty=Decimal(1),
        pack_unit="pcs",
        alt_gtins=["0250012506247"],
    )
    index.resolve(other)
    assert other.gtin == "4820000000002"  # внутрішній код 02… не склеює різні товари
