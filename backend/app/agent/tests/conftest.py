"""Тести агента без БД, мережі й LLM: каталог і geo підміняються реальними даними з mocks/."""

import json
from pathlib import Path

import pytest

from app.agent.service import CHAIN_NAMES
from app.catalog import service as catalog_service
from app.catalog.schemas import PriceSearchOut, ProductPricesOut, StoreOut
from app.config import get_settings
from app.geo import service as geo_service
from app.geo.distance import haversine_km

MOCKS = Path(__file__).resolve().parents[4] / "mocks"
PRICE_MOCKS = [
    "03_prices_milk_galychyna_by_stores.json",
    "04_prices_curd_no_sugar_no_palm.json",
    "05_prices_eggs_repeated_store_ids.json",
    "06_prices_coffee_jacobs_all_stores.json",
]
# Точка між Сільпо на Берковецькій і NOVUS на Виноградарі — обидва мають ціни на всі 4 товари з моків
USER_LAT, USER_LNG = 50.48, 30.40


def _load(name: str) -> dict:
    return json.loads((MOCKS / name).read_text())["response"]


STORES = [StoreOut.model_validate(s) for s in _load("01_stores_kyiv.json")]
PRODUCTS = [ProductPricesOut.model_validate(p) for name in PRICE_MOCKS for p in _load(name)["products"]]


async def fake_list_stores(session, city=None, chain=None, with_prices=True):
    return STORES


async def fake_search_prices(session, query, store_ids=None, category=None, exclude=None, in_stock_only=True, limit=20):
    """Спрощена копія поведінки каталогу: категорія або перше слово назви, фільтр складу, лише запитані магазини."""
    words = query.lower().split()
    if not words:
        raise ValueError("query has no searchable words")
    out = []
    for p in PRODUCTS:
        if category and p.category != category:
            continue
        if not category and not p.title.lower().startswith(words[0][:4]):
            continue
        if exclude and (set(p.tags) & set(exclude) or not p.composition_known):
            continue
        prices = [pr for pr in p.prices if not store_ids or pr.store_id in store_ids]
        if prices:
            out.append(p.model_copy(update={"prices": prices}))
    return PriceSearchOut(query=query, tokens=words, store_ids=store_ids or [], missing_store_ids=[], products=out)


async def fake_find_nearby(lat, lng, mode="walk", radius_km=None, store_ids=None, client=None):
    """Форма відповіді geo.find_nearby без мережі (Valhalla): пряма × 1.3, усі магазини з моків мають ціни."""
    radius = radius_km or {"walk": 2.0, "car": 10.0}[mode]
    speed = {"walk": 5, "car": 25}[mode]
    items = []
    for st in STORES:
        straight = haversine_km(lat, lng, st.lat, st.lng)
        km = round(straight * 1.3, 2)
        items.append({
            "store_id": st.store_id, "source": st.source, "chain": st.chain,
            "chain_name": CHAIN_NAMES.get(st.chain, st.chain),
            "name": st.name, "city": st.city, "address": st.address, "lat": st.lat, "lng": st.lng,
            "alt_store_ids": [], "has_online_prices": True, "in_radius": straight <= radius,
            "distance_km": km, "duration_min": round(km / speed * 60, 1), "estimated": True,
            "maps_urls": {"walking": "https://maps/w", "driving": "https://maps/d", "transit": "https://maps/t"},
        })  # fmt: skip
    items.sort(key=lambda x: x["duration_min"])
    return {"radius_km": radius, "radius_expanded": False, "stores": items}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Без ключів LLM (парсер на правилах), з каталогом і geo на даних із mocks/."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(catalog_service, "list_stores", fake_list_stores)
    monkeypatch.setattr(catalog_service, "search_prices", fake_search_prices)
    monkeypatch.setattr(geo_service, "find_nearby", fake_find_nearby)
    yield
    get_settings.cache_clear()
