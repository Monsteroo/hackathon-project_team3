"""Пошук магазинів поруч і вибір рекомендованого для маршруту.

Логіка (рішення команди 21.11):
  * на карті — усі магазини в радіусі (за замовчуванням пішки 2 км, авто 10 км), відсортовані за часом у дорозі;
  * якщо в радіусі порожньо — радіус подвоюється (до 3 разів), у відповіді `radius_expanded: true`;
  * `recommended` — найближчий за часом магазин серед `store_ids` (підтверджені ціна й наявність від
    агента / Учасника 2), навіть якщо він поза радіусом; без `store_ids` — найближчий з товарами в наявності
    за OFFERS (`has_online_prices`), теж і поза радіусом (до 5 найближчих таких магазинів).
"""
from __future__ import annotations

from typing import Iterable

import httpx

from backend.geo.directory import load_stores
from backend.geo.distance import haversine_km
from backend.geo.routing import DEFAULT_RADIUS_KM, Mode, maps_urls, travel_matrix

MAX_RADIUS_KM = 50.0
MAX_EXPANSIONS = 3
CONFIRMED_OUTSIDE_RADIUS = 5  # скільки найближчих підтверджених магазинів поза радіусом теж рахувати


def find_store(store_id: str) -> dict | None:
    for s in load_stores():
        if s["id"] == store_id or store_id in s["alt_ids"]:
            return s
    return None


def _is_confirmed(store: dict, ids: set[str]) -> bool:
    return store["id"] in ids or any(a in ids for a in store["alt_ids"])


def find_nearby(lat: float, lng: float, mode: Mode = "walk", radius_km: float | None = None,
                store_ids: Iterable[str] | None = None, client: httpx.Client | None = None) -> dict:
    origin = (lat, lng)
    radius = min(radius_km or DEFAULT_RADIUS_KM[mode], MAX_RADIUS_KM)
    confirmed_ids = {s.strip() for s in (store_ids or []) if s and s.strip()}

    with_dist = [(haversine_km(lat, lng, s["lat"], s["lng"]), s) for s in load_stores()]
    with_dist.sort(key=lambda x: x[0])

    in_radius = [x for x in with_dist if x[0] <= radius]
    expanded = False
    for _ in range(MAX_EXPANSIONS):
        if in_radius or radius >= MAX_RADIUS_KM:
            break
        radius = min(radius * 2, MAX_RADIUS_KM)
        in_radius = [x for x in with_dist if x[0] <= radius]
        expanded = True

    # Маршрут має вести туди, де ціну підтверджено, навіть якщо це поза радіусом:
    # з store_ids — підтверджені агентом; без них — магазини з товарами в наявності за OFFERS.
    def priced(s: dict) -> bool:
        return _is_confirmed(s, confirmed_ids) if confirmed_ids else s["has_online_prices"]

    candidates = list(in_radius)
    seen = {s["id"] for _, s in in_radius}
    extra = [x for x in with_dist if x[1]["id"] not in seen and priced(x[1])]
    candidates += extra[:CONFIRMED_OUTSIDE_RADIUS]

    travel = travel_matrix(origin, [(s["lat"], s["lng"]) for _, s in candidates], mode, client=client)

    items = []
    for (straight, s), t in zip(candidates, travel):
        items.append({
            "id": s["id"],
            "alt_ids": s["alt_ids"],
            "chain": s["chain"],
            "chain_name": s["chain_name"],
            "name": s["name"],
            "city": s["city"],
            "address": s["address"],
            "lat": s["lat"],
            "lng": s["lng"],
            "place_id": s["place_id"],
            "has_online_prices": s["has_online_prices"],
            "online_catalog": s.get("online_catalog", False),
            "has_pickup": s["has_pickup"],
            "confirmed": _is_confirmed(s, confirmed_ids),
            "in_radius": straight <= radius,
            "straight_km": round(straight, 2),
            **t,
            "maps_urls": maps_urls(origin, (s["lat"], s["lng"])),
        })
    items.sort(key=lambda x: (x["duration_min"], x["distance_km"]))

    recommended, reason = None, None
    if confirmed_ids:
        recommended = next((i for i in items if i["confirmed"]), None)
        reason = "confirmed_offer" if recommended else None
    if recommended is None:
        recommended = next((i for i in items if i["has_online_prices"]), None)
        reason = "nearest_with_online_prices" if recommended else None

    return {
        "origin": {"lat": lat, "lng": lng},
        "mode": mode,
        "radius_km": radius,
        "radius_expanded": expanded,
        "routing": "estimated" if items and all(i["estimated"] for i in items)
                   else "mixed" if any(i["estimated"] for i in items) else "valhalla",
        "recommended_id": recommended["id"] if recommended else None,
        "recommended_reason": reason,
        "count": len(items),
        "stores": items,
    }
