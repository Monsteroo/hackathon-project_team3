from functools import lru_cache

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
    enabled_modules: str = "catalog,geo,voice"

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

    @property
    def api_key_list(self) -> list[str]:
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def enabled_module_list(self) -> list[str]:
        return [name.strip() for name in self.enabled_modules.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
