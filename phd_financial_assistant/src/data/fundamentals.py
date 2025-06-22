import yfinance as yf
import sqlite3
import os

FUNDAMENTALS_DB = os.path.join(os.path.dirname(__file__), "../../local_db/market_data.db")

def init_fundamentals_table():
    conn = sqlite3.connect(FUNDAMENTALS_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundamentals (
            symbol TEXT PRIMARY KEY,
            pe_ratio REAL,
            dividend_yield REAL,
            market_cap REAL,
            sector TEXT,
            industry TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fetch_and_store_fundamentals(symbol: str):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    data = (
        symbol,
        info.get("trailingPE"),
        info.get("dividendYield"),
        info.get("marketCap"),
        info.get("sector"),
        info.get("industry")
    )

    conn = sqlite3.connect(FUNDAMENTALS_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO fundamentals 
        (symbol, pe_ratio, dividend_yield, market_cap, sector, industry)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()
