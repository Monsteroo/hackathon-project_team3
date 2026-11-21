"""Фонові задачі модуля catalog: нічний ETL цін (за замовчуванням щодня о 03:00 за Києвом)."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.catalog.etl.runner import run_etl
from app.config import get_settings

log = logging.getLogger(__name__)

NIGHTLY_ETL_JOB_ID = "catalog_nightly_etl"


def etl_trigger() -> CronTrigger:
    settings = get_settings()
    return CronTrigger.from_crontab(settings.etl_cron, timezone=settings.scheduler_timezone)


async def nightly_etl() -> None:
    result = await run_etl(trigger="schedule")
    log.info(
        "nightly ETL: status=%s run_id=%s offers=%s duration=%ss",
        result.get("status"),
        result.get("run_id"),
        result.get("offers_upserted"),
        result.get("duration_s"),
    )


def register(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        nightly_etl,
        etl_trigger(),
        id=NIGHTLY_ETL_JOB_ID,
        name="Catalog nightly ETL",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,  # якщо о 03:00 процес "спав", дозволяємо запуск протягом години
        replace_existing=True,
    )
