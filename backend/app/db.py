from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Базовий клас ORM-моделей усіх модулів. Схему створюють SQL-міграції, не create_all()."""

    # У міграціях час завжди timestamptz, тож і в ORM datetime має бути з часовим поясом.
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
        pool_pre_ping=True,
        connect_args={"ssl": "require"} if settings.db_ssl else {},
    )


# Створення engine не відкриває з'єднання: воно з'явиться при першому запиті.
engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
