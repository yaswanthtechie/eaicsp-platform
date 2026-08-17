from apscheduler.schedulers.blocking import BlockingScheduler

from app.jobs.rescreen_job import nightly_rescreen_job


scheduler = BlockingScheduler()


scheduler.add_job(
    nightly_rescreen_job,
    "interval",
    minutes=5,
    id="nightly_rescreen",
    max_instances=1,
    replace_existing=True,
    coalesce=True,
)


print("Rescreen scheduler started...")


scheduler.start()