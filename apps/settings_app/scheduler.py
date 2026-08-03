"""
APScheduler setup — runs backup and report jobs automatically.
Called from AppConfig.ready() to start when Django starts.
Requires: pip install django-apscheduler
"""
import logging

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

from django.conf import settings

logger = logging.getLogger('scheduler')

_scheduler = None


def start_scheduler():
    """Start the background scheduler with backup and report jobs."""
    global _scheduler

    if not HAS_APSCHEDULER:
        logger.info("APScheduler not installed — automated emails disabled. Install with: pip install django-apscheduler")
        return

    if _scheduler and _scheduler.running:
        return  # Already running

    _scheduler = BackgroundScheduler(timezone='Asia/Karachi')

    # Job 1: Daily backup — runs at 11:00 PM Pakistan time
    _scheduler.add_job(
        _run_backup,
        trigger=CronTrigger(hour=23, minute=0, timezone='Asia/Karachi'),
        id='daily_backup',
        name='Daily Database Backup Email',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,  # Allow 1 hour grace if missed
    )

    # Job 2: Morning agenda — 7:00 AM Pakistan time
    _scheduler.add_job(
        _run_morning_report,
        trigger=CronTrigger(hour=7, minute=0, timezone='Asia/Karachi'),
        id='morning_report',
        name='Morning Agenda Report',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Job 3: Evening summary — 10:00 PM Pakistan time
    _scheduler.add_job(
        _run_evening_report,
        trigger=CronTrigger(hour=22, minute=0, timezone='Asia/Karachi'),
        id='evening_report',
        name='Evening Summary Report',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("Scheduler started — backup at 11PM, morning agenda at 7AM, evening summary at 10PM (Asia/Karachi)")


def _run_backup():
    """Execute backup with retry on failure."""
    import time
    from .backup_email import send_backup_email

    for attempt in range(3):
        try:
            result = send_backup_email()
            if result:
                logger.info("Backup email sent successfully")
                return
            else:
                logger.warning(f"Backup attempt {attempt+1} failed, retrying in 5 min...")
        except Exception as e:
            logger.error(f"Backup attempt {attempt+1} error: {e}")
        time.sleep(300)  # Wait 5 minutes between retries

    logger.error("All 3 backup attempts failed")


def _run_morning_report():
    """Execute morning agenda report with retry."""
    import time
    from .backup_email import send_morning_report

    for attempt in range(3):
        try:
            result = send_morning_report()
            if result:
                logger.info("Morning agenda report sent successfully")
                return
            else:
                logger.warning(f"Morning report attempt {attempt+1} failed, retrying in 2 min...")
        except Exception as e:
            logger.error(f"Morning report attempt {attempt+1} error: {e}")
        time.sleep(120)

    logger.error("All 3 morning report attempts failed")


def _run_evening_report():
    """Execute evening summary report with retry."""
    import time
    from .backup_email import send_evening_report

    for attempt in range(3):
        try:
            result = send_evening_report()
            if result:
                logger.info("Evening summary report sent successfully")
                return
            else:
                logger.warning(f"Evening report attempt {attempt+1} failed, retrying in 2 min...")
        except Exception as e:
            logger.error(f"Evening report attempt {attempt+1} error: {e}")
        time.sleep(120)

    logger.error("All 3 evening report attempts failed")
