"""Відстань і час у дорозі через публічний Valhalla (OSM) з fallback-оцінкою за прямою.

Публічний інстанс FOSSGIS: без ключа, ліміт 100 точок на матрицю → батчі по 99 цілей.
Якщо Valhalla не відповів — рахуємо за прямою з коефіцієнтом обходу і позначаємо `estimated: True`.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Sequence
from urllib.parse import urlencode

import httpx

from backend.config import get_settings
from backend.geo.distance import haversine_km

log = logging.getLogger(__name__)

Mode = Literal["walk", "car"]
COSTING: dict[str, str] = {"walk": "pedestrian", "car": "auto"}

# ПРИПУЩЕННЯ для fallback (коли Valhalla недоступний): середня швидкість і коефіцієнт
# обходу вулицями відносно прямої. Позначаються в відповіді як estimated=True.
FALLBACK_SPEED_KMH: dict[str, float] = {"walk": 4.8, "car": 25.0}
FALLBACK_DETOUR: dict[str, float] = {"walk": 1.3, "car": 1.4}

DEFAULT_RADIUS_KM: dict[str, float] = {"walk": 2.0, "car": 10.0}  # рішення команди 21.11
MAX_RADIUS_KM = 50.0  # спільна межа для запитів і витягу радіуса з голосу
MATRIX_BATCH = 99      # 1 джерело + 99 цілей = ліміт 100 точок публічного Valhalla
TIMEOUT_S = 5.0


def estimate(origin: tuple[float, float], dest: tuple[float, float], mode: Mode) -> dict:
    straight = haversine_km(*origin, *dest)
    dist = straight * FALLBACK_DETOUR[mode]
    return {"distance_km": round(dist, 2), "duration_min": round(dist / FALLBACK_SPEED_KMH[mode] * 60, 1),
            "estimated": True}


def _matrix_batch(client: httpx.Client, origin: tuple[float, float], targets: Sequence[tuple[float, float]],
                  mode: Mode) -> list[dict | None]:
    body = {
        "sources": [{"lat": origin[0], "lon": origin[1]}],
        "targets": [{"lat": t[0], "lon": t[1]} for t in targets],
        "costing": COSTING[mode],
        "units": "kilometers",
    }
    r = client.post(f"{get_settings().valhalla_url}/sources_to_targets", json=body)
    r.raise_for_status()
    row = r.json()["sources_to_targets"][0]
    out: list[dict | None] = [None] * len(targets)
    for cell in row:
        if cell.get("distance") is None or cell.get("time") is None:
            continue  # недосяжно (острів, закрита територія) → fallback нижче
        out[cell["to_index"]] = {"distance_km": round(cell["distance"], 2),
                                 "duration_min": round(cell["time"] / 60, 1), "estimated": False}
    return out


def travel_matrix(origin: tuple[float, float], targets: Sequence[tuple[float, float]], mode: Mode,
                  client: httpx.Client | None = None) -> list[dict]:
    """Для кожної цілі: {distance_km, duration_min, estimated}. Ніколи не падає."""
    if not targets:
        return []
    batches = [targets[i:i + MATRIX_BATCH] for i in range(0, len(targets), MATRIX_BATCH)]
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": get_settings().geo_user_agent})
    results: list[dict | None] = []
    try:
        def run(batch):
            try:
                return _matrix_batch(client, origin, batch, mode)
            except Exception as e:  # noqa: BLE001 — будь-яка помилка мережі/API → fallback
                log.warning("Valhalla matrix failed (%s): %s", mode, e)
                return [None] * len(batch)

        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as pool:
            for part in pool.map(run, batches):
                results.extend(part)
    finally:
        if own:
            client.close()
    return [res or estimate(origin, t, mode) for res, t in zip(results, targets)]


def _decode_polyline6(encoded: str) -> list[tuple[float, float]]:
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


def route_shape(origin: tuple[float, float], dest: tuple[float, float], mode: Mode,
                client: httpx.Client | None = None) -> dict:
    """Лінія маршруту для карти. Fallback — пряма лінія з estimated=True."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": get_settings().geo_user_agent})
    try:
        body = {"locations": [{"lat": origin[0], "lon": origin[1]}, {"lat": dest[0], "lon": dest[1]}],
                "costing": COSTING[mode], "directions_type": "none", "units": "kilometers"}
        r = client.post(f"{get_settings().valhalla_url}/route", json=body)
        r.raise_for_status()
        trip = r.json()["trip"]
        return {"distance_km": round(trip["summary"]["length"], 2),
                "duration_min": round(trip["summary"]["time"] / 60, 1),
                "estimated": False,
                "coordinates": [[a, b] for a, b in _decode_polyline6(trip["legs"][0]["shape"])]}
    except Exception as e:  # noqa: BLE001
        log.warning("Valhalla route failed (%s): %s", mode, e)
        return {**estimate(origin, dest, mode), "coordinates": [list(origin), list(dest)]}
    finally:
        if own:
            client.close()


def maps_urls(origin: tuple[float, float], dest: tuple[float, float]) -> dict[str, str]:
    """Посилання Google Maps без ключа; громадський транспорт рахує сам Google."""
    def url(travelmode: str) -> str:
        return "https://www.google.com/maps/dir/?" + urlencode({
            "api": 1,
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{dest[0]:.6f},{dest[1]:.6f}",
            "travelmode": travelmode,
        })
    return {"walking": url("walking"), "driving": url("driving"), "transit": url("transit")}
