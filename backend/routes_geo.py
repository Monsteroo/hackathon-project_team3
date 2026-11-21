"""HTTP API: магазини поруч, маршрут до обраного магазину, повний довідник для карти."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.config import in_service_area, not_found_in_area_message, outside_area_message
from backend.geo.directory import load_stores
from backend.geo.geocode import GeocoderUnavailable, OutsideServiceArea, geocode, reverse
from backend.geo.nearby import find_nearby, find_store
from backend.geo.routing import maps_urls, route_shape

router = APIRouter(prefix="/api", tags=["geo"])

Lat = Query(..., ge=-90, le=90)
Lng = Query(..., ge=-180, le=180)


def _outside_area() -> HTTPException:
    return HTTPException(422, {"code": "outside_service_area",
                               "message": outside_area_message()})


def _require_service_area(lat: float, lng: float) -> None:
    if not in_service_area(lat, lng):
        raise _outside_area()


@router.get("/stores/nearby")
def stores_nearby(
    lat: float = Lat,
    lng: float = Lng,
    mode: Literal["walk", "car"] = "walk",
    radius_km: float | None = Query(None, gt=0, le=50),
    store_ids: str | None = Query(None, description="ID через кому: магазини з підтвердженою ціною й наявністю"),
):
    _require_service_area(lat, lng)
    ids = store_ids.split(",") if store_ids else None
    return find_nearby(lat, lng, mode=mode, radius_km=radius_km, store_ids=ids)


@router.get("/route")
def route(
    lat: float = Lat,
    lng: float = Lng,
    store_id: str = Query(...),
    mode: Literal["walk", "car"] = "walk",
):
    _require_service_area(lat, lng)
    store = find_store(store_id)
    if store is None:
        raise HTTPException(404, {"code": "store_not_found", "message": "Магазин не знайдено"})
    dest = (store["lat"], store["lng"])
    return {
        "store_id": store["id"],
        "mode": mode,
        **route_shape((lat, lng), dest, mode),
        "maps_urls": maps_urls((lat, lng), dest),
    }


@router.get("/geocode")
def geocode_address(
    q: str = Query(..., min_length=2, max_length=200),
    suggest: bool = Query(False, description="true — підказки під час набору (лише Photon)"),
    lat: float | None = Query(None, ge=-90, le=90, description="зміщення підказок до поточної позиції"),
    lng: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(5, ge=1, le=10),
):
    bias = (lat, lng) if lat is not None and lng is not None else None
    try:
        results = geocode(q, limit=limit, suggest=suggest, bias=bias)
    except OutsideServiceArea:
        raise _outside_area()
    except GeocoderUnavailable:
        raise HTTPException(503, {"code": "geocoder_unavailable",
                                  "message": "Пошук адреси тимчасово недоступний. Спробуйте кнопку геолокації."})
    if not results and not suggest:
        raise HTTPException(404, {"code": "not_found_in_service_area", "message": not_found_in_area_message()})
    return {"results": results}


@router.get("/reverse")
def reverse_geocode(lat: float = Lat, lng: float = Lng):
    try:
        result = reverse(lat, lng)
    except OutsideServiceArea:
        raise _outside_area()
    except GeocoderUnavailable:
        raise HTTPException(503, {"code": "geocoder_unavailable", "message": "Не вдалося визначити адресу"})
    # Без адреси координати все одно придатні для пошуку магазинів
    return result or {"label": f"{lat:.5f}, {lng:.5f}", "full": "", "lat": lat, "lng": lng, "source": "coords"}


@router.get("/stores")
def all_stores():
    """Легкий список усіх магазинів для оглядової карти."""
    keys = ("id", "chain", "chain_name", "name", "city", "address", "lat", "lng", "place_id", "has_online_prices")
    return {"count": len(load_stores()), "stores": [{k: s[k] for k in keys} for s in load_stores()]}
