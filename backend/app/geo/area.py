"""Зона обслуговування демо: міста з `SERVICE_CITIES` і їхні межі. Дані модуля — у `app/geo/data/`."""

from pathlib import Path

from app.config import get_settings

DATA_DIR = Path(__file__).resolve().parent / "data"

# Межі міст (lat_min, lng_min, lat_max, lng_max). Щоб повернути інші міста — додайте сюди межі,
# назву в SERVICE_CITIES і перезберіть довідник: `uv run python -m app.geo.build_stores`.
CITY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "Київ": (50.213, 30.239, 50.591, 30.826),
}


def service_cities() -> list[str]:
    return [c.strip() for c in get_settings().service_cities.split(",") if c.strip()]


def service_bboxes() -> list[tuple[float, float, float, float]]:
    return [CITY_BBOX[c] for c in service_cities() if c in CITY_BBOX]


def area_box() -> tuple[float, float, float, float] | None:
    """Обгортка над усіма містами демо."""
    boxes = service_bboxes()
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def in_service_area(lat: float, lng: float) -> bool:
    return any(b[0] <= lat <= b[2] and b[1] <= lng <= b[3] for b in service_bboxes())


def outside_area_detail() -> dict[str, str]:
    """`detail` англійською (правило команди); український текст UI бере за `code` (див. HANDOFF.md)."""
    return {"code": "outside_service_area", "message": f"service area is limited to: {', '.join(service_cities())}"}
