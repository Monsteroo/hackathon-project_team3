import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.auth import require_api_key
from app.catalog import jobs as catalog_jobs
from app.catalog.router import router as catalog_router
from app.config import get_settings
from app.db import SessionDep, engine
from app.geo.router import router as geo_router
from app.scheduler import shutdown_scheduler, start_scheduler
from app.voice.router import router as voice_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not get_settings().api_key_list:
        log.warning("API_KEYS is empty: protected endpoints will answer 503 until it is set in backend/.env")
    # Фонові задачі модулів: один registrar на модуль.
    start_scheduler([catalog_jobs.register])
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

    # Модулі учасників: один рядок на модуль. Усі їхні ендпоінти вимагають X-API-Key.
    app.include_router(catalog_router, dependencies=[Depends(require_api_key)])
    app.include_router(geo_router, dependencies=[Depends(require_api_key)])
    app.include_router(voice_router, dependencies=[Depends(require_api_key)])
    return app


app = create_app()
