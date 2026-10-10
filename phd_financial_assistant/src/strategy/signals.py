# src/strategy/signals.py
#
# Price-only allocation rules shared by the backtest and the live autopilot.
# Each rule takes a DataFrame of adjusted daily closes (index = dates, columns =
# symbols) containing only data up to the decision date, and returns target
# weights {symbol: fraction} summing to 1.

import pandas as pd

BENCHMARK = "SPY"
CASH = "BIL"  # 1-3 month T-bill ETF as the "risk-off" holding
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU"]

TREND_WINDOW = 200     # trading days for the SPY moving-average filter
MOM_LOOKBACK = 252     # ~12 months
MOM_SKIP = 21          # skip the most recent month (short-term reversal)


def spy_above_trend(prices: pd.DataFrame) -> bool:
    spy = prices[BENCHMARK].dropna()
    if len(spy) < TREND_WINDOW:
        return True
    return spy.iloc[-1] > spy.iloc[-TREND_WINDOW:].mean()


def momentum_scores(prices: pd.DataFrame, symbols) -> pd.Series:
    """12-1 month total return for symbols with full history."""
    window = prices[[s for s in symbols if s in prices.columns]].iloc[-(MOM_LOOKBACK + 1):]
    window = window.dropna(axis=1)
    if len(window) <= MOM_LOOKBACK:
        return pd.Series(dtype=float)
    return (window.iloc[-(MOM_SKIP + 1)] / window.iloc[0] - 1).dropna()


def top_momentum(prices, symbols, top_n):
    scores = momentum_scores(prices, symbols)
    scores = scores[scores > 0].nlargest(top_n)  # absolute momentum: never hold losers
    if scores.empty:
        return {CASH: 1.0}
    weights = {s: 1.0 / top_n for s in scores.index}
    if len(scores) < top_n:
        weights[CASH] = 1.0 - len(scores) / top_n
    return weights


def buy_and_hold_spy(prices, universe=None):
    return {BENCHMARK: 1.0}


def spy_trend(prices, universe=None):
    return {BENCHMARK: 1.0} if spy_above_trend(prices) else {CASH: 1.0}


def stock_momentum(prices, universe, top_n=20):
    return top_momentum(prices, universe, top_n)


def stock_momentum_trend(prices, universe, top_n=20):
    return stock_momentum(prices, universe, top_n) if spy_above_trend(prices) else {CASH: 1.0}


def sector_momentum_trend(prices, universe=None, top_n=3):
    return top_momentum(prices, SECTOR_ETFS, top_n) if spy_above_trend(prices) else {CASH: 1.0}


_SECTORS = None


def _sector_table():
    """Today's sector per symbol (the backtest's universe is today's list anyway)."""
    global _SECTORS
    if _SECTORS is None:
        import sqlite3
        conn = sqlite3.connect("local_db/market_data.db")
        rows = conn.execute("SELECT symbol, sector FROM fundamentals").fetchall()
        conn.close()
        _SECTORS = pd.DataFrame({"sector": {s.replace("-", "."): sec for s, sec in rows}})
    return _SECTORS


def multifactor_price(prices, universe, top_n=None):
    """Backtestable part of src.strategy.multifactor: price factors + trend filter + sector cap."""
    from src.strategy import multifactor as mf
    cols = [s for s in universe if s in prices.columns]
    weights = {k: mf.WEIGHTS[k] for k in mf.PRICE_FACTORS}
    scored = mf.score(prices[cols], _sector_table(), weights=weights)
    picks = mf.select(scored, top_n=top_n or mf.TOP_N)
    return {s: 1 / len(picks) for s in picks} if picks else {BENCHMARK: 1.0}


STRATEGIES = {
    "spy_buy_hold": buy_and_hold_spy,
    "spy_trend": spy_trend,
    "stock_momentum": stock_momentum,
    "stock_momentum_trend": stock_momentum_trend,
    "sector_momentum_trend": sector_momentum_trend,
    "multifactor_price": multifactor_price,
}
