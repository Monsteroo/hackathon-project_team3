"""Спільний планувальник фонових задач (APScheduler) у процесі FastAPI.

Кожен модуль реєструє свої задачі функцією register(scheduler), а сам планувальник стартує в lifespan
застосунку. Якщо працює кілька процесів (кілька учасників підняли сервер або uvicorn --workers N), задача
стартує в кожному з них. Від подвійного виконання захищається сама задача: ETL, наприклад, бере pg_advisory_lock.
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler(registrars: list[Callable[[AsyncIOScheduler], None]]) -> AsyncIOScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        log.info("scheduler disabled (SCHEDULER_ENABLED=false)")
        return None
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    for register in registrars:
        register(scheduler)
    scheduler.start()
    for job in scheduler.get_jobs():
        log.info("scheduled job %s, next run at %s", job.id, job.next_run_time)
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
