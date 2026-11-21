import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.geo import nearby

ORIGIN = (50.4500, 30.5200)


def store(id_, lat, lng, online=True, alt=()):
    return {"id": id_, "alt_ids": list(alt), "chain": "novus", "chain_name": "NOVUS", "name": id_, "city": "Київ",
            "address": "", "lat": lat, "lng": lng, "place_id": f"{lat},{lng}", "has_online_prices": online,
            "has_pickup": online}


STORES = (
    store("osm:n1", 50.4510, 30.5200, online=False),       # ~0.1 км, без цін
    store("zakaz:1", 50.4560, 30.5200),                     # ~0.7 км
    store("silpo:a", 50.4600, 30.5200, alt=["silpo:old"]),  # ~1.1 км
    store("zakaz:far", 50.5200, 30.5200),                   # ~7.8 км
)


@pytest.fixture(autouse=True)
def fake_data(monkeypatch):
    monkeypatch.setattr(nearby, "load_stores", lambda: STORES)

    def fake_matrix(origin, targets, mode, client=None):
        # час пропорційний відстані по прямій: детерміновано, без мережі
        return [{"distance_km": round(nearby.haversine_km(*origin, *t), 2),
                 "duration_min": round(nearby.haversine_km(*origin, *t) * 12, 1), "estimated": False}
                for t in targets]
    monkeypatch.setattr(nearby, "travel_matrix", fake_matrix)


def test_default_walk_radius_and_recommend_nearest_online():
    r = nearby.find_nearby(*ORIGIN)
    assert r["radius_km"] == 2.0 and not r["radius_expanded"]
    # у радіусі — 3; плюс магазин з цінами поза радіусом (in_radius=False), щоб було куди вести маршрут
    assert [(s["id"], s["in_radius"]) for s in r["stores"]] == [
        ("osm:n1", True), ("zakaz:1", True), ("silpo:a", True), ("zakaz:far", False)]
    assert r["recommended_id"] == "zakaz:1"  # найближчий osm без цін пропускаємо
    assert r["recommended_reason"] == "nearest_with_online_prices"


def test_confirmed_store_ids_win_even_outside_radius():
    r = nearby.find_nearby(*ORIGIN, store_ids=["zakaz:far"])
    assert r["recommended_id"] == "zakaz:far"
    assert r["recommended_reason"] == "confirmed_offer"
    far = next(s for s in r["stores"] if s["id"] == "zakaz:far")
    assert far["confirmed"] and not far["in_radius"]


def test_confirmed_matches_alt_ids():
    r = nearby.find_nearby(*ORIGIN, store_ids=["silpo:old"])
    assert r["recommended_id"] == "silpo:a"


def test_radius_expands_when_empty():
    r = nearby.find_nearby(50.6000, 30.5200, mode="walk")  # ~9 км від найближчого
    assert r["radius_expanded"] and r["radius_km"] == 16.0
    assert r["count"] >= 1


def test_car_default_radius():
    r = nearby.find_nearby(*ORIGIN, mode="car")
    assert r["radius_km"] == 10.0 and r["count"] == 4


def test_api_nearby_and_validation():
    c = TestClient(app)
    ok = c.get("/api/stores/nearby", params={"lat": ORIGIN[0], "lng": ORIGIN[1], "store_ids": "zakaz:1, silpo:a"})
    assert ok.status_code == 200 and ok.json()["recommended_id"] == "zakaz:1"
    assert set(ok.json()["stores"][0]["maps_urls"]) == {"walking", "driving", "transit"}
    assert c.get("/api/stores/nearby", params={"lat": 50.45, "lng": 30.52, "mode": "bike"}).status_code == 422
    assert c.get("/api/stores/nearby", params={"lat": 50.45}).status_code == 422


def test_api_route_unknown_store():
    r = TestClient(app).get("/api/route", params={"lat": 50.45, "lng": 30.52, "store_id": "nope"})
    assert r.status_code == 404


def test_priced_store_outside_radius_is_still_recommended(monkeypatch):
    stores = (store("osm:n1", 50.4510, 30.5200, online=False),
              store("zakaz:far", 50.5200, 30.5200, online=True))   # ~7.8 км, з цінами
    monkeypatch.setattr(nearby, "load_stores", lambda: stores)
    r = nearby.find_nearby(*ORIGIN)
    assert r["recommended_id"] == "zakaz:far" and r["recommended_reason"] == "nearest_with_online_prices"
    assert [s["in_radius"] for s in r["stores"]] == [True, False]


# --- B1: сирі ID з API Учасниці 2 / агента --------------------------------------------------

@pytest.mark.parametrize("raw,norm", [
    ("48201031", "zakaz:48201031"),
    ("zakaz:48201031", "zakaz:48201031"),
    (" 1EDB6B12-C559-61CC-B8C3-EB10F39E9FE0 ", "silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0"),
    ("silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0", "silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0"),
    ("osm:n123", "osm:n123"),
])
def test_normalize_store_id(raw, norm):
    assert nearby.normalize_store_id(raw) == norm


def test_raw_ids_and_alt_ids_are_confirmed():
    r = nearby.find_nearby(*ORIGIN, store_ids=["1", "old"])  # «old» не uuid і не число → невідомий
    assert r["recommended_id"] == "zakaz:1" and r["recommended_reason"] == "confirmed_offer"
    assert r["unknown_store_ids"] == ["old"]


def test_all_unknown_ids_behave_like_no_ids():
    r = nearby.find_nearby(*ORIGIN, store_ids=["999999", "nope"])
    assert r["recommended_reason"] == "nearest_with_online_prices" and r["recommended_id"] == "zakaz:1"
    assert r["unknown_store_ids"] == ["999999", "nope"]
    assert not any(s["confirmed"] for s in r["stores"])


def test_real_silpo_alt_branch_resolves(monkeypatch):
    """Сільпо №2025 і №3319 — одна адреса (Бережанська, 22): uuid №3319 від агента веде до того ж магазину."""
    monkeypatch.undo()  # справжній довідник
    from backend.geo.nearby import find_store
    a = find_store("1eda8887-bf7c-6f38-b0cb-9503162b5586")
    b = find_store("1eda888d-b60d-66f4-a557-03a302d993f3")
    assert a is not None and a is b


def test_api_route_accepts_raw_id(monkeypatch):
    monkeypatch.setattr("backend.routes_geo.route_shape",
                        lambda o, d, m: {"distance_km": 1, "duration_min": 1, "estimated": True, "coordinates": []})
    r = TestClient(app).get("/api/route", params={"lat": ORIGIN[0], "lng": ORIGIN[1], "store_id": "1"})
    assert r.status_code == 200 and r.json()["store_id"] == "zakaz:1"
