from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Налаштування з env / backend/.env. Нову змінну додавай також у .env.example."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voicecart"
    db_ssl: bool = False
    db_pool_size: int = 5
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Ключі доступу до API (заголовок X-API-Key), через кому: окремий ключ на кожного клієнта
    # (фронт, агент, Postman), щоб будь-який можна було відкликати, не чіпаючи решту.
    # Порожньо означає, що захищені ендпоінти відповідають 503, а не відкриваються всім.
    api_keys: str = ""

    # Які модулі підключати (через кому). За замовчуванням усі; для окремого деплою одного модуля,
    # напр. каталогу, — ENABLED_MODULES=catalog. Список модулів — MODULES у app/main.py.
    enabled_modules: str = "catalog,geo,voice,agent"

    # Планувальник фонових задач у процесі FastAPI
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Kyiv"

    # Нічний ETL каталогу
    etl_cron: str = "0 3 * * *"
    etl_city: str = "Київ"
    etl_concurrency: int = 5
    etl_zakaz_store_limit: int | None = None
    etl_silpo_branch_limit: int | None = None

    # Модуль geo (Учасник 1): магазини поруч, маршрути, геокодинг
    service_cities: str = "Київ"  # міста демо через кому; межі — app/geo/area.py
    priced_min_offers: int = 50  # «є ціни» = offers_count у каталозі >= порогу
    geo_user_agent: str = "voicecart-hackathon/0.1"  # Nominatim вимагає контакт у User-Agent
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    photon_url: str = "https://photon.komoot.io"
    valhalla_url: str = "https://valhalla1.openstreetmap.de"

    # Модуль voice (Учасник 1): голос → текст (Groq)
    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3"
    groq_cleanup_model: str = "qwen/qwen3.8-27b"
    groq_cleanup_fallback_model: str = "openai/gpt-oss-120b"
    voice_rate_limit_per_min: int = 10  # запитів на IP до /voice/*
    # Агент (Учасник 5): LLM для розбору запиту. Без ключа обраного провайдера працює парсер на правилах.
    llm_provider: Literal["anthropic", "openai_compat"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_effort: Literal["low", "medium", "high"] = "low"
    # OpenAI-сумісні провайдери (Gemini, Groq, Grok): LLM_PROVIDER=openai_compat
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_reasoning_effort: str = "low"
    llm_timeout_s: float = 15.0
    # Запасний пошук магазинів поруч (якщо модуль geo недоступний)
    agent_radius_walk_km: float = 1.5
    agent_radius_car_km: float = 5.0
    agent_stores_per_chain: int = 2
    # Smart Split показуємо, лише якщо він заощаджує щонайменше стільки гривень
    agent_smart_split_min_saving: float = 30.0

    @property
    def api_key_list(self) -> list[str]:
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def enabled_module_list(self) -> list[str]:
        return [name.strip() for name in self.enabled_modules.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
