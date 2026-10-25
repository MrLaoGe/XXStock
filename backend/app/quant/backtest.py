import math
import numpy as np
import pandas as pd

COMMISSION_RATE = 0.0003
SLIPPAGE_RATE = 0.001
ANNUAL_TRADING_DAYS = 244

def run_backtest(df, strategy_name, params=None):
    """df: DataFrame with columns trade_date, open, high, low, close, pct_chg.
    Returns dict of metrics."""
    params = params or dict()
    df = df.sort_values("trade_date").reset_index(drop=True).copy()
    if len(df) < 3:
        return dict(total_return=0, annual_return=0, max_drawdown=0, sharpe_ratio=0, win_rate=0, equity_curve=[], trades=[])

    close = df["close"].values
    dates = df["trade_date"].astype(str).tolist()

    if strategy_name == "dual_ma":
        short = params.get("short_window", 5)
        long_w = params.get("long_window", 20)
        ma_short = pd.Series(close).rolling(short).mean().values
        ma_long = pd.Series(close).rolling(long_w).mean().values
        signals = np.where(np.nan_to_num(ma_short, nan=0) > np.nan_to_num(ma_long, nan=0), 1, 0)
    elif strategy_name == "momentum":
        window = params.get("lookback", 20)
        mom = pd.Series(close).pct_change(window).values
        threshold = params.get("threshold", 0.05)
        signals = np.where(np.nan_to_num(mom, nan=0) > threshold, 1, 0)
    elif strategy_name == "low_valuation":
        pe = df.get("pe_ttm", pd.Series([np.nan]*len(df))).values
        pb = df.get("pb", pd.Series([np.nan]*len(df))).values
        score = np.nan_to_num(pe, nan=1e9) + np.nan_to_num(pb, nan=1e9) * 10
        median_score = np.nanmedian(score)
        signals = np.where(score < median_score, 1, 0)
    else:
        signals = np.ones(len(df))

    position = 0
    cash = 1.0
    equity = []
    trades = []
    n = len(close)

    for i in range(n):
        prev_signal = signals[i-1] if i > 0 else 0
        signal = signals[i]

        # T+1: only sell on next day after signal change
        if signal != prev_signal and position > 0 and signal == 0:
            sell_price = close[i] * (1 - SLIPPAGE_RATE)
            cash = position * sell_price * (1 - COMMISSION_RATE)
            trades.append(dict(date=dates[i], action="sell", price=sell_price))
            position = 0
        elif signal == 1 and position == 0:
            buy_price = close[i] * (1 + SLIPPAGE_RATE)
            position = cash * (1 - COMMISSION_RATE) / buy_price
            cash = 0
            trades.append(dict(date=dates[i], action="buy", price=buy_price))

        equity_value = cash + position * close[i]
        equity.append(dict(date=dates[i], value=round(equity_value, 6)))

    total_return = (equity[-1]["value"] / equity[0]["value"] - 1) if len(equity) > 1 else 0
    n_days = len(equity)
    annual_return = (1 + total_return) ** (ANNUAL_TRADING_DAYS / max(n_days, 1)) - 1 if n_days > 0 else 0

    values = [e["value"] for e in equity]
    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    returns = pd.Series(values).pct_change().dropna()
    if len(returns) > 1 and returns.std() > 0:
        sharpe = returns.mean() / returns.std() * math.sqrt(ANNUAL_TRADING_DAYS)
    else:
        sharpe = 0

    buy_trades = [t for t in trades if t["action"] == "buy"]
    sell_trades = [t for t in trades if t["action"] == "sell"]
    if len(buy_trades) > 0 and len(sell_trades) > 0:
        wins = 0
        for j in range(min(len(buy_trades), len(sell_trades))):
            if sell_trades[j]["price"] > buy_trades[j]["price"]:
                wins += 1
        win_rate = wins / min(len(buy_trades), len(sell_trades))
    else:
        win_rate = 0

    return dict(
        total_return=round(total_return, 6),
        annual_return=round(annual_return, 6),
        max_drawdown=round(max_dd, 6),
        sharpe_ratio=round(sharpe, 4),
        win_rate=round(win_rate, 4),
        equity_curve=equity,
        trades=trades
    )

def screen_stocks(stocks_data, strategy_name, params=None):
    """stocks_data: list of dicts with ts_code, close, pe, pb, pct_chg_20d etc.
    Returns ranked list."""
    params = params or dict()
    results = []
    for s in stocks_data:
        if strategy_name == "low_valuation":
            pe = s.get("pe_ttm") or 1e9
            pb = s.get("pb") or 1e9
            score = pe + pb * 10
            results.append(dict(ts_code=s["ts_code"], name=s.get("name", ""), score=round(score, 4)))
        elif strategy_name == "momentum":
            mom = s.get("pct_chg_20d", 0) or 0
            results.append(dict(ts_code=s["ts_code"], name=s.get("name", ""), score=round(mom, 4)))
        elif strategy_name == "dual_ma":
            close = s.get("close", 0)
            ma5 = s.get("ma5", 0)
            ma20 = s.get("ma20", 0)
            if ma20 and ma5 > ma20:
                score = (ma5 - ma20) / ma20
            else:
                score = -1
            results.append(dict(ts_code=s["ts_code"], name=s.get("name", ""), score=round(score, 4)))
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:params.get("top_n", 20)]
