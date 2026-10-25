import logging
import time
from datetime import datetime
from app.database import SessionLocal
from app.models import Announcement

logger = logging.getLogger(__name__)

def collect_announcements_akshare(db, ts_code):
    start = time.time()
    try:
        import akshare as ak
        df = ak.stock_notice_report(symbol=ts_code.split(".")[0])
        count = 0
        for _, r in df.head(20).iterrows():
            title = str(r.get("公告标题", ""))
            url = str(r.get("公告链接", ""))
            pub = str(r.get("公告日期", ""))
            if not title:
                continue
            pub_date = None
            try:
                pub_date = datetime.strptime(pub[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
            existing = db.query(Announcement).filter_by(ts_code=ts_code, title=title).first()
            if not existing:
                db.add(Announcement(ts_code=ts_code, title=title, url=url, publish_date=pub_date, source="akshare"))
                count += 1
        db.commit()
        return count
    except Exception as e:
        logger.warning("AKShare announcements failed: %s", e)
        return 0
