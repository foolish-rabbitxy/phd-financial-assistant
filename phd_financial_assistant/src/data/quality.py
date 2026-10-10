# src/data/quality.py
#
# Quality metrics (return on equity, profit margin, debt/equity) from Yahoo Finance for the
# multi-factor strategy. Snapshot only — Yahoo gives today's values, not history.
#
# Usage: python3 -m src.data.quality

import sqlite3
import time
from datetime import datetime

import yfinance as yf

DB_PATH = "local_db/market_data.db"


def init_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality (
            symbol TEXT PRIMARY KEY,
            roe REAL,
            profit_margin REAL,
            debt_to_equity REAL,
            updated TEXT
        )
    """)


def fetch_one(symbol: str) -> tuple:
    info = yf.Ticker(symbol.replace(".", "-")).info
    return (symbol, info.get("returnOnEquity"), info.get("profitMargins"), info.get("debtToEquity"),
            datetime.now().strftime("%Y-%m-%d"))


def refresh(pause: float = 0.3) -> int:
    conn = sqlite3.connect(DB_PATH)
    init_table(conn)
    symbols = [r[0] for r in conn.execute("SELECT symbol FROM fundamentals")]
    done = 0
    for i, sym in enumerate(symbols, 1):
        try:
            conn.execute("INSERT OR REPLACE INTO quality VALUES (?, ?, ?, ?, ?)", fetch_one(sym))
            done += 1
        except Exception as e:  # one bad ticker shouldn't stop the run
            print(f"skip {sym}: {e}")
        if i % 50 == 0:
            conn.commit()
            print(f"{i}/{len(symbols)}")
        time.sleep(pause)
    conn.commit()
    conn.close()
    return done


STALE_DAYS = 28  # quality metrics move slowly; the weekly autopilot refreshes them monthly


def is_stale(days: int = STALE_DAYS) -> bool:
    conn = sqlite3.connect(DB_PATH)
    init_table(conn)
    newest = conn.execute("SELECT MAX(updated) FROM quality").fetchone()[0]
    conn.close()
    return not newest or (datetime.now() - datetime.strptime(newest, "%Y-%m-%d")).days >= days


if __name__ == "__main__":
    import sys
    if "--force" in sys.argv or is_stale():
        print(f"updated {refresh()} symbols")
    else:
        print("quality data is fresh; skipping (use --force to refetch)")
