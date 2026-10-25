from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def daily_collect():
    from app.database import SessionLocal
    from app.collectors.tushare_collector import (collect_stock_basic,
                                                   collect_daily_basic, collect_trade_calendar)
    from datetime import date
    db = SessionLocal()
    try:
        logger.info("Scheduler: starting daily collection")
        collect_stock_basic(db)
        collect_trade_calendar(db)
        trade_date = date.today().strftime("%Y%m%d")
        collect_daily_basic(db, trade_date)
        logger.info("Scheduler: daily collection done")
    except Exception as e:
        logger.error("Scheduler error: %s", e)
    finally:
        db.close()

scheduler = BackgroundScheduler()

def start_scheduler():
    if not settings.SCHEDULER_ENABLED:
        return
    hour, minute = settings.COLLECTION_TIME.split(":")
    scheduler.add_job(daily_collect, CronTrigger(hour=int(hour), minute=int(minute)), id="daily_collect")
    scheduler.start()
    logger.info("Scheduler started with daily collection at %s", settings.COLLECTION_TIME)
