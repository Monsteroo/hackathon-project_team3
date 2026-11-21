from decimal import Decimal

from httpx import ASGITransport, AsyncClient

from app.agent import service
from app.agent.optimizer import Candidate, make_line
from app.agent.parser import parse_rules
from app.agent.schemas import BasketIn, Constraints, RequestedItem
from app.agent.tests.conftest import PRODUCTS, STORES, USER_LAT, USER_LNG
from app.db import get_session
from app.main import app

TEXT = "молоко, кисломолочний сир, яйця і кава, поїду на авто в радіусі 10 км"


# ---------- Parse (правила) ----------
def test_rules_parser_extracts_items_and_constraints():
    p = parse_rules("молоко і каву без цукру до 300 грн в Сільпо, далеко не хочу")
    assert [(i.name, i.category) for i in p.items] == [("молоко", "milk"), ("кава", "coffee_ground")]
    c = p.constraints
    assert (c.budget_uah, c.exclude, c.radius_km, c.preferred_chains) == (300, ["sugar"], 1.0, ["silpo"])


# ---------- Optimize ----------
def test_shrinkflation_pack_counts_as_one_with_note():
    milk = next(p for p in PRODUCTS if p.category == "milk" and p.pack_qty and p.pack_qty < 1000)
    item = RequestedItem(name="молоко", search_query="молоко", category="milk", quantity=1000, unit="ml")
    line = make_line(item, Candidate(item="молоко", product=milk, price=milk.prices[0]))
    assert line.packs == 1
    assert line.note.startswith("Менша пачка: 950 г замість 1000 мл")
    assert line.line_total == milk.prices[0].price


def test_pick_nearby_respects_radius_and_chains():
    near = service.pick_nearby(STORES, USER_LAT, USER_LNG, Constraints(radius_km=3), per_chain=2)
    assert near and all(s.distance_km <= 3 for s in near)
    assert near == sorted(near, key=lambda s: s.duration_min)
    only_silpo = service.pick_nearby(
        STORES, USER_LAT, USER_LNG, Constraints(radius_km=10, preferred_chains=["silpo"]), 5
    )
    assert only_silpo and {s.chain for s in only_silpo} == {"silpo"}


# ---------- Повний пайплайн на реальних цінах із mocks/ ----------
async def test_build_returns_baskets_with_real_prices():
    out = await service.build(None, BasketIn(text=TEXT, lat=USER_LAT, lng=USER_LNG))
    assert out.parser == "rules"
    assert 1 <= len(out.baskets) <= 3
    assert out.baskets[0].type == "nearest"
    for b in out.baskets:
        assert b.total == sum(line.line_total for line in b.lines)
        assert b.saving >= 0
        assert {line.store_id for line in b.lines} <= {s.store_id for s in b.stores}
    assert any(not b.missing for b in out.baskets), "хоч один кошик має бути повним"
    assert "грн" in out.explanation


async def test_exclude_sugar_filters_unknown_composition():
    out = await service.build(None, BasketIn(text=f"{TEXT}, без цукру", lat=USER_LAT, lng=USER_LNG))
    for b in out.baskets:
        assert all("sugar" not in line.tags for line in b.lines)


async def test_no_stores_in_radius():
    out = await service.build(None, BasketIn(text="кава в радіусі 0.1 км", lat=50.0, lng=36.0))  # Харків
    assert out.baskets == [] and out.stores_considered == 0
    assert out.warnings


async def test_empty_radius_offers_nearest_priced_store_with_warning():
    out = await service.build(None, BasketIn(text="кава в радіусі 0.1 км", lat=USER_LAT, lng=USER_LNG))
    assert out.baskets
    assert any("немає магазинів з цінами" in w for w in out.warnings)


# ---------- HTTP ----------
async def _post(path: str, body: dict, key: str | None = "test-api-key"):
    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    try:
        headers = {"X-API-Key": key} if key else {}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
            return await client.post(path, json=body)
    finally:
        app.dependency_overrides.clear()


async def test_http_basket_and_parse():
    r = await _post("/agent/basket", {"text": TEXT, "lat": USER_LAT, "lng": USER_LNG})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data["baskets"][0]["total"], float)  # Money → число в JSON
    r = await _post("/agent/parse", {"text": "літр молока"})
    assert r.status_code == 200 and r.json()["items"][0]["category"] == "milk"


async def test_http_requires_api_key_and_products():
    assert (await _post("/agent/parse", {"text": "молоко"}, key=None)).status_code == 401
    r = await _post("/agent/basket", {"text": "привіт", "lat": USER_LAT, "lng": USER_LNG})
    assert r.status_code == 422 and r.json()["detail"] == "no products found in the request"


def test_money_is_decimal():
    assert isinstance(PRODUCTS[0].prices[0].price, Decimal)


def test_search_attempts_go_from_exact_to_general():
    bananas = RequestedItem(name="банани", search_query="банани", category="bananas", quantity=1000, unit="g")
    assert service.search_attempts(bananas) == [
        ("бана", "bananas"),  # і «Банан», і «Банани в сиропі» — дешевший за кг обере оптимізатор
        ("банани", "bananas"),
        ("банан", "bananas"),
        ("бана", None),
    ]
    milk = RequestedItem(
        name="молоко", search_query="молоко", category="milk", quantity=1, unit="pcs", brand="Галичина"
    )
    assert ("молоко", "milk") not in service.search_attempts(milk), "бренд не можна відкидати"


# ---------- Інтеграція з voice і geo ----------
async def test_voice_mode_and_radius_override_parsed_text():
    """mode/radius_km з VoiceResult головніші за те, що агент розібрав з тексту."""
    out = await service.build(
        None, BasketIn(text="молоко і кава", lat=USER_LAT, lng=USER_LNG, mode="car", radius_km=10)
    )
    assert out.parsed.constraints.travel_mode == "car"
    assert out.parsed.constraints.radius_km == 10
    assert out.baskets and all(s.maps_url == "https://maps/d" for b in out.baskets for s in b.stores)


async def test_geo_failure_falls_back_to_catalog_coordinates(monkeypatch):
    from app.geo import service as geo_service

    async def broken(*args, **kwargs):
        raise RuntimeError("valhalla down")

    monkeypatch.setattr(geo_service, "find_nearby", broken)
    out = await service.build(None, BasketIn(text=TEXT, lat=USER_LAT, lng=USER_LNG))
    assert out.baskets
    assert any("за прямою" in w for w in out.warnings)


async def test_alt_store_ids_prices_go_to_primary_store(monkeypatch):
    """Ціна з іншої філії в тій самій будівлі приписується магазину, який показуємо користувачу."""
    from app.agent.schemas import StoreNearby

    silpo = "1edb6b13-defd-6bb8-a1c4-87d073549907"
    store = StoreNearby(
        store_id="primary-id", alt_store_ids=[silpo], chain="silpo", name="Сільпо", lat=USER_LAT, lng=USER_LNG,
        distance_km=1, duration_min=10, maps_url="x",
    )  # fmt: skip
    item = RequestedItem(name="кава", search_query="кава", category="coffee_ground", quantity=1, unit="pcs")
    candidates, _ = await service.find_candidates(None, [item], [store], [])
    assert candidates["кава"] and {c.price.store_id for c in candidates["кава"]} == {"primary-id"}


def test_search_without_category_requires_title_to_start_with_query():
    """«зелень (кріп, петрушка)» не має знаходити «Сир … з зеленою цибулею»."""
    assert not service.title_starts_with("Сир Piatnica сметанковий з зеленою цибулею 150г", "зелень (кріп, петрушка)")
    assert not service.title_starts_with("Чіпси Lay's зі смаком картоплі", "картопля")
    assert service.title_starts_with("Картопля молода, кг", "картопля")
    assert service.title_starts_with("Банан", "банани")
    assert service.title_starts_with("Яйця курячі Квочка С1 10шт", "яйця курячі")


# ---------- Список з екрана 2 (items) ----------
async def test_basket_from_confirmed_items_skips_llm():
    body = BasketIn(
        items=[
            {"category": "milk", "need": 1000, "unit": "ml", "exclude": ["sugar"]},
            {"label": "Кава Jacobs", "query": "кава jacobs", "need": 1, "unit": "pcs"},
            {"category": "eggs", "need": 10, "unit": "pcs"},
        ],
        budget_uah=500,
        lat=USER_LAT,
        lng=USER_LNG,
        mode="car",
        radius_km=10,
    )
    out = await service.build(None, body)
    assert out.parser == "items"
    assert [i.name for i in out.parsed.items] == ["молоко", "Кава Jacobs", "яйця"]
    assert out.parsed.constraints.budget_uah == 500
    assert out.parsed.constraints.travel_mode == "car"
    assert out.baskets and any(not b.missing for b in out.baskets)


def test_basket_needs_text_or_items():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BasketIn(lat=USER_LAT, lng=USER_LNG)
    assert BasketIn(text="молоко", lat=USER_LAT, lng=USER_LNG).items is None


def test_duplicate_labels_get_unique_names():
    body = BasketIn(
        items=[{"label": "Молоко", "category": "milk", "need": 1, "unit": "pcs"}] * 2, lat=USER_LAT, lng=USER_LNG
    )
    assert [i.name for i in service.parsed_from_items(body).items] == ["Молоко", "Молоко (2)"]
