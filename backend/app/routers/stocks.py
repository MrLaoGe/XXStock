from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Stock, DailyQuote, DailyBasic, Financial, Announcement, NewsItem

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

@router.get("/")
def list_stocks(skip: int = 0, limit: int = 50, search: str = "", db: Session = Depends(get_db)):
    q = db.query(Stock).filter(Stock.list_status == "L")
    if search:
        q = q.filter(Stock.name.contains(search) | Stock.ts_code.contains(search))
    total = q.count()
    stocks = q.order_by(Stock.ts_code).offset(skip).limit(limit).all()
    return dict(total=total, items=[dict(
        ts_code=s.ts_code, name=s.name, industry=s.industry,
        area=s.area, market=s.market
    ) for s in stocks])

@router.get("/{ts_code}")
def get_stock(ts_code: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.ts_code == ts_code).first()
    if not stock:
        raise HTTPException(404, "Stock not found")
    latest_quote = db.query(DailyQuote).filter(DailyQuote.ts_code == ts_code).order_by(DailyQuote.trade_date.desc()).first()
    latest_basic = db.query(DailyBasic).filter(DailyBasic.ts_code == ts_code).order_by(DailyBasic.trade_date.desc()).first()
    return dict(
        ts_code=stock.ts_code, name=stock.name, industry=stock.industry,
        area=stock.area, market=stock.market, exchange=stock.exchange,
        list_date=str(stock.list_date) if stock.list_date else None,
        latest_close=latest_quote.close if latest_quote else None,
        latest_pct_chg=latest_quote.pct_chg if latest_quote else None,
        pe=latest_basic.pe_ttm if latest_basic else None,
        pb=latest_basic.pb if latest_basic else None,
        total_mv=latest_basic.total_mv if latest_basic else None
    )

@router.get("/{ts_code}/quotes")
def get_quotes(ts_code: str, start_date: str = "", end_date: str = "", limit: int = 250, db: Session = Depends(get_db)):
    q = db.query(DailyQuote).filter(DailyQuote.ts_code == ts_code)
    if start_date:
        q = q.filter(DailyQuote.trade_date >= date.fromisoformat(start_date))
    if end_date:
        q = q.filter(DailyQuote.trade_date <= date.fromisoformat(end_date))
    quotes = q.order_by(DailyQuote.trade_date).limit(limit).all()
    return [dict(
        date=str(q_.trade_date), open=q_.open, high=q_.high, low=q_.low,
        close=q_.close, pct_chg=q_.pct_chg, volume=q_.volume, amount=q_.amount
    ) for q_ in quotes]

@router.get("/{ts_code}/financials")
def get_financials(ts_code: str, limit: int = 12, db: Session = Depends(get_db)):
    fins = db.query(Financial).filter(Financial.ts_code == ts_code).order_by(Financial.period.desc()).limit(limit).all()
    return [dict(
        period=f.period, revenue=f.revenue, net_profit=f.net_profit,
        roe=f.roe, roa=f.roa, eps=f.eps, bps=f.bps,
        gross_margin=f.grossprofit_margin, net_margin=f.netprofit_margin
    ) for f in fins]

@router.get("/{ts_code}/news")
def get_news(ts_code: str, limit: int = 20, db: Session = Depends(get_db)):
    anns = db.query(Announcement).filter(Announcement.ts_code == ts_code).order_by(Announcement.publish_date.desc()).limit(limit).all()
    news = db.query(NewsItem).filter(NewsItem.ts_code == ts_code).order_by(NewsItem.publish_date.desc()).limit(limit).all()
    return dict(announcements=[dict(id=a.id, title=a.title, url=a.url, date=str(a.publish_date) if a.publish_date else None, source=a.source) for a in anns],
                news=[dict(id=n.id, title=n.title, url=n.url, date=str(n.publish_date) if n.publish_date else None, source=n.source) for n in news])
