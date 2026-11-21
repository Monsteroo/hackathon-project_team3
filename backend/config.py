"""Налаштування з оточення (.env локально, Environment Variables на Vercel)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv потрібен лише локально
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass

DATA_DIR = Path(__file__).resolve().parent / "data"

# Межі міст (lat_min, lng_min, lat_max, lng_max). Щоб повернути інші міста — додайте сюди межі
# й назву в SERVICE_CITIES (env, через кому), потім перезберіть scripts/build_stores.py.
CITY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "Київ": (50.213, 30.239, 50.591, 30.826),
}
DEFAULT_SERVICE_CITIES = "Київ"  # рішення команди 21.11: демо лише по Києву


def service_cities() -> list[str]:
    raw = os.environ.get("SERVICE_CITIES", DEFAULT_SERVICE_CITIES)
    return [c.strip() for c in raw.split(",") if c.strip()]


def service_bboxes() -> list[tuple[float, float, float, float]]:
    return [CITY_BBOX[c] for c in service_cities() if c in CITY_BBOX]


def in_service_area(lat: float, lng: float) -> bool:
    return any(b[0] <= lat <= b[2] and b[1] <= lng <= b[3] for b in service_bboxes())


# Відмінки для повідомлень: «лише по Києву», «не знайдено в Києві»
CITY_DATIVE = {"Київ": "Києву"}
CITY_LOCATIVE = {"Київ": "Києві"}


def outside_area_message() -> str:
    names = [CITY_DATIVE.get(c, f"місту {c}") for c in service_cities()]
    return f"Поки працюємо лише по {', '.join(names)}"


def not_found_in_area_message() -> str:
    names = [CITY_LOCATIVE.get(c, f"місті {c}") for c in service_cities()]
    return f"Адресу не знайдено в {', '.join(names)}. {outside_area_message()}."


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_stt_model: str
    groq_cleanup_model: str
    groq_cleanup_fallback_model: str
    geo_user_agent: str
    nominatim_url: str
    photon_url: str
    valhalla_url: str


@lru_cache
def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        groq_api_key=env("GROQ_API_KEY", ""),
        groq_stt_model=env("GROQ_STT_MODEL", "whisper-large-v3"),
        groq_cleanup_model=env("GROQ_CLEANUP_MODEL", "qwen/qwen3.8-27b"),
        groq_cleanup_fallback_model=env("GROQ_CLEANUP_FALLBACK_MODEL", "openai/gpt-oss-120b"),
        geo_user_agent=env("GEO_USER_AGENT", "voicecart-hackathon/0.1"),
        nominatim_url=env("NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/"),
        photon_url=env("PHOTON_URL", "https://photon.komoot.io").rstrip("/"),
        valhalla_url=env("VALHALLA_URL", "https://valhalla1.openstreetmap.de").rstrip("/"),
    )
