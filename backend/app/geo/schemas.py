"""Схеми модуля geo — контракт з фронтом (Учасник 3) і агентом (Учасник 5). Приклади: mocks/geo_*.json."""

from typing import Literal

from pydantic import BaseModel

Mode = Literal["walk", "car"]
Source = Literal["zakaz", "silpo", "osm"]


class MapsUrls(BaseModel):
    walking: str
    driving: str
    transit: str


class StoreOut(BaseModel):
    store_id: str  # Zakaz — "482010105", Сільпо — uuid; OSM без цін — внутрішній "osm:n123"
    source: Source
    chain: str
    chain_name: str
    name: str
    city: str
    address: str
    lat: float
    lng: float
    place_id: str  # однаковий для магазинів в одній будівлі — групуйте маркери
    alt_store_ids: list[str]  # інші ID того самого магазину (дві філії Сільпо за однією адресою)
    has_online_prices: bool  # offers_count у каталозі >= PRICED_MIN_OFFERS
    offers_count: int | None
    online_catalog: bool  # є в Zakaz.ua / Сільпо
    has_pickup: bool


class StoresOut(BaseModel):
    count: int
    stores: list[StoreOut]


class NearbyStoreOut(StoreOut):
    confirmed: bool  # store_id був серед переданих store_ids
    in_radius: bool
    straight_km: float
    distance_km: float
    duration_min: float
    estimated: bool  # Valhalla недоступний — оцінка за прямою
    maps_urls: MapsUrls


class LatLng(BaseModel):
    lat: float
    lng: float


class NearbyOut(BaseModel):
    origin: LatLng
    mode: Mode
    radius_km: float
    radius_expanded: bool
    routing: Literal["valhalla", "mixed", "estimated"]
    recommended_store_id: str | None
    recommended_reason: Literal["confirmed_offer", "nearest_with_online_prices"] | None
    unknown_store_ids: list[str]
    count: int
    stores: list[NearbyStoreOut]


class LineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]  # [[lng, lat], …] — як чекає MapLibre / GeoJSON


class RouteOut(BaseModel):
    store_id: str
    source: Source
    chain: str
    mode: Mode
    distance_km: float
    duration_min: float
    estimated: bool
    geometry: LineString
    maps_urls: MapsUrls


class Place(BaseModel):
    label: str  # «вулиця Хрещатик, 22, Київ»
    full: str
    lat: float
    lng: float
    source: Literal["nominatim", "photon", "coords"]


class GeocodeOut(BaseModel):
    results: list[Place]


class ErrorDetail(BaseModel):
    code: str  # outside_service_area | not_found_in_service_area | geocoder_unavailable | store_not_found
    message: str  # англійською; текст для людини UI бере за code
