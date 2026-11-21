import importlib
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.auth import require_api_key
from app.config import get_settings
from app.db import SessionDep, engine
from app.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("app")

# Модулі учасників: назва -> роутер і (необов'язково) registrar фонових задач.
# Новий модуль — новий рядок тут. Які модулі підключати, задає ENABLED_MODULES (за замовчуванням усі),
# і імпортуються лише ввімкнені: деплой одного модуля не тягне налаштувань і секретів інших.
MODULES: dict[str, dict[str, str]] = {
    "catalog": {"router": "app.catalog.router:router", "jobs": "app.catalog.jobs:register"},  # Учасник 2
    "geo": {"router": "app.geo.router:router"},  # Учасник 1
    "voice": {"router": "app.voice.router:router"},  # Учасник 1
    "agent": {"router": "app.agent.router:router"},  # Учасник 5: потребує catalog і geo (викликає їхні service.py)
}


def _load(path: str):
    module_path, attr = path.split(":")
    return getattr(importlib.import_module(module_path), attr)


def enabled_modules() -> list[str]:
    names = get_settings().enabled_module_list
    unknown = [name for name in names if name not in MODULES]
    if unknown:
        raise RuntimeError(f"unknown ENABLED_MODULES: {', '.join(unknown)} (known: {', '.join(MODULES)})")
    return names


def _job_registrars() -> list[Callable]:
    return [_load(MODULES[name]["jobs"]) for name in enabled_modules() if "jobs" in MODULES[name]]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not get_settings().api_key_list:
        log.warning("API_KEYS is empty: protected endpoints will answer 503 until it is set in backend/.env")
    # Фонові задачі ввімкнених модулів: один registrar на модуль.
    start_scheduler(_job_registrars())
    yield
    shutdown_scheduler()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="VoiceCart API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db", tags=["health"], dependencies=[Depends(require_api_key)])
    async def health_db(session: SessionDep) -> dict[str, str]:
        try:
            await session.execute(text("select 1"))
        except Exception as exc:  # будь-яка помилка БД означає "недоступна"
            raise HTTPException(status_code=503, detail=f"database unavailable: {type(exc).__name__}") from exc
        return {"status": "ok"}

    # Роутери ввімкнених модулів. Усі їхні ендпоінти вимагають X-API-Key.
    names = enabled_modules()
    for name in names:
        router: APIRouter = _load(MODULES[name]["router"])
        app.include_router(router, dependencies=[Depends(require_api_key)])
    log.info("enabled modules: %s", ", ".join(names) or "none")
    return app


app = create_app()
