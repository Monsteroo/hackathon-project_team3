"""Геокодинг: адреса → координати і координати → адреса (лише в межах міст демо).

Основний — Nominatim (OSM): українською, не частіше 1 запиту/с (політика Nominatim), з кешем.
Запасний — Photon (komoot), він же для підказок під час набору (Nominatim автокомпліт забороняє).
Адреса в іншому місті → OutsideServiceArea (а не схожа київська вулиця).
"""

import asyncio
import logging
import time
from collections import OrderedDict

import httpx

from app.config import get_settings
from app.geo.area import area_box, in_service_area, service_cities
from app.geo.logsafe import err_summary

log = logging.getLogger(__name__)

TIMEOUT_S = 6.0
CACHE_SIZE = 512


class GeocoderUnavailable(RuntimeError):
    pass


class OutsideServiceArea(ValueError):
    """Точка або адреса поза містами демо (зараз — лише Київ)."""

    def __init__(self):
        super().__init__(f"service area is limited to: {', '.join(service_cities())}")


class _LRU(OrderedDict):
    def get_or(self, key):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put(self, key, value):
        self[key] = value
        self.move_to_end(key)
        while len(self) > CACHE_SIZE:
            self.popitem(last=False)


_cache = _LRU()
_OUTSIDE = object()  # у кеші: «адреса є, але поза містами демо»
_throttle_lock = asyncio.Lock()
_last_nominatim = 0.0


async def _nominatim_throttle() -> None:
    global _last_nominatim
    async with _throttle_lock:
        wait = 1.0 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim = time.monotonic()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": get_settings().geo_user_agent})


def short_label(addr: dict) -> str:
    """«вулиця Хрещатик, 22, Київ» з addressdetails Nominatim / properties Photon."""
    road = addr.get("road") or addr.get("street") or addr.get("pedestrian") or addr.get("square") or ""
    house = addr.get("house_number") or addr.get("housenumber") or ""
    place = (
        addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or addr.get("municipality")
    ) or ""
    name = addr.get("name") or ""
    parts = [p for p in (road, house) if p] or ([name] if name else [])
    if place and place not in parts:
        parts.append(place)
    return ", ".join(parts)


def _from_nominatim(item: dict) -> dict:
    addr = item.get("address") or {}
    return {
        "label": short_label(addr) or item.get("display_name", ""),
        "full": item.get("display_name", ""),
        "lat": float(item["lat"]),
        "lng": float(item["lon"]),
        "source": "nominatim",
    }


def _from_photon(f: dict) -> dict:
    p = f.get("properties") or {}
    lng, lat = f["geometry"]["coordinates"]
    parts = (p.get("name"), p.get("street"), p.get("housenumber"), p.get("city"), p.get("country"))
    full = ", ".join(x for x in parts if x)
    return {"label": short_label(p) or full, "full": full, "lat": float(lat), "lng": float(lng), "source": "photon"}


async def _photon_search(client: httpx.AsyncClient, q: str, limit: int, bias: tuple[float, float] | None) -> list[dict]:
    params: dict = {"q": q, "limit": limit * 2}
    if bias:
        params.update(lat=bias[0], lon=bias[1])
    if box := area_box():
        params["bbox"] = f"{box[1]},{box[0]},{box[3]},{box[2]}"  # minLon,minLat,maxLon,maxLat
    r = await client.get(f"{get_settings().photon_url.rstrip('/')}/api/", params=params)
    r.raise_for_status()
    feats = [f for f in r.json().get("features", []) if (f.get("properties") or {}).get("countrycode") == "UA"]
    return [_from_photon(f) for f in feats[:limit]]


async def _nominatim_search(client: httpx.AsyncClient, q: str, limit: int, bounded: bool) -> list[dict]:
    await _nominatim_throttle()
    params: dict = {
        "q": q,
        "format": "jsonv2",
        "countrycodes": "ua",
        "accept-language": "uk",
        "addressdetails": 1,
        "limit": limit,
    }
    if bounded and (box := area_box()):
        # viewbox=lng_min,lat_max,lng_max,lat_min; bounded=1 — лише всередині міст демо
        params.update(viewbox=f"{box[1]},{box[2]},{box[3]},{box[0]}", bounded=1)
    r = await client.get(f"{get_settings().nominatim_url.rstrip('/')}/search", params=params)
    r.raise_for_status()
    return [_from_nominatim(i) for i in r.json()]


async def geocode(
    q: str,
    limit: int = 5,
    suggest: bool = False,
    bias: tuple[float, float] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    q = " ".join(q.split())
    if not q:
        return []
    key = ("s" if suggest else "g", q.lower(), limit, bias and (round(bias[0], 2), round(bias[1], 2)))
    if (hit := _cache.get_or(key)) is not None:
        if hit is _OUTSIDE:
            raise OutsideServiceArea()
        return hit

    own = client is None
    client = client or _client()
    try:
        results = None
        if not suggest:
            try:
                results = await _nominatim_search(client, q, limit, bounded=True)
                if not results and area_box():
                    # У межах міста порожньо: перевіряємо, чи адреса взагалі є, але деінде («Львів, …»),
                    # щоб сказати «поки лише Київ», а не підсунути схожу київську вулицю.
                    anywhere = await _nominatim_search(client, q, 1, bounded=False)
                    if anywhere and not in_service_area(anywhere[0]["lat"], anywhere[0]["lng"]):
                        _cache.put(key, _OUTSIDE)
                        raise OutsideServiceArea()
            except OutsideServiceArea:
                raise
            except Exception as e:
                log.warning("Nominatim search failed: %s", err_summary(e))
                results = None
        if results is None:  # Nominatim недоступний (не «порожньо») або режим підказок
            try:
                results = await _photon_search(client, q, limit, bias)
            except Exception as e:
                log.warning("Photon search failed: %s", err_summary(e))
                if not suggest:
                    raise GeocoderUnavailable("both geocoders are unavailable") from e
                results = []
        seen, unique = set(), []
        for item in results:  # той самий будинок як node і way → один рядок
            if in_service_area(item["lat"], item["lng"]) and item["label"] not in seen:
                seen.add(item["label"])
                unique.append(item)
        _cache.put(key, unique)
        return unique
    finally:
        if own:
            await client.aclose()


async def reverse(lat: float, lng: float, client: httpx.AsyncClient | None = None) -> dict | None:
    if not in_service_area(lat, lng):
        raise OutsideServiceArea()
    key = ("r", round(lat, 5), round(lng, 5))
    if (hit := _cache.get_or(key)) is not None:
        return hit
    own = client is None
    client = client or _client()
    try:
        result = None
        try:
            await _nominatim_throttle()
            r = await client.get(
                f"{get_settings().nominatim_url.rstrip('/')}/reverse",
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "jsonv2",
                    "accept-language": "uk",
                    "zoom": 18,
                    "addressdetails": 1,
                },
            )
            r.raise_for_status()
            j = r.json()
            if "error" not in j:
                result = _from_nominatim(j)
        except Exception as e:
            log.warning("Nominatim reverse failed: %s", err_summary(e))
            try:
                r = await client.get(
                    f"{get_settings().photon_url.rstrip('/')}/reverse", params={"lat": lat, "lon": lng}
                )
                r.raise_for_status()
                feats = r.json().get("features", [])
                result = _from_photon(feats[0]) if feats else None
            except Exception as e2:
                raise GeocoderUnavailable("both geocoders are unavailable") from e2
        if result:
            result = {**result, "lat": lat, "lng": lng}  # координати користувача, не найближчої будівлі
        _cache.put(key, result)
        return result
    finally:
        if own:
            await client.aclose()
