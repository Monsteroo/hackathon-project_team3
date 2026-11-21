from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.catalog import jobs

KYIV = ZoneInfo("Europe/Kyiv")


def test_nightly_etl_fires_at_3am_kyiv():
    trigger = jobs.etl_trigger()
    now = datetime(2026, 11, 21, 13, 0, tzinfo=KYIV)
    assert trigger.get_next_fire_time(None, now) == datetime(2026, 11, 22, 3, 0, tzinfo=KYIV)
    # і після переходу на літній час — так само о 03:00 за Києвом
    summer = datetime(2026, 4, 1, 12, 0, tzinfo=KYIV)
    assert trigger.get_next_fire_time(None, summer) == datetime(2026, 4, 2, 3, 0, tzinfo=KYIV)


async def test_register_adds_single_nightly_job():
    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
    scheduler.start(paused=True)
    try:
        jobs.register(scheduler)
        jobs.register(scheduler)  # replace_existing: повторна реєстрація не дублює задачу
        [job] = scheduler.get_jobs()
        assert job.id == jobs.NIGHTLY_ETL_JOB_ID
        assert job.max_instances == 1
        assert (job.next_run_time.hour, job.next_run_time.minute) == (3, 0)
        assert str(job.next_run_time.tzinfo) == "Europe/Kyiv"
    finally:
        scheduler.shutdown(wait=False)
