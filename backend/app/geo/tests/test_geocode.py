import httpx
import pytest

from app.geo import geocode as g

NOMINATIM_ITEM = {
    "lat": "50.4498465",
    "lon": "30.5230925",
    "display_name": "22, вулиця Хрещатик, Центр, Шевченківський район, Київ, 01001, Україна",
    "address": {"house_number": "22", "road": "вулиця Хрещатик", "city": "Київ", "country_code": "ua"},
}
PHOTON_FC = {
    "features": [
        {
            "properties": {"street": "вулиця Хрещатик", "housenumber": "22", "city": "Київ", "countrycode": "UA"},
            "geometry": {"coordinates": [30.5231, 50.4498]},
        },
        {
            "properties": {"street": "Хрещатик", "city": "Чернівці", "countrycode": "RO"},
            "geometry": {"coordinates": [25.9, 48.3]},
        },
    ]
}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    async def instant():
        return None

    monkeypatch.setattr(g, "_nominatim_throttle", instant)
    g._cache.clear()


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_short_label():
    assert g.short_label(NOMINATIM_ITEM["address"]) == "вулиця Хрещатик, 22, Київ"
    assert g.short_label({"town": "Буча", "name": "ТЦ"}) == "ТЦ, Буча"


async def test_geocode_nominatim_params_and_parse():
    seen = {}

    def h(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=[NOMINATIM_ITEM])

    res = await g.geocode("  Хрещатик   22 ", client=client(h))
    assert seen["countrycodes"] == "ua" and seen["accept-language"] == "uk" and seen["q"] == "Хрещатик 22"
    assert res[0]["label"] == "вулиця Хрещатик, 22, Київ" and res[0]["source"] == "nominatim"


async def test_geocode_falls_back_to_photon_and_filters_ua():
    def h(req):
        return httpx.Response(503) if "nominatim" in req.url.host else httpx.Response(200, json=PHOTON_FC)

    res = await g.geocode("Хрещатик 22", client=client(h))
    assert [r["source"] for r in res] == ["photon"] and res[0]["label"] == "вулиця Хрещатик, 22, Київ"


async def test_suggest_uses_photon_only():
    hosts = []

    def h(req):
        hosts.append(req.url.host)
        return httpx.Response(200, json=PHOTON_FC)

    await g.geocode("Хреща", suggest=True, client=client(h))
    assert hosts == ["photon.komoot.io"]


async def test_both_down_raises():
    with pytest.raises(g.GeocoderUnavailable):
        await g.geocode("Хрещатик", client=client(lambda r: httpx.Response(500)))


async def test_cache_hits_once():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(200, json=[NOMINATIM_ITEM])

    c = client(h)
    await g.geocode("Хрещатик 22", client=c)
    await g.geocode("хрещатик 22", client=c)
    assert len(calls) == 1


async def test_reverse_keeps_user_coords():
    res = await g.reverse(50.44991, 30.52316, client=client(lambda r: httpx.Response(200, json=NOMINATIM_ITEM)))
    assert res["label"] == "вулиця Хрещатик, 22, Київ" and (res["lat"], res["lng"]) == (50.44991, 30.52316)
