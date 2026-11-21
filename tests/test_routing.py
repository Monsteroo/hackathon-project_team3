import httpx
import pytest

from backend.geo import routing

ORIGIN = (50.4498, 30.5231)
A = (50.4520, 30.5300)
B = (50.4931, 30.5581)


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_estimate_uses_detour_and_speed():
    e = routing.estimate(ORIGIN, B, "walk")
    straight = routing.haversine_km(*ORIGIN, *B)
    assert e["estimated"] is True
    assert e["distance_km"] == pytest.approx(straight * 1.3, abs=0.01)
    assert e["duration_min"] == pytest.approx(e["distance_km"] / 4.8 * 60, abs=0.2)


def test_matrix_parses_valhalla_and_fills_unreachable():
    def handler(req):
        return httpx.Response(200, json={"sources_to_targets": [[
            {"to_index": 0, "distance": 0.845, "time": 663},
            {"to_index": 1, "distance": None, "time": None},
        ]]})
    res = routing.travel_matrix(ORIGIN, [A, B], "walk", client=mock_client(handler))
    assert res[0] == {"distance_km": round(0.845, 2), "duration_min": 11.1, "estimated": False}
    assert res[1]["estimated"] is True


def test_matrix_falls_back_when_valhalla_down():
    res = routing.travel_matrix(ORIGIN, [A, B], "car", client=mock_client(lambda r: httpx.Response(503)))
    assert all(x["estimated"] for x in res) and len(res) == 2


def test_matrix_batches_by_99(monkeypatch):
    calls = []

    def handler(req):
        import json
        n = len(json.loads(req.content)["targets"])
        calls.append(n)
        return httpx.Response(200, json={"sources_to_targets": [[
            {"to_index": i, "distance": 1.0, "time": 600} for i in range(n)]]})
    res = routing.travel_matrix(ORIGIN, [A] * 250, "car", client=mock_client(handler))
    assert sorted(calls) == [52, 99, 99]
    assert len(res) == 250 and not any(x["estimated"] for x in res)


def test_polyline6_decode():
    # Канонічний приклад Google (precision 5) у масштабі 1e6: кодуємо самі й декодуємо назад
    def enc(v):
        v = ~(v << 1) if v < 0 else v << 1
        out = ""
        while v >= 0x20:
            out += chr((0x20 | (v & 0x1F)) + 63)
            v >>= 5
        return out + chr(v + 63)
    pts = [(50.449800, 30.523100), (50.452000, 30.530000)]
    prev = (0, 0)
    s = ""
    for lat, lng in pts:
        ilat, ilng = round(lat * 1e6), round(lng * 1e6)
        s += enc(ilat - prev[0]) + enc(ilng - prev[1])
        prev = (ilat, ilng)
    assert routing._decode_polyline6(s) == pts


def test_route_shape_fallback_is_straight_line():
    r = routing.route_shape(ORIGIN, B, "walk", client=mock_client(lambda req: httpx.Response(500)))
    assert r["estimated"] is True and r["coordinates"] == [list(ORIGIN), list(B)]


def test_maps_urls_modes():
    urls = routing.maps_urls(ORIGIN, B)
    assert set(urls) == {"walking", "driving", "transit"}
    assert "travelmode=transit" in urls["transit"] and "destination=50.493100%2C30.558100" in urls["walking"]
