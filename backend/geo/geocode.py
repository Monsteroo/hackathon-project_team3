"""Геокодинг: адреса → координати і координати → адреса.

Основний — Nominatim (OSM): лише Україна, українською, не частіше 1 запиту/с (політика Nominatim),
з кешем. Запасний — Photon (komoot), він же для підказок під час набору (Nominatim автокомпліт забороняє).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict

import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)

TIMEOUT_S = 6.0
CACHE_SIZE = 512


class GeocoderUnavailable(RuntimeError):
    pass


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
_throttle_lock = threading.Lock()
_last_nominatim = 0.0


def _nominatim_throttle() -> None:
    global _last_nominatim
    with _throttle_lock:
        wait = 1.0 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            time.sleep(wait)
        _last_nominatim = time.monotonic()


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": get_settings().geo_user_agent})


def short_label(addr: dict) -> str:
    """«вулиця Хрещатик, 22, Київ» з addressdetails Nominatim / properties Photon."""
    road = addr.get("road") or addr.get("street") or addr.get("pedestrian") or addr.get("square") or ""
    house = addr.get("house_number") or addr.get("housenumber") or ""
    place = (addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet")
             or addr.get("municipality") or "")
    name = addr.get("name") or ""
    parts = [p for p in (road, house) if p] or ([name] if name else [])
    if place and place not in parts:
        parts.append(place)
    return ", ".join(parts)


def _from_nominatim(item: dict) -> dict:
    addr = item.get("address") or {}
    return {"label": short_label(addr) or item.get("display_name", ""), "full": item.get("display_name", ""),
            "lat": float(item["lat"]), "lng": float(item["lon"]), "source": "nominatim"}


def _from_photon(f: dict) -> dict:
    p = f.get("properties") or {}
    lng, lat = f["geometry"]["coordinates"]
    full = ", ".join(x for x in (p.get("name"), p.get("street"), p.get("housenumber"), p.get("city"), p.get("country")) if x)
    return {"label": short_label(p) or full, "full": full, "lat": float(lat), "lng": float(lng), "source": "photon"}


def _photon_search(client: httpx.Client, q: str, limit: int, bias: tuple[float, float] | None) -> list[dict]:
    params = {"q": q, "limit": limit * 2}
    if bias:
        params.update(lat=bias[0], lon=bias[1])
    r = client.get(f"{get_settings().photon_url}/api/", params=params)
    r.raise_for_status()
    feats = [f for f in r.json().get("features", []) if (f.get("properties") or {}).get("countrycode") == "UA"]
    return [_from_photon(f) for f in feats[:limit]]


def geocode(q: str, limit: int = 5, suggest: bool = False, bias: tuple[float, float] | None = None,
            client: httpx.Client | None = None) -> list[dict]:
    q = " ".join(q.split())
    if not q:
        return []
    key = ("s" if suggest else "g", q.lower(), limit, bias and (round(bias[0], 2), round(bias[1], 2)))
    if (hit := _cache.get_or(key)) is not None:
        return hit

    own = client is None
    client = client or _client()
    try:
        results = None
        if not suggest:
            try:
                _nominatim_throttle()
                r = client.get(f"{get_settings().nominatim_url}/search", params={
                    "q": q, "format": "jsonv2", "countrycodes": "ua", "accept-language": "uk",
                    "addressdetails": 1, "limit": limit})
                r.raise_for_status()
                results = [_from_nominatim(i) for i in r.json()]
            except Exception as e:  # noqa: BLE001
                log.warning("Nominatim search failed: %s", e)
        if results is None or (not results and not suggest):
            try:
                results = _photon_search(client, q, limit, bias) or (results or [])
            except Exception as e:  # noqa: BLE001
                log.warning("Photon search failed: %s", e)
                if results is None:
                    raise GeocoderUnavailable("Обидва геокодери недоступні") from e
        seen, unique = set(), []
        for r_ in results:  # той самий будинок як node і way → один рядок
            if r_["label"] not in seen:
                seen.add(r_["label"])
                unique.append(r_)
        _cache.put(key, unique)
        return unique
    finally:
        if own:
            client.close()


def reverse(lat: float, lng: float, client: httpx.Client | None = None) -> dict | None:
    key = ("r", round(lat, 5), round(lng, 5))
    if (hit := _cache.get_or(key)) is not None:
        return hit
    own = client is None
    client = client or _client()
    try:
        result = None
        try:
            _nominatim_throttle()
            r = client.get(f"{get_settings().nominatim_url}/reverse", params={
                "lat": lat, "lon": lng, "format": "jsonv2", "accept-language": "uk", "zoom": 18, "addressdetails": 1})
            r.raise_for_status()
            j = r.json()
            if "error" not in j:
                result = _from_nominatim(j)
        except Exception as e:  # noqa: BLE001
            log.warning("Nominatim reverse failed: %s", e)
            try:
                r = client.get(f"{get_settings().photon_url}/reverse", params={"lat": lat, "lon": lng})
                r.raise_for_status()
                feats = r.json().get("features", [])
                result = _from_photon(feats[0]) if feats else None
            except Exception as e2:  # noqa: BLE001
                raise GeocoderUnavailable("Обидва геокодери недоступні") from e2
        if result:
            result = {**result, "lat": lat, "lng": lng}  # координати користувача, не найближчої будівлі
        _cache.put(key, result)
        return result
    finally:
        if own:
            client.close()
