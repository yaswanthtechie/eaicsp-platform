import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs.rescreen_job import nightly_rescreen_job


scheduler = BlockingScheduler()


demo_minutes = os.getenv(
    "RESCREEN_INTERVAL_MINUTES"
)


if demo_minutes:

    trigger = {
        "trigger": "interval",
        "minutes": int(demo_minutes),
    }

else:

    trigger = {
        "trigger": CronTrigger(
            hour=2,
            minute=0,
        ),
    }


scheduler.add_job(
    nightly_rescreen_job,
    id="nightly_rescreen",
    max_instances=1,
    replace_existing=True,
    coalesce=True,
    **trigger,
)


print("Rescreen scheduler started...")


scheduler.start()