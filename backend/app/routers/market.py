from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Stock, DailyQuote, DailyBasic

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/overview")
def market_overview(db: Session = Depends(get_db)):
    total_stocks = db.query(Stock).filter(Stock.list_status == "L").count()
    latest_date = db.query(func.max(DailyQuote.trade_date)).scalar()
    if not latest_date:
        return dict(total_stocks=total_stocks, latest_date=None, advancers=0, decliners=0, flat=0, total_amount=0)
    advancers = db.query(DailyQuote).filter(DailyQuote.trade_date == latest_date, DailyQuote.pct_chg > 0).count()
    decliners = db.query(DailyQuote).filter(DailyQuote.trade_date == latest_date, DailyQuote.pct_chg < 0).count()
    flat = db.query(DailyQuote).filter(DailyQuote.trade_date == latest_date, DailyQuote.pct_chg == 0).count()
    total_amount = db.query(func.sum(DailyQuote.amount)).filter(DailyQuote.trade_date == latest_date).scalar() or 0
    return dict(total_stocks=total_stocks, latest_date=str(latest_date), advancers=advancers, decliners=decliners, flat=flat, total_amount=round(total_amount, 2))

@router.get("/top-movers")
def top_movers(direction: str = "up", limit: int = 10, db: Session = Depends(get_db)):
    latest_date = db.query(func.max(DailyQuote.trade_date)).scalar()
    if not latest_date:
        return []
    q = db.query(DailyQuote, Stock).join(Stock, Stock.ts_code == DailyQuote.ts_code).filter(DailyQuote.trade_date == latest_date)
    if direction == "up":
        q = q.order_by(DailyQuote.pct_chg.desc())
    else:
        q = q.order_by(DailyQuote.pct_chg.asc())
    rows = q.limit(limit).all()
    return [dict(ts_code=quote.ts_code, name=stock.name, close=quote.close, pct_chg=quote.pct_chg, volume=quote.volume) for quote, stock in rows]

@router.get("/industry-ranking")
def industry_ranking(db: Session = Depends(get_db)):
    latest_date = db.query(func.max(DailyQuote.trade_date)).scalar()
    if not latest_date:
        return []
    results = db.query(
        Stock.industry,
        func.count(DailyQuote.id).label("count"),
        func.avg(DailyQuote.pct_chg).label("avg_pct_chg")
    ).join(DailyQuote, DailyQuote.ts_code == Stock.ts_code).filter(
        DailyQuote.trade_date == latest_date,
        Stock.industry.isnot(None)
    ).group_by(Stock.industry).order_by(func.avg(DailyQuote.pct_chg).desc()).all()
    return [dict(industry=r.industry, count=r.count, avg_pct_chg=round(r.avg_pct_chg, 4) if r.avg_pct_chg else 0) for r in results]
