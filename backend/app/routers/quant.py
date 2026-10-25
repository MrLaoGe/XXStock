from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DailyQuote, DailyBasic, BacktestResult
from app.quant.backtest import run_backtest, screen_stocks

router = APIRouter(prefix="/api/quant", tags=["quant"])

class BacktestRequest(BaseModel):
    ts_code: str
    strategy: str = "dual_ma"
    params: dict = dict()
    start_date: str = ""
    end_date: str = ""

@router.post("/backtest")
def backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    q = db.query(DailyQuote).filter(DailyQuote.ts_code == req.ts_code)
    if req.start_date:
        q = q.filter(DailyQuote.trade_date >= date.fromisoformat(req.start_date))
    if req.end_date:
        q = q.filter(DailyQuote.trade_date <= date.fromisoformat(req.end_date))
    quotes = q.order_by(DailyQuote.trade_date).all()
    if not quotes:
        raise HTTPException(404, "No quote data for this stock")
    basics = dict()
    basic_rows = db.query(DailyBasic).filter(DailyBasic.ts_code == req.ts_code).all()
    for b in basic_rows:
        basics[str(b.trade_date)] = dict(pe_ttm=b.pe_ttm, pb=b.pb)

    import pandas as pd
    df = pd.DataFrame([dict(
        trade_date=str(q_.trade_date), open=q_.open, high=q_.high,
        low=q_.low, close=q_.close, pct_chg=q_.pct_chg,
        pe_ttm=basics.get(str(q_.trade_date), dict()).get("pe_ttm"),
        pb=basics.get(str(q_.trade_date), dict()).get("pb")
    ) for q_ in quotes])

    result = run_backtest(df, req.strategy, req.params)
    br = BacktestResult(
        strategy_name=req.strategy, params=req.params,
        start_date=date.fromisoformat(df["trade_date"].iloc[0]) if len(df) > 0 else None,
        end_date=date.fromisoformat(df["trade_date"].iloc[-1]) if len(df) > 0 else None,
        total_return=result["total_return"], annual_return=result["annual_return"],
        max_drawdown=result["max_drawdown"], sharpe_ratio=result["sharpe_ratio"],
        win_rate=result["win_rate"], equity_curve=result["equity_curve"],
        trades=result["trades"]
    )
    db.add(br)
    db.commit()
    db.refresh(br)
    return dict(id=br.id, **result)

class ScreenRequest(BaseModel):
    strategy: str = "low_valuation"
    params: dict = dict()

@router.post("/screen")
def screen(req: ScreenRequest, db: Session = Depends(get_db)):
    from sqlalchemy import func as sfunc
    latest_date = db.query(sfunc.max(DailyBasic.trade_date)).scalar()
    if not latest_date:
        raise HTTPException(404, "No daily basic data")
    rows = db.query(DailyBasic, Stock).join(Stock, Stock.ts_code == DailyBasic.ts_code).filter(DailyBasic.trade_date == latest_date).all()
    stock_data = []
    for basic, stock in rows:
        stock_data.append(dict(ts_code=basic.ts_code, name=stock.name, close=basic.close, pe_ttm=basic.pe_ttm, pb=basic.pb))
    results = screen_stocks(stock_data, req.strategy, req.params)
    return dict(latest_date=str(latest_date), results=results)

@router.get("/backtest/history")
def backtest_history(limit: int = 20, db: Session = Depends(get_db)):
    results = db.query(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit).all()
    return [dict(id=r.id, strategy_name=r.strategy_name, params=r.params,
                 total_return=r.total_return, annual_return=r.annual_return,
                 max_drawdown=r.max_drawdown, sharpe_ratio=r.sharpe_ratio, win_rate=r.win_rate,
                 created_at=str(r.created_at)) for r in results]
