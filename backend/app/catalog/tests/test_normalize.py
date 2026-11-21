from decimal import Decimal

import pytest

from app.catalog.etl.categories import BY_KEY
from app.catalog.etl.normalize import (
    build_tags,
    composition_tags,
    kopecks,
    norm_gtin,
    parse_fat,
    parse_pack,
    pick_gtins,
    unit_price,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Молоко Галичина ультрапастеризоване 2,5% 950г", (Decimal(950), "g")),
        ("Борошно пшеничне Хуторок 1,5 кг", (Decimal(1500), "g")),
        ("Сік 0.9 л", (Decimal(900), "ml")),
        ("Йогурт 2х200г", (Decimal(400), "g")),
        ("Яйця курячі Квочка С1 10шт", (Decimal(10), "pcs")),
        ("6шт/уп", (Decimal(6), "pcs")),
        ("Сир кисломолочний для дітей від 6-ти місяців 4,5% 90г", (Decimal(90), "g")),
        ("Кава мелена Jacobs", (None, None)),
    ],
)
def test_parse_pack(text, expected):
    assert parse_pack(text) == expected


def test_gtin_normalization_matches_zakaz_and_silpo():
    assert norm_gtin("04820222760249") == "4820222760249"  # Zakaz, 14 цифр
    assert norm_gtin("4820222760249") == "4820222760249"  # Сільпо
    assert norm_gtin("auchan02202760000000") is None  # ваговий товар Auchan


def test_pick_gtins_skips_store_internal_codes():
    primary, alts = pick_gtins(["0250012506247", "14820222760246", "4820222760249"])
    assert primary == "4820222760249"
    assert set(alts) == {"0250012506247", "14820222760246"}


def test_unit_price_catches_shrinkflation():
    # 870 г за 68.99 дешевше на полиці, але дорожче за кг, ніж 950 г за 74.99
    assert unit_price(Decimal("68.99"), Decimal(870), "g") == Decimal("79.30")
    assert unit_price(Decimal("74.99"), Decimal(950), "g") == Decimal("78.94")
    assert unit_price(Decimal("63.99"), Decimal(10), "pcs") == Decimal("6.40")


def test_kopecks():
    assert kopecks(7499) == Decimal("74.99")


def test_parse_fat():
    assert parse_fat("Молоко 2,5% 950г") == Decimal("2.5")
    assert parse_fat("Кава", "9%") == Decimal(9)


@pytest.mark.parametrize(
    ("ingredients", "tags"),
    [
        ("Молоко коров'яче незбиране, молоко коров'яче знежирене.", []),
        ("Сир кисломолочний, цукор, ванілін", ["sugar"]),
        ("Йогурт без доданого цукру, закваска", []),
        ("Глазур: олія пальмова, какао", ["palm_oil"]),
        ("Молоко нормалізоване, замінник молочного жиру", ["palm_oil"]),
    ],
)
def test_composition_tags(ingredients, tags):
    assert composition_tags(ingredients) == tags


def test_build_tags_lactose_and_private_label():
    assert build_tags("milk", "Молоко Галичина 2,5%", "Галичина", "") == ["lactose"]
    assert build_tags("milk", "Молоко безлактозне 2,5%", "Галичина", "") == []
    assert build_tags("flour", "Борошно Auchan", "Auchan", "борошно пшеничне") == ["private_label"]


@pytest.mark.parametrize(
    ("category", "title", "ok"),
    [
        ("curd", "Сир кисломолочний Біло 5% 350г", True),
        ("curd", "Сир кисломолочний «Молокія» 5%", True),
        ("curd", "Сир кисломолочний President зі сметаною та курагою 9% 180г", False),
        ("curd", "Сир кисломолочний Яготинське для дітей від 6-ти місяців 4,5% 90г", False),
        ("coffee_ground", "Кава мелена Fort 250г", True),
        ("coffee_ground", "Кава мелена Кава Старого Львова Марципанова 250г", False),
        ("coffee_ground", "Кава мелена Auchan без кофеїну 250г", False),
        ("milk", "Молоко «Галичина» ультрапастеризоване 2,5%", True),
        ("milk", "Молоко кокосове Aroy-D 400мл", False),
        ("eggs", "Яйця курячі Квочка С1 10шт", True),
        ("eggs", "Яйця курячі Свіжак С2 10шт", False),
        ("bananas", "Банан", True),
        ("bananas", "Банан Auchan сушений 100г", False),
    ],
)
def test_category_rules(category, title, ok):
    assert BY_KEY[category].matches(title) is ok
