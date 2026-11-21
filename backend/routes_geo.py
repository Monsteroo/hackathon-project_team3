"""HTTP API: магазини поруч, маршрут до обраного магазину, повний довідник для карти."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.geo.directory import load_stores
from backend.geo.nearby import find_nearby, find_store
from backend.geo.routing import maps_urls, route_shape

router = APIRouter(prefix="/api", tags=["geo"])

Lat = Query(..., ge=-90, le=90)
Lng = Query(..., ge=-180, le=180)


@router.get("/stores/nearby")
def stores_nearby(
    lat: float = Lat,
    lng: float = Lng,
    mode: Literal["walk", "car"] = "walk",
    radius_km: float | None = Query(None, gt=0, le=50),
    store_ids: str | None = Query(None, description="ID через кому: магазини з підтвердженою ціною й наявністю"),
):
    ids = store_ids.split(",") if store_ids else None
    return find_nearby(lat, lng, mode=mode, radius_km=radius_km, store_ids=ids)


@router.get("/route")
def route(
    lat: float = Lat,
    lng: float = Lng,
    store_id: str = Query(...),
    mode: Literal["walk", "car"] = "walk",
):
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


@router.get("/stores")
def all_stores():
    """Легкий список усіх магазинів для оглядової карти."""
    keys = ("id", "chain", "chain_name", "name", "city", "address", "lat", "lng", "place_id", "has_online_prices")
    return {"count": len(load_stores()), "stores": [{k: s[k] for k in keys} for s in load_stores()]}
