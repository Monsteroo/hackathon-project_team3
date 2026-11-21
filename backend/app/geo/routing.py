"""Відстань і час у дорозі через публічний Valhalla (OSM) з fallback-оцінкою за прямою.

Публічний інстанс FOSSGIS: без ключа, ліміт 100 точок на матрицю → батчі по 99 цілей паралельно.
Якщо Valhalla не відповів — рахуємо за прямою з коефіцієнтом обходу і позначаємо `estimated: True`.
"""

import asyncio
import logging
from collections.abc import Sequence
from typing import Literal
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.geo.distance import haversine_km
from app.geo.logsafe import err_summary

log = logging.getLogger(__name__)

Mode = Literal["walk", "car"]
COSTING: dict[str, str] = {"walk": "pedestrian", "car": "auto"}

# ПРИПУЩЕННЯ для fallback (коли Valhalla недоступний): середня швидкість і коефіцієнт обходу вулицями
# відносно прямої. У відповіді позначаються як estimated=True.
FALLBACK_SPEED_KMH: dict[str, float] = {"walk": 4.8, "car": 25.0}
FALLBACK_DETOUR: dict[str, float] = {"walk": 1.3, "car": 1.4}

DEFAULT_RADIUS_KM: dict[str, float] = {"walk": 2.0, "car": 10.0}  # рішення команди 21.11
MAX_RADIUS_KM = 50.0  # спільна межа для запитів і витягу радіуса з голосу
MATRIX_BATCH = 99  # 1 джерело + 99 цілей = ліміт 100 точок публічного Valhalla
TIMEOUT_S = 5.0


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": get_settings().geo_user_agent})


def estimate(origin: tuple[float, float], dest: tuple[float, float], mode: Mode) -> dict:
    dist = haversine_km(*origin, *dest) * FALLBACK_DETOUR[mode]
    return {
        "distance_km": round(dist, 2),
        "duration_min": round(dist / FALLBACK_SPEED_KMH[mode] * 60, 1),
        "estimated": True,
    }


async def _matrix_batch(
    client: httpx.AsyncClient, origin: tuple[float, float], targets: Sequence[tuple[float, float]], mode: Mode
) -> list[dict | None]:
    body = {
        "sources": [{"lat": origin[0], "lon": origin[1]}],
        "targets": [{"lat": t[0], "lon": t[1]} for t in targets],
        "costing": COSTING[mode],
        "units": "kilometers",
    }
    try:
        r = await client.post(f"{get_settings().valhalla_url.rstrip('/')}/sources_to_targets", json=body)
        r.raise_for_status()
        row = r.json()["sources_to_targets"][0]
    except Exception as e:  # будь-яка помилка мережі/API → fallback для всього батча
        log.warning("Valhalla matrix failed (%s): %s", mode, err_summary(e))
        return [None] * len(targets)
    out: list[dict | None] = [None] * len(targets)
    for cell in row:
        if cell.get("distance") is None or cell.get("time") is None:
            continue  # недосяжно (острів, закрита територія) → fallback нижче
        out[cell["to_index"]] = {
            "distance_km": round(cell["distance"], 2),
            "duration_min": round(cell["time"] / 60, 1),
            "estimated": False,
        }
    return out


async def travel_matrix(
    origin: tuple[float, float],
    targets: Sequence[tuple[float, float]],
    mode: Mode,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Для кожної цілі: {distance_km, duration_min, estimated}. Ніколи не падає."""
    if not targets:
        return []
    batches = [targets[i : i + MATRIX_BATCH] for i in range(0, len(targets), MATRIX_BATCH)]
    own = client is None
    client = client or _client()
    try:
        parts = await asyncio.gather(*(_matrix_batch(client, origin, b, mode) for b in batches))
    finally:
        if own:
            await client.aclose()
    results = [cell for part in parts for cell in part]
    return [res or estimate(origin, t, mode) for res, t in zip(results, targets, strict=True)]


def _decode_polyline6(encoded: str) -> list[tuple[float, float]]:
    """Valhalla shape (precision 6) → [(lat, lng), …]."""
    coords, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        coords.append((lat / 1e6, lng / 1e6))
    return coords


def line_string(points: Sequence[tuple[float, float]]) -> dict:
    """GeoJSON LineString: координати [lng, lat], як чекає MapLibre."""
    return {"type": "LineString", "coordinates": [[round(lng, 6), round(lat, 6)] for lat, lng in points]}


async def route_shape(
    origin: tuple[float, float], dest: tuple[float, float], mode: Mode, client: httpx.AsyncClient | None = None
) -> dict:
    """Лінія маршруту для карти (`geometry`, GeoJSON). Fallback — пряма лінія з estimated=True."""
    own = client is None
    client = client or _client()
    try:
        body = {
            "locations": [{"lat": origin[0], "lon": origin[1]}, {"lat": dest[0], "lon": dest[1]}],
            "costing": COSTING[mode],
            "directions_type": "none",
            "units": "kilometers",
        }
        r = await client.post(f"{get_settings().valhalla_url.rstrip('/')}/route", json=body)
        r.raise_for_status()
        trip = r.json()["trip"]
        return {
            "distance_km": round(trip["summary"]["length"], 2),
            "duration_min": round(trip["summary"]["time"] / 60, 1),
            "estimated": False,
            "geometry": line_string(_decode_polyline6(trip["legs"][0]["shape"])),
        }
    except Exception as e:
        log.warning("Valhalla route failed (%s): %s", mode, err_summary(e))
        return {**estimate(origin, dest, mode), "geometry": line_string([origin, dest])}
    finally:
        if own:
            await client.aclose()


def maps_urls(origin: tuple[float, float], dest: tuple[float, float]) -> dict[str, str]:
    """Посилання Google Maps без ключа; громадський транспорт рахує сам Google."""

    def url(travelmode: str) -> str:
        return "https://www.google.com/maps/dir/?" + urlencode(
            {
                "api": 1,
                "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
                "destination": f"{dest[0]:.6f},{dest[1]:.6f}",
                "travelmode": travelmode,
            }
        )

    return {"walking": url("walking"), "driving": url("driving"), "transit": url("transit")}
