# src/strategy/live_picks.py
#
# Live inputs for src.strategy.multifactor: recent adjusted prices (Alpaca), fundamentals,
# quality metrics and average news sentiment from the local DB. Used by the autopilot and
# the dashboard.

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta

import pandas as pd

from src.strategy import multifactor as mf

DB_PATH = "local_db/market_data.db"
PRICE_CACHE = "local_db/prices_live.pkl"
PRICE_MAX_AGE_S = 20 * 3600
LOOKBACK_DAYS = 420  # calendar days → ~290 trading days, enough for 12-1 momentum + 200-day trend


def _norm(sym: str) -> str:
    return sym.replace("-", ".")


def load_prices(max_age_s: float = PRICE_MAX_AGE_S) -> pd.DataFrame:
    """Adjusted daily closes for the universe, cached on disk for most of a day."""
    if os.path.exists(PRICE_CACHE) and time.time() - os.path.getmtime(PRICE_CACHE) < max_age_s:
        return pd.read_pickle(PRICE_CACHE)
    from src.backtest.run_backtest import fetch_prices, load_universe
    start = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    prices = fetch_prices(load_universe(), start=start)
    prices.to_pickle(PRICE_CACHE)
    return prices


def load_fundamentals(db_path: str = DB_PATH) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        f = pd.read_sql("SELECT symbol, pe_ratio, dividend_yield, market_cap, sector, industry FROM fundamentals", conn)
        try:
            q = pd.read_sql("SELECT symbol, roe, profit_margin, debt_to_equity FROM quality", conn)
            f = f.merge(q, on="symbol", how="left")
        except Exception:  # quality table not fetched yet → those factors stay neutral
            pass
        s = pd.read_sql("SELECT symbol, AVG(sentiment) AS sentiment FROM news GROUP BY symbol", conn)
        f = f.merge(s, on="symbol", how="left")
    finally:
        conn.close()
    f["symbol"] = f["symbol"].map(_norm)
    return f.set_index("symbol")


def run(current: set[str] = frozenset()) -> tuple[pd.DataFrame, list[str]]:
    """Score today's universe and pick the portfolio. Returns (scored table, picks)."""
    scored = mf.score(load_prices(), load_fundamentals())
    return scored, mf.select(scored, current={_norm(s) for s in current})
