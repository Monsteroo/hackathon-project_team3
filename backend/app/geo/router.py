"""HTTP API модуля geo (prefix /geo). Тонкий шар: валідація → service → схема."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.geo import service
from app.geo.area import in_service_area, outside_area_detail
from app.geo.routing import MAX_RADIUS_KM
from app.geo.schemas import GeocodeOut, Mode, NearbyOut, Place, RouteOut, StoresOut

router = APIRouter(prefix="/geo", tags=["geo"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]


def _require_service_area(lat: float, lng: float) -> None:
    if not in_service_area(lat, lng):
        raise HTTPException(422, outside_area_detail())


@router.get("/stores", response_model=StoresOut)
async def list_stores() -> dict:
    """Усі магазини міст демо (без відстаней) — для оглядової карти."""
    stores = service.all_stores()
    return {"count": len(stores), "stores": stores}


@router.get("/stores/nearby", response_model=NearbyOut)
async def stores_nearby(
    lat: Lat,
    lng: Lng,
    mode: Mode = "walk",
    radius_km: Annotated[float | None, Query(gt=0, le=MAX_RADIUS_KM)] = None,
    store_ids: Annotated[
        str | None,
        Query(description="ID через кому: магазини з підтвердженою ціною й наявністю (сирі або zakaz:/silpo:)"),
    ] = None,
) -> dict:
    _require_service_area(lat, lng)
    ids = store_ids.split(",") if store_ids else None
    return await service.find_nearby(lat, lng, mode=mode, radius_km=radius_km, store_ids=ids)


@router.get("/route", response_model=RouteOut)
async def route(lat: Lat, lng: Lng, store_id: str, mode: Mode = "walk") -> dict:
    _require_service_area(lat, lng)
    result = await service.route_to_store(lat, lng, store_id, mode)
    if result is None:
        raise HTTPException(404, {"code": "store_not_found", "message": "store not found"})
    return result


@router.get("/geocode", response_model=GeocodeOut)
async def geocode_address(
    q: Annotated[str, Query(min_length=2, max_length=200)],
    suggest: Annotated[bool, Query(description="true — підказки під час набору (лише Photon)")] = False,
    lat: Annotated[float | None, Query(ge=-90, le=90, description="зміщення підказок до поточної позиції")] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> dict:
    bias = (lat, lng) if lat is not None and lng is not None else None
    try:
        results = await service.geocode(q, limit=limit, suggest=suggest, bias=bias)
    except service.OutsideServiceArea as e:
        raise HTTPException(422, outside_area_detail()) from e
    except service.GeocoderUnavailable as e:
        raise HTTPException(503, {"code": "geocoder_unavailable", "message": "geocoding is unavailable"}) from e
    if not results and not suggest:
        raise HTTPException(
            404, {"code": "not_found_in_service_area", "message": "address not found in the service area"}
        )
    return {"results": results}


@router.get("/reverse", response_model=Place)
async def reverse_geocode(lat: Lat, lng: Lng) -> dict:
    try:
        result = await service.reverse(lat, lng)
    except service.OutsideServiceArea as e:
        raise HTTPException(422, outside_area_detail()) from e
    except service.GeocoderUnavailable as e:
        raise HTTPException(503, {"code": "geocoder_unavailable", "message": "reverse geocoding is unavailable"}) from e
    # Без адреси координати все одно придатні для пошуку магазинів
    return result or {"label": f"{lat:.5f}, {lng:.5f}", "full": "", "lat": lat, "lng": lng, "source": "coords"}
