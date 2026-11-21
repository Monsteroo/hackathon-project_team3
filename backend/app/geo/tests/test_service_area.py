import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.geo import area
from app.geo import geocode as g
from app.geo.directory import load_stores
from app.main import app

KYIV = {"lat": 50.4498, "lng": 30.5231}
LVIV = {"lat": 49.8397, "lng": 24.0297}
OUTSIDE = {"code": "outside_service_area", "message": "service area is limited to: Київ"}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    async def instant():
        return None

    monkeypatch.setattr(g, "_nominatim_throttle", instant)
    g._cache.clear()


async def api_get(path, params):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "test-api-key"}
    ) as c:
        return await c.get(path, params=params)


def test_default_service_area_is_kyiv(monkeypatch):
    monkeypatch.delenv("SERVICE_CITIES", raising=False)
    get_settings.cache_clear()
    assert area.service_cities() == ["Київ"]
    assert area.in_service_area(**KYIV) and not area.in_service_area(**LVIV)


def test_service_cities_from_env(monkeypatch):
    monkeypatch.setenv("SERVICE_CITIES", "Київ, Невідоме")
    get_settings.cache_clear()
    assert area.service_cities() == ["Київ", "Невідоме"]
    assert area.service_bboxes() == [area.CITY_BBOX["Київ"]]  # міста без меж ігноруються


def test_directory_is_kyiv_only():
    stores = load_stores()
    assert {s["city"] for s in stores} == {"Київ"}
    assert all(area.in_service_area(s["lat"], s["lng"]) for s in stores)


@pytest.mark.parametrize(
    "path,params",
    [
        ("/geo/stores/nearby", LVIV),
        ("/geo/route", {**LVIV, "store_id": "48201070"}),
        ("/geo/reverse", LVIV),
    ],
)
async def test_outside_kyiv_is_clear_error(path, params):
    r = await api_get(path, params)
    assert r.status_code == 422 and r.json()["detail"] == OUTSIDE


async def test_nominatim_is_bounded_to_kyiv():
    seen = []

    def h(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=[])

    assert await g.geocode("Хрещатик 22", client=httpx.AsyncClient(transport=httpx.MockTransport(h))) == []
    assert seen[0]["bounded"] == "1" and seen[0]["viewbox"] == "30.239,50.591,30.826,50.213"


async def test_address_in_other_city_is_outside_not_substituted_and_cached():
    lviv = {
        "lat": "49.8405",
        "lon": "24.0293",
        "display_name": "10, проспект Свободи, Львів",
        "address": {"road": "проспект Свободи", "house_number": "10", "city": "Львів"},
    }
    calls = []

    def h(req):
        calls.append(1)
        assert "photon" not in req.url.host, "Photon не має підміняти адресу, коли Nominatim працює"
        return httpx.Response(200, json=[] if req.url.params.get("bounded") else [lviv])

    c = httpx.AsyncClient(transport=httpx.MockTransport(h))
    with pytest.raises(g.OutsideServiceArea):
        await g.geocode("Львів, Свободи 10", client=c)
    with pytest.raises(g.OutsideServiceArea):  # з кешу, без повторних запитів до Nominatim
        await g.geocode("Львів, Свободи 10", client=c)
    assert len(calls) == 2  # bounded + unbounded лише першого разу


async def test_photon_results_outside_kyiv_dropped():
    fc = {
        "features": [
            {
                "properties": {"street": "проспект Свободи", "housenumber": "10", "city": "Львів", "countrycode": "UA"},
                "geometry": {"coordinates": [24.0293, 49.8405]},
            }
        ]
    }
    res = await g.geocode(
        "Свободи 10",
        suggest=True,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=fc))),
    )
    assert res == []


async def test_api_geocode_not_found(monkeypatch):
    async def nothing(*a, **k):
        return []

    monkeypatch.setattr("app.geo.service.geocode", nothing)
    r = await api_get("/geo/geocode", {"q": "Неіснуюча вулиця 999"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found_in_service_area"
