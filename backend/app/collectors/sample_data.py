import csv
import os
from datetime import date
from app.database import SessionLocal
from app.models import Stock, DailyQuote, DailyBasic, Financial

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_data")

def load_sample_data(db):
    stocks_file = os.path.join(SAMPLE_DIR, "stocks.csv")
    if not os.path.exists(stocks_file):
        return
    with open(stocks_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exists = db.query(Stock).filter_by(ts_code=row["ts_code"]).first()
            if not exists:
                db.add(Stock(
                    ts_code=row["ts_code"], symbol=row.get("symbol", ""),
                    name=row.get("name", ""), area=row.get("area", ""),
                    industry=row.get("industry", ""), market=row.get("market", ""),
                    exchange=row.get("exchange", ""), list_status="L"
                ))
        db.commit()

    quotes_file = os.path.join(SAMPLE_DIR, "daily_quotes.csv")
    if os.path.exists(quotes_file):
        with open(quotes_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                td = date.fromisoformat(row["trade_date"])
                exists = db.query(DailyQuote).filter_by(ts_code=row["ts_code"], trade_date=td).first()
                if not exists:
                    db.add(DailyQuote(
                        ts_code=row["ts_code"], trade_date=td,
                        open=float(row["open"]), high=float(row["high"]),
                        low=float(row["low"]), close=float(row["close"]),
                        pct_chg=float(row.get("pct_chg", 0)),
                        volume=float(row.get("volume", 0)),
                        adj_factor=float(row.get("adj_factor", 1.0)),
                        source="sample"
                    ))
            db.commit()

    basic_file = os.path.join(SAMPLE_DIR, "daily_basic.csv")
    if os.path.exists(basic_file):
        with open(basic_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                td = date.fromisoformat(row["trade_date"])
                exists = db.query(DailyBasic).filter_by(ts_code=row["ts_code"], trade_date=td).first()
                if not exists:
                    db.add(DailyBasic(
                        ts_code=row["ts_code"], trade_date=td,
                        close=float(row.get("close", 0)), pe=float(row.get("pe", 0)),
                        pb=float(row.get("pb", 0)), turnover_rate=float(row.get("turnover_rate", 0)),
                        source="sample"
                    ))
            db.commit()
