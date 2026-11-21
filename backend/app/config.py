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

    # Планувальник фонових задач у процесі FastAPI
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Kyiv"

    # Нічний ETL каталогу
    etl_cron: str = "0 3 * * *"
    etl_city: str = "Київ"
    etl_concurrency: int = 5
    etl_zakaz_store_limit: int | None = None
    etl_silpo_branch_limit: int | None = None

    @property
    def api_key_list(self) -> list[str]:
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
