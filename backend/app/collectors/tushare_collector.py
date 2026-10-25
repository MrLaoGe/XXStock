import logging
import time
from datetime import date
from app.database import SessionLocal
from app.models import (Stock, DailyQuote, DailyBasic, Financial,
                        TradeCalendar, CollectionLog)
from app.config import settings

logger = logging.getLogger(__name__)

def _get_pro():
    import tushare as ts
    ts.set_token(settings.TUSHARE_TOKEN)
    return ts.pro_api()

def _log(db, api_name, params, status, rows, error, duration_ms, source):
    db.add(CollectionLog(api_name=api_name, params=params, status=status,
                         rows_affected=rows, error_message=error,
                         duration_ms=duration_ms, source=source))
    db.commit()

def _upsert(model, db, rows, keys):
    count = 0
    for r in rows:
        filters = dict((k, r.get(k)) for k in keys)
        existing = db.query(model).filter_by(**filters).first()
        if existing:
            for k, v in r.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
        else:
            db.add(model(**dict((k, v) for k, v in r.items() if hasattr(model, k))))
        count += 1
    db.commit()
    return count

def _parse_date(s):
    if not s or s == "None":
        return None
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))

def collect_stock_basic(db):
    start = time.time()
    try:
        pro = _get_pro()
        df = pro.stock_basic(exchange='', list_status='L',
                             fields='ts_code,symbol,name,area,industry,market,exchange,list_date,list_status')
        rows = []
        for _, r in df.iterrows():
            rows.append(dict(
                ts_code=r["ts_code"], symbol=r["symbol"], name=r["name"],
                area=r.get("area"), industry=r.get("industry"),
                market=r.get("market"), exchange=r.get("exchange"),
                list_date=_parse_date(str(r.get("list_date", ""))),
                list_status=r.get("list_status", "L")
            ))
        count = _upsert(Stock, db, rows, ["ts_code"])
        _log(db, "stock_basic", dict(), "success", count, None, int((time.time()-start)*1000), "tushare")
        return count
    except Exception as e:
        _log(db, "stock_basic", dict(), "failed", 0, str(e), int((time.time()-start)*1000), "tushare")
        raise

def collect_trade_calendar(db, start_date=None, end_date=None):
    start = time.time()
    try:
        pro = _get_pro()
        df = pro.trade_cal(exchange='SSE', start_date=start_date or "20200101",
                           end_date=end_date or date.today().strftime("%Y%m%d"),
                           fields='exchange,cal_date,is_open,pretrade_date')
        rows = []
        for _, r in df.iterrows():
            rows.append(dict(
                exchange=r["exchange"],
                cal_date=_parse_date(str(r["cal_date"])),
                is_open=int(r["is_open"]),
                pretrade_date=_parse_date(str(r.get("pretrade_date", "")))
            ))
        count = _upsert(TradeCalendar, db, rows, ["exchange", "cal_date"])
        _log(db, "trade_cal", dict(), "success", count, None, int((time.time()-start)*1000), "tushare")
        return count
    except Exception as e:
        _log(db, "trade_cal", dict(), "failed", 0, str(e), int((time.time()-start)*1000), "tushare")
        raise

def collect_daily(db, ts_code, start_date, end_date):
    start = time.time()
    try:
        pro = _get_pro()
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        adj = pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
        adj_map = dict()
        for _, r in adj.iterrows():
            adj_map[r["trade_date"]] = r["adj_factor"]
        rows = []
        for _, r in df.iterrows():
            td = _parse_date(str(r["trade_date"]))
            rows.append(dict(
                ts_code=ts_code, trade_date=td,
                open=r["open"], high=r["high"], low=r["low"], close=r["close"],
                pre_close=r.get("pre_close"), change=r.get("change"),
                pct_chg=r.get("pct_chg"), volume=r.get("vol"), amount=r.get("amount"),
                adj_factor=float(adj_map.get(r["trade_date"], 1.0)),
                source="tushare"
            ))
        count = _upsert(DailyQuote, db, rows, ["ts_code", "trade_date"])
        _log(db, "daily", dict(ts_code=ts_code), "success", count, None, int((time.time()-start)*1000), "tushare")
        return count
    except Exception as e:
        _log(db, "daily", dict(ts_code=ts_code), "failed", 0, str(e), int((time.time()-start)*1000), "tushare")
        raise

def collect_daily_basic(db, trade_date):
    start = time.time()
    try:
        pro = _get_pro()
        df = pro.daily_basic(trade_date=trade_date,
                             fields='ts_code,trade_date,close,turnover_rate,pe,pe_ttm,pb,total_share,float_share,total_mv,circ_mv')
        rows = []
        for _, r in df.iterrows():
            rows.append(dict(
                ts_code=r["ts_code"], trade_date=_parse_date(str(r["trade_date"])),
                close=r.get("close"), turnover_rate=r.get("turnover_rate"),
                pe=r.get("pe"), pe_ttm=r.get("pe_ttm"), pb=r.get("pb"),
                total_share=r.get("total_share"), float_share=r.get("float_share"),
                total_mv=r.get("total_mv"), circ_mv=r.get("circ_mv"),
                source="tushare"
            ))
        count = _upsert(DailyBasic, db, rows, ["ts_code", "trade_date"])
        _log(db, "daily_basic", dict(trade_date=trade_date), "success", count, None, int((time.time()-start)*1000), "tushare")
        return count
    except Exception as e:
        _log(db, "daily_basic", dict(trade_date=trade_date), "failed", 0, str(e), int((time.time()-start)*1000), "tushare")
        raise

def collect_financial(db, ts_code):
    start = time.time()
    try:
        pro = _get_pro()
        df = pro.fina_indicator(ts_code=ts_code,
                                fields='ts_code,period,revenue,operate_profit,total_profit,net_profit,total_assets,total_liab,total_equity,roe,roa,grossprofit_margin,netprofit_margin,eps,bps')
        rows = []
        for _, r in df.iterrows():
            rows.append(dict(
                ts_code=ts_code, period=str(r["period"]),
                revenue=r.get("revenue"), operate_profit=r.get("operate_profit"),
                total_profit=r.get("total_profit"), net_profit=r.get("net_profit"),
                total_assets=r.get("total_assets"), total_liab=r.get("total_liab"),
                total_equity=r.get("total_equity"), roe=r.get("roe"), roa=r.get("roa"),
                grossprofit_margin=r.get("grossprofit_margin"),
                netprofit_margin=r.get("netprofit_margin"),
                eps=r.get("eps"), bps=r.get("bps"),
                source="tushare"
            ))
        count = _upsert(Financial, db, rows, ["ts_code", "period"])
        _log(db, "fina_indicator", dict(ts_code=ts_code), "success", count, None, int((time.time()-start)*1000), "tushare")
        return count
    except Exception as e:
        _log(db, "fina_indicator", dict(ts_code=ts_code), "failed", 0, str(e), int((time.time()-start)*1000), "tushare")
        raise
