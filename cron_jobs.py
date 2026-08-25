#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اجرای Jobهای زمان‌بندی‌شده از طریق Cron (cPanel / aaPanel / crontab)

استفاده:
  python cron_jobs.py backup
  python cron_jobs.py hourly
  python cron_jobs.py auto_approve
  python cron_jobs.py optimize
  python cron_jobs.py all

مثال crontab (هر ۲ دقیقه تأیید کارت، هر ساعت کسر ساعتی، هر روز بکاپ):
  */2 * * * * cd /path/to/farnoudbot && /path/to/python cron_jobs.py auto_approve >> /tmp/farnoud_cron.log 2>&1
  5 * * * *   cd /path/to/farnoudbot && /path/to/python cron_jobs.py hourly >> /tmp/farnoud_cron.log 2>&1
  15 3 * * *  cd /path/to/farnoudbot && /path/to/python cron_jobs.py backup >> /tmp/farnoud_cron.log 2>&1
  30 4 * * 0  cd /path/to/farnoudbot && /path/to/python cron_jobs.py optimize >> /tmp/farnoud_cron.log 2>&1
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from types import SimpleNamespace

# مسیر پروژه
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cron] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cron_jobs")


class _FakeContext:
    """جایگزین ContextTypes برای فراخوانی jobهای موجود."""

    def __init__(self, bot, application=None):
        self.bot = bot
        self.application = application
        self.job = None
        self.user_data = {}
        self.chat_data = {}
        self.bot_data = {}


async def _build_app():
    from config import BOT_TOKEN
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN در .env تنظیم نشده است")
    from telegram.ext import Application
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    await app.initialize()
    return app


async def job_backup():
    from handlers.group_reports import backup_job
    app = await _build_app()
    try:
        ctx = _FakeContext(app.bot, app)
        await backup_job(ctx)
        log.info("backup: done")
    finally:
        await app.shutdown()


async def job_hourly():
    from handlers.group_reports import hourly_job
    app = await _build_app()
    try:
        ctx = _FakeContext(app.bot, app)
        await hourly_job(ctx)
        log.info("hourly: done")
    finally:
        await app.shutdown()


async def job_auto_approve():
    from handlers.group_reports import auto_approve_job
    app = await _build_app()
    try:
        ctx = _FakeContext(app.bot, app)
        await auto_approve_job(ctx)
        log.info("auto_approve: done")
    finally:
        await app.shutdown()


async def job_optimize():
    """بهینه‌سازی دیتابیس + گزارش به ادمین."""
    from config import ADMIN_ID
    from services.optimize import optimize_bot_data, format_optimize_report
    from database import get_setting_sync

    # اگر در تنظیمات غیرفعال باشد (interval=0) باز هم با cron دستی قابل اجراست
    stats = optimize_bot_data()
    msg = format_optimize_report(stats)
    log.info("optimize: %s", stats)

    if ADMIN_ID:
        app = await _build_app()
        try:
            await app.bot.send_message(int(ADMIN_ID), msg, parse_mode="HTML")
        except Exception as e:
            log.warning("optimize notify admin failed: %s", e)
        finally:
            await app.shutdown()


async def job_price_schedules():
    from db_products import apply_due_price_schedules
    stats = apply_due_price_schedules()
    log.info("price_schedules: %s", stats)


JOBS = {
    "backup": job_backup,
    "hourly": job_hourly,
    "auto_approve": job_auto_approve,
    "optimize": job_optimize,
    "price_schedules": job_price_schedules,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        print("Jobs:", ", ".join(JOBS.keys()), ", all")
        sys.exit(0)

    name = sys.argv[1].strip().lower()
    if name == "all":
        names = list(JOBS.keys())
    elif name in JOBS:
        names = [name]
    else:
        print(f"Unknown job: {name}")
        print("Available:", ", ".join(JOBS.keys()), ", all")
        sys.exit(1)

    for n in names:
        log.info("running job: %s", n)
        try:
            asyncio.run(JOBS[n]())
        except Exception as e:
            log.exception("job %s failed: %s", n, e)
            # ادامه بقیه jobها در حالت all
            if name != "all":
                sys.exit(1)


if __name__ == "__main__":
    main()
