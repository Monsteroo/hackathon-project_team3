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
