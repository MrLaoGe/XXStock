import sys
from datetime import date, timedelta
from app.database import SessionLocal
from app.collectors.tushare_collector import (
    collect_stock_basic, collect_trade_calendar, collect_daily, collect_daily_basic
)

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    db = SessionLocal()
    try:
        n = collect_stock_basic(db)
        print("stock_basic:", n)
        n = collect_trade_calendar(db)
        print("trade_cal:", n)
        # recent daily_basic for last few trade days
        for i in range(5):
            d = (date.today() - timedelta(days=i)).strftime("%Y%m%d")
            try:
                n = collect_daily_basic(db, d)
                print("daily_basic", d, ":", n)
            except Exception as e:
                print("daily_basic", d, "failed:", str(e)[:120])
        # daily quotes for a starter watchlist over the window
        codes = [c[0] for c in db.query(db.query(__import__('app.models', fromlist=['Stock']).Stock).limit(0)).all()] if False else [
            "000001.SZ","600519.SH","300750.SZ","601318.SH","000858.SZ",
            "600036.SH","000333.SZ","600276.SH","601899.SH","000651.SZ"
        ]
        start = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
        end = date.today().strftime("%Y%m%d")
        for code in codes:
            try:
                n = collect_daily(db, code, start, end)
                print("daily", code, ":", n)
            except Exception as e:
                print("daily", code, "failed:", str(e)[:120])
    finally:
        db.close()
