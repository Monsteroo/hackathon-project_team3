import pytest
from httpx import ASGITransport, AsyncClient

from app.geo import service
from app.main import app

ORIGIN = (50.4500, 30.5200)


def store(id_, lat, lng, online=True, alt=()):
    source = id_.split(":")[0]
    return {
        "id": id_,
        "source": source,
        "alt_ids": list(alt),
        "chain": "novus",
        "chain_name": "NOVUS",
        "name": id_,
        "city": "Київ",
        "address": "",
        "lat": lat,
        "lng": lng,
        "place_id": f"{lat},{lng}",
        "has_online_prices": online,
        "offers_count": 100 if online else 0,
        "online_catalog": online,
        "has_pickup": online,
    }


STORES = (
    store("osm:n1", 50.4510, 30.5200, online=False),  # ~0.1 км, без цін
    store("zakaz:1", 50.4560, 30.5200),  # ~0.7 км
    store(
        "silpo:aaaaaaaa-0000-0000-0000-000000000001",
        50.4600,
        30.5200,
        alt=["silpo:aaaaaaaa-0000-0000-0000-000000000002"],
    ),  # ~1.1 км
    store("zakaz:9", 50.5200, 30.5200),  # ~7.8 км
)
SILPO_A = "aaaaaaaa-0000-0000-0000-000000000001"
SILPO_ALT = "aaaaaaaa-0000-0000-0000-000000000002"


@pytest.fixture
def fake_data(monkeypatch):
    monkeypatch.setattr(service, "load_stores", lambda: STORES)

    async def fake_matrix(origin, targets, mode, client=None):
        # час пропорційний відстані по прямій: детерміновано, без мережі
        return [
            {
                "distance_km": round(service.haversine_km(*origin, *t), 2),
                "duration_min": round(service.haversine_km(*origin, *t) * 12, 1),
                "estimated": False,
            }
            for t in targets
        ]

    monkeypatch.setattr(service, "travel_matrix", fake_matrix)


async def api_get(path, params):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "test-api-key"}
    ) as c:
        return await c.get(path, params=params)


async def test_default_walk_radius_and_recommend_nearest_online(fake_data):
    r = await service.find_nearby(*ORIGIN)
    assert r["radius_km"] == 2.0 and not r["radius_expanded"]
    # у радіусі — 3; плюс магазин з цінами поза радіусом (in_radius=False), щоб було куди вести маршрут
    assert [(s["store_id"], s["in_radius"]) for s in r["stores"]] == [
        ("osm:n1", True),
        ("1", True),
        (SILPO_A, True),
        ("9", False),
    ]
    assert r["recommended_store_id"] == "1"  # найближчий osm без цін пропускаємо
    assert r["recommended_reason"] == "nearest_with_online_prices"
    assert r["stores"][2]["alt_store_ids"] == [SILPO_ALT] and r["stores"][2]["source"] == "silpo"


async def test_confirmed_store_ids_win_even_outside_radius(fake_data):
    r = await service.find_nearby(*ORIGIN, store_ids=["9"])
    assert r["recommended_store_id"] == "9" and r["recommended_reason"] == "confirmed_offer"
    far = next(s for s in r["stores"] if s["store_id"] == "9")
    assert far["confirmed"] and not far["in_radius"]


@pytest.mark.parametrize("ids", [["zakaz:1"], ["1"]])
async def test_both_id_formats_accepted(fake_data, ids):
    r = await service.find_nearby(*ORIGIN, store_ids=ids)
    assert r["recommended_store_id"] == "1" and r["unknown_store_ids"] == []


async def test_confirmed_matches_alt_ids(fake_data):
    r = await service.find_nearby(*ORIGIN, store_ids=[SILPO_ALT])
    assert r["recommended_store_id"] == SILPO_A


async def test_all_unknown_ids_behave_like_no_ids(fake_data):
    r = await service.find_nearby(*ORIGIN, store_ids=["999999", "nope"])
    assert r["recommended_reason"] == "nearest_with_online_prices" and r["recommended_store_id"] == "1"
    assert r["unknown_store_ids"] == ["999999", "nope"]
    assert not any(s["confirmed"] for s in r["stores"])


async def test_radius_expands_when_empty(fake_data):
    r = await service.find_nearby(50.6000, 30.5200, mode="walk")  # ~9 км від найближчого
    assert r["radius_expanded"] and r["radius_km"] == 16.0 and r["count"] >= 1


async def test_car_default_radius(fake_data):
    r = await service.find_nearby(*ORIGIN, mode="car")
    assert r["radius_km"] == 10.0 and r["count"] == 4


@pytest.mark.parametrize(
    "raw,norm",
    [
        ("48201031", "zakaz:48201031"),
        ("zakaz:48201031", "zakaz:48201031"),
        (" 1EDB6B12-C559-61CC-B8C3-EB10F39E9FE0 ", "silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0"),
        ("osm:n123", "osm:n123"),
    ],
)
def test_normalize_store_id(raw, norm):
    assert service.normalize_store_id(raw) == norm


@pytest.mark.parametrize(
    "internal,public",
    [
        ("zakaz:482010105", "482010105"),
        ("silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0", "1edb6b12-c559-61cc-b8c3-eb10f39e9fe0"),
        ("osm:n123", "osm:n123"),
    ],
)
def test_public_store_id_has_no_prefix(internal, public):
    assert service.public_store_id(internal) == public


def test_real_silpo_alt_branch_resolves():
    """Сільпо №2025 і №3319 — одна адреса (Бережанська, 22): uuid №3319 від агента веде до того ж магазину."""
    a = service.find_store("1eda8887-bf7c-6f38-b0cb-9503162b5586")
    b = service.find_store("1eda888d-b60d-66f4-a557-03a302d993f3")
    assert a is not None and a is b


async def test_api_nearby_requires_key_and_validates(fake_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/geo/stores/nearby", params={"lat": ORIGIN[0], "lng": ORIGIN[1]})).status_code == 401
    ok = await api_get("/geo/stores/nearby", {"lat": ORIGIN[0], "lng": ORIGIN[1], "store_ids": "1, " + SILPO_A})
    assert ok.status_code == 200 and ok.json()["recommended_store_id"] == "1"
    assert set(ok.json()["stores"][0]["maps_urls"]) == {"walking", "driving", "transit"}
    assert (await api_get("/geo/stores/nearby", {"lat": 50.45, "lng": 30.52, "mode": "bike"})).status_code == 422
    assert (await api_get("/geo/stores/nearby", {"lat": 50.45})).status_code == 422


async def test_api_route_raw_id_and_unknown(fake_data, monkeypatch):
    async def fake_shape(o, d, m):
        return {
            "distance_km": 1,
            "duration_min": 1,
            "estimated": True,
            "geometry": {"type": "LineString", "coordinates": [[o[1], o[0]], [d[1], d[0]]]},
        }

    monkeypatch.setattr(service, "route_shape", fake_shape)
    r = await api_get("/geo/route", {"lat": ORIGIN[0], "lng": ORIGIN[1], "store_id": "1"})
    assert r.status_code == 200 and r.json()["store_id"] == "1" and r.json()["geometry"]["type"] == "LineString"
    r = await api_get("/geo/route", {"lat": ORIGIN[0], "lng": ORIGIN[1], "store_id": "nope"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "store_not_found"
