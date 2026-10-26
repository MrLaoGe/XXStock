from sqlalchemy import (Column, Integer, String, Float, Date, DateTime,
                         Text, JSON, UniqueConstraint)
from sqlalchemy.sql import func
from app.database import Base

class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), unique=True, nullable=False, index=True)
    symbol = Column(String(8))
    name = Column(String(30))
    area = Column(String(20))
    industry = Column(String(30))
    market = Column(String(10))
    exchange = Column(String(10))
    list_date = Column(Date)
    delist_date = Column(Date)
    list_status = Column(String(1), default="L")
    created_at = Column(DateTime, server_default=func.now())

class SkillInstall(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True)
    skill_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    version = Column(String(50), nullable=False)
    api_version = Column(String(50), nullable=False)
    path = Column(String(1000), nullable=False)
    entrypoint = Column(String(500), nullable=False)
    status = Column(String(20), default="installed")
    enabled = Column(Integer, default=1)
    manifest = Column(JSON, nullable=False)
    installed_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SkillRun(Base):
    __tablename__ = "skill_runs"
    id = Column(Integer, primary_key=True)
    skill_id = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    duration_ms = Column(Integer)
    input_payload = Column(JSON)
    output_payload = Column(JSON)
    error_message = Column(Text)
    stderr = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class SkillInstallJob(Base):
    __tablename__ = "skill_install_jobs"
    id = Column(String(36), primary_key=True)
    status = Column(String(20), nullable=False, default="queued")
    skill_id = Column(String(100))
    version = Column(String(50))
    message = Column(Text)
    archive_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    pre_close = Column(Float)
    change = Column(Float)
    pct_chg = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    adj_factor = Column(Float)
    source = Column(String(20), default="tushare")
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("ts_code", "trade_date", name="uq_quote_code_date"),)

class DailyBasic(Base):
    __tablename__ = "daily_basic"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    close = Column(Float)
    turnover_rate = Column(Float)
    pe = Column(Float)
    pe_ttm = Column(Float)
    pb = Column(Float)
    total_share = Column(Float)
    float_share = Column(Float)
    total_mv = Column(Float)
    circ_mv = Column(Float)
    source = Column(String(20), default="tushare")
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("ts_code", "trade_date", name="uq_basic_code_date"),)

class Financial(Base):
    __tablename__ = "financials"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), nullable=False, index=True)
    period = Column(String(8), nullable=False, index=True)
    revenue = Column(Float)
    operate_profit = Column(Float)
    total_profit = Column(Float)
    net_profit = Column(Float)
    total_assets = Column(Float)
    total_liab = Column(Float)
    total_equity = Column(Float)
    roe = Column(Float)
    roa = Column(Float)
    grossprofit_margin = Column(Float)
    netprofit_margin = Column(Float)
    eps = Column(Float)
    bps = Column(Float)
    source = Column(String(20), default="tushare")
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("ts_code", "period", name="uq_fin_code_period"),)

class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), index=True)
    title = Column(String(200))
    url = Column(String(500))
    publish_date = Column(Date)
    summary = Column(Text)
    source = Column(String(20), default="tushare")
    created_at = Column(DateTime, server_default=func.now())

class NewsItem(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), index=True)
    title = Column(String(200))
    url = Column(String(500))
    publish_date = Column(Date)
    content = Column(Text)
    summary = Column(Text)
    source = Column(String(20), default="akshare")
    created_at = Column(DateTime, server_default=func.now())

class TradeCalendar(Base):
    __tablename__ = "trade_calendar"
    id = Column(Integer, primary_key=True)
    exchange = Column(String(10), default="SSE")
    cal_date = Column(Date, nullable=False, index=True)
    is_open = Column(Integer, default=1)
    pretrade_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("exchange", "cal_date", name="uq_cal_ex_date"),)

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(50), nullable=False)
    params = Column(JSON)
    start_date = Column(Date)
    end_date = Column(Date)
    total_return = Column(Float)
    annual_return = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    win_rate = Column(Float)
    equity_curve = Column(JSON)
    trades = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(12), index=True)
    report_type = Column(String(20), default="stock_report")
    content = Column(Text)
    references = Column(JSON)
    model_used = Column(String(50))
    status = Column(String(10), default="completed")
    created_at = Column(DateTime, server_default=func.now())

class CollectionLog(Base):
    __tablename__ = "collection_logs"
    id = Column(Integer, primary_key=True)
    api_name = Column(String(50))
    params = Column(JSON)
    status = Column(String(10))
    rows_affected = Column(Integer, default=0)
    error_message = Column(Text)
    duration_ms = Column(Integer)
    source = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
