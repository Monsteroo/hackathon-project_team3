import httpx
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.geo import geocode as g
from backend.geo.directory import load_stores

KYIV = {"lat": 50.4498, "lng": 30.5231}
LVIV = {"lat": 49.8397, "lng": 24.0297}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(g, "_nominatim_throttle", lambda: None)
    g._cache.clear()


def test_default_service_area_is_kyiv(monkeypatch):
    monkeypatch.delenv("SERVICE_CITIES", raising=False)
    assert config.service_cities() == ["Київ"]
    assert config.in_service_area(**KYIV) and not config.in_service_area(**LVIV)
    assert config.outside_area_message() == "Поки працюємо лише по Києву"


def test_service_cities_from_env(monkeypatch):
    monkeypatch.setenv("SERVICE_CITIES", "Київ, Невідоме")
    assert config.service_cities() == ["Київ", "Невідоме"]
    assert config.service_bboxes() == [config.CITY_BBOX["Київ"]]  # міста без меж ігноруються


def test_directory_is_kyiv_only():
    stores = load_stores()
    assert {s["city"] for s in stores} == {"Київ"}
    assert all(config.in_service_area(s["lat"], s["lng"]) for s in stores)


@pytest.mark.parametrize("path,params", [
    ("/api/stores/nearby", LVIV),
    ("/api/route", {**LVIV, "store_id": "zakaz:48201070"}),
    ("/api/reverse", LVIV),
])
def test_outside_kyiv_is_clear_error(path, params):
    r = TestClient(app).get(path, params=params)
    assert r.status_code == 422
    assert r.json()["detail"] == {"code": "outside_service_area", "message": "Поки працюємо лише по Києву"}


def test_nominatim_is_bounded_to_kyiv():
    seen = []

    def h(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=[])
    assert g.geocode("Хрещатик 22", client=httpx.Client(transport=httpx.MockTransport(h))) == []
    assert seen[0]["bounded"] == "1" and seen[0]["viewbox"] == "30.239,50.591,30.826,50.213"


def test_address_in_other_city_is_outside_not_substituted():
    lviv = {"lat": "49.8405", "lon": "24.0293", "display_name": "10, проспект Свободи, Львів",
            "address": {"road": "проспект Свободи", "house_number": "10", "city": "Львів"}}

    def h(req):
        if "photon" in req.url.host:
            raise AssertionError("Photon не має підміняти адресу, коли Nominatim працює")
        return httpx.Response(200, json=[] if req.url.params.get("bounded") else [lviv])
    with pytest.raises(g.OutsideServiceArea):
        g.geocode("Львів, Свободи 10", client=httpx.Client(transport=httpx.MockTransport(h)))


def test_photon_results_outside_kyiv_dropped():
    fc = {"features": [
        {"properties": {"street": "проспект Свободи", "housenumber": "10", "city": "Львів", "countrycode": "UA"},
         "geometry": {"coordinates": [24.0293, 49.8405]}},
    ]}
    res = g.geocode("Свободи 10", suggest=True,
                    client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=fc))))
    assert res == []


def test_api_geocode_not_found_message(monkeypatch):
    monkeypatch.setattr("backend.routes_geo.geocode", lambda *a, **k: [])
    r = TestClient(app).get("/api/geocode", params={"q": "Львів, Свободи 10"})
    assert r.status_code == 404
    assert r.json()["detail"]["message"] == "Адресу не знайдено в Києві. Поки працюємо лише по Києву."
