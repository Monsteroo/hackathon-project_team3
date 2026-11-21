import json

import httpx
import pytest

from app.geo import routing

ORIGIN = (50.4498, 30.5231)
A = (50.4520, 30.5300)
B = (50.4931, 30.5581)


def mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_estimate_uses_detour_and_speed():
    e = routing.estimate(ORIGIN, B, "walk")
    straight = routing.haversine_km(*ORIGIN, *B)
    assert e["estimated"] is True
    assert e["distance_km"] == pytest.approx(straight * 1.3, abs=0.01)
    assert e["duration_min"] == pytest.approx(e["distance_km"] / 4.8 * 60, abs=0.2)


async def test_matrix_parses_valhalla_and_fills_unreachable():
    def handler(req):
        return httpx.Response(
            200,
            json={
                "sources_to_targets": [
                    [{"to_index": 0, "distance": 0.845, "time": 663}, {"to_index": 1, "distance": None, "time": None}]
                ]
            },
        )

    res = await routing.travel_matrix(ORIGIN, [A, B], "walk", client=mock_client(handler))
    assert res[0] == {"distance_km": round(0.845, 2), "duration_min": 11.1, "estimated": False}
    assert res[1]["estimated"] is True


async def test_matrix_falls_back_when_valhalla_down():
    res = await routing.travel_matrix(ORIGIN, [A, B], "car", client=mock_client(lambda r: httpx.Response(503)))
    assert all(x["estimated"] for x in res) and len(res) == 2


async def test_matrix_batches_by_99():
    calls = []

    def handler(req):
        n = len(json.loads(req.content)["targets"])
        calls.append(n)
        cells = [{"to_index": i, "distance": 1.0, "time": 600} for i in range(n)]
        return httpx.Response(200, json={"sources_to_targets": [cells]})

    res = await routing.travel_matrix(ORIGIN, [A] * 250, "car", client=mock_client(handler))
    assert sorted(calls) == [52, 99, 99]
    assert len(res) == 250 and not any(x["estimated"] for x in res)


def _encode(v: int) -> str:
    v = ~(v << 1) if v < 0 else v << 1
    out = ""
    while v >= 0x20:
        out += chr((0x20 | (v & 0x1F)) + 63)
        v >>= 5
    return out + chr(v + 63)


def test_polyline6_decode():
    pts = [(50.449800, 30.523100), (50.452000, 30.530000)]
    prev, s = (0, 0), ""
    for lat, lng in pts:
        ilat, ilng = round(lat * 1e6), round(lng * 1e6)
        s += _encode(ilat - prev[0]) + _encode(ilng - prev[1])
        prev = (ilat, ilng)
    assert routing._decode_polyline6(s) == pts


async def test_route_geometry_is_geojson_lng_lat():
    shape = _encode(round(50.4498 * 1e6)) + _encode(round(30.5231 * 1e6))
    body = {"trip": {"summary": {"length": 0.9, "time": 650}, "legs": [{"shape": shape}]}}
    r = await routing.route_shape(ORIGIN, A, "walk", client=mock_client(lambda req: httpx.Response(200, json=body)))
    assert r["geometry"] == {"type": "LineString", "coordinates": [[30.5231, 50.4498]]}  # [lng, lat]
    assert r["estimated"] is False and r["duration_min"] == 10.8


async def test_route_shape_fallback_is_straight_line():
    r = await routing.route_shape(ORIGIN, B, "walk", client=mock_client(lambda req: httpx.Response(500)))
    assert r["estimated"] is True
    assert r["geometry"]["coordinates"] == [[ORIGIN[1], ORIGIN[0]], [B[1], B[0]]]


def test_maps_urls_modes():
    urls = routing.maps_urls(ORIGIN, B)
    assert set(urls) == {"walking", "driving", "transit"}
    assert "travelmode=transit" in urls["transit"] and "destination=50.493100%2C30.558100" in urls["walking"]
