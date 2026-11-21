"""Публічний сервіс модуля geo: магазини поруч, маршрут, геокодинг.

Інші модулі (агент) викликають ці функції напряму, без HTTP: `await app.geo.service.find_nearby(...)`.

Логіка (рішення команди 21.11):
  * у відповіді — усі магазини в радіусі (пішки 2 км, авто 10 км), відсортовані за часом у дорозі;
  * якщо в радіусі порожньо — радіус подвоюється (до 3 разів), `radius_expanded: true`;
  * `recommended_store_id` — найближчий за часом серед `store_ids` (ціна й наявність підтверджені агентом
    або каталогом), навіть поза радіусом; без них — найближчий з `has_online_prices` (до 5 таких магазинів
    поза радіусом теж додаються у відповідь з `in_radius: false`).

ID магазинів за контрактом команди: `store_id` (Zakaz — `"482010105"`, Сільпо — uuid) + `chain` + `source`.
Для фізичних магазинів з OSM без цін `store_id` внутрішній: `"osm:n123"` / `"osm:w456"`.
"""

from collections.abc import Iterable

import httpx

from app.geo.directory import load_stores
from app.geo.distance import haversine_km
from app.geo.geocode import GeocoderUnavailable, OutsideServiceArea, geocode, reverse
from app.geo.ids import normalize_store_id
from app.geo.routing import DEFAULT_RADIUS_KM, MAX_RADIUS_KM, Mode, maps_urls, route_shape, travel_matrix

__all__ = [
    "MAX_RADIUS_KM",
    "GeocoderUnavailable",
    "OutsideServiceArea",
    "all_stores",
    "find_nearby",
    "find_store",
    "geocode",
    "normalize_store_id",
    "public_store_id",
    "reverse",
    "route_to_store",
]

MAX_EXPANSIONS = 3
PRICED_OUTSIDE_RADIUS = 5  # скільки найближчих магазинів з цінами поза радіусом теж повертати


def public_store_id(internal_id: str) -> str:
    """`zakaz:482010105` → `482010105`, `silpo:<uuid>` → `<uuid>`, OSM лишається `osm:n123`."""
    source, _, rest = internal_id.partition(":")
    return rest if source in ("zakaz", "silpo") else internal_id


def find_store(store_id: str) -> dict | None:
    sid = normalize_store_id(store_id)
    for s in load_stores():
        if s["id"] == sid or sid in s["alt_ids"]:
            return s
    return None


def _is_confirmed(store: dict, ids: set[str]) -> bool:
    return store["id"] in ids or any(a in ids for a in store["alt_ids"])


def _public(store: dict) -> dict:
    return {
        "store_id": public_store_id(store["id"]),
        "source": store["source"],
        "chain": store["chain"],
        "chain_name": store["chain_name"],
        "name": store["name"],
        "city": store["city"],
        "address": store["address"],
        "lat": store["lat"],
        "lng": store["lng"],
        "place_id": store["place_id"],
        "alt_store_ids": [public_store_id(a) for a in store["alt_ids"]],
        "has_online_prices": store["has_online_prices"],
        "offers_count": store.get("offers_count"),
        "online_catalog": store.get("online_catalog", False),
        "has_pickup": store["has_pickup"],
    }


def all_stores() -> list[dict]:
    return [_public(s) for s in load_stores()]


async def find_nearby(
    lat: float,
    lng: float,
    mode: Mode = "walk",
    radius_km: float | None = None,
    store_ids: Iterable[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    origin = (lat, lng)
    radius = min(radius_km or DEFAULT_RADIUS_KM[mode], MAX_RADIUS_KM)
    stores = load_stores()

    requested = [s.strip() for s in (store_ids or []) if s and s.strip()]
    known = {i for s in stores for i in (s["id"], *s["alt_ids"])}
    unknown = [r for r in requested if normalize_store_id(r) not in known]
    # Жоден ID не знайдено → працюємо як без store_ids, а невідомі повертаємо агенту/фронту
    confirmed_ids = {normalize_store_id(r) for r in requested} & known

    with_dist = sorted(((haversine_km(lat, lng, s["lat"], s["lng"]), s) for s in stores), key=lambda x: x[0])
    in_radius = [x for x in with_dist if x[0] <= radius]
    expanded = False
    for _ in range(MAX_EXPANSIONS):
        if in_radius or radius >= MAX_RADIUS_KM:
            break
        radius = min(radius * 2, MAX_RADIUS_KM)
        in_radius = [x for x in with_dist if x[0] <= radius]
        expanded = True

    # Маршрут має вести туди, де ціну підтверджено, навіть якщо це поза радіусом
    def priced(s: dict) -> bool:
        return _is_confirmed(s, confirmed_ids) if confirmed_ids else s["has_online_prices"]

    seen = {s["id"] for _, s in in_radius}
    extra = [x for x in with_dist if x[1]["id"] not in seen and priced(x[1])][:PRICED_OUTSIDE_RADIUS]
    candidates = in_radius + extra

    travel = await travel_matrix(origin, [(s["lat"], s["lng"]) for _, s in candidates], mode, client=client)

    items = []
    for (straight, s), t in zip(candidates, travel, strict=True):
        items.append(
            {
                **_public(s),
                "confirmed": _is_confirmed(s, confirmed_ids),
                "in_radius": straight <= radius,
                "straight_km": round(straight, 2),
                **t,
                "maps_urls": maps_urls(origin, (s["lat"], s["lng"])),
            }
        )
    items.sort(key=lambda x: (x["duration_min"], x["distance_km"]))

    recommended, reason = None, None
    if confirmed_ids:
        recommended = next((i for i in items if i["confirmed"]), None)
        reason = "confirmed_offer" if recommended else None
    if recommended is None:
        recommended = next((i for i in items if i["has_online_prices"]), None)
        reason = "nearest_with_online_prices" if recommended else None

    if items and all(i["estimated"] for i in items):
        routing = "estimated"
    elif any(i["estimated"] for i in items):
        routing = "mixed"
    else:
        routing = "valhalla"

    return {
        "origin": {"lat": lat, "lng": lng},
        "mode": mode,
        "radius_km": radius,
        "radius_expanded": expanded,
        "routing": routing,
        "recommended_store_id": recommended["store_id"] if recommended else None,
        "recommended_reason": reason,
        "unknown_store_ids": unknown,
        "count": len(items),
        "stores": items,
    }


async def route_to_store(lat: float, lng: float, store_id: str, mode: Mode = "walk") -> dict | None:
    """None — якщо магазин не знайдено."""
    store = find_store(store_id)
    if store is None:
        return None
    dest = (store["lat"], store["lng"])
    return {
        "store_id": public_store_id(store["id"]),
        "source": store["source"],
        "chain": store["chain"],
        "mode": mode,
        **(await route_shape((lat, lng), dest, mode)),
        "maps_urls": maps_urls((lat, lng), dest),
    }
