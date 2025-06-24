# src/sp500_loader.py

import yfinance as yf
import sqlite3

def fetch_sp500_symbols():
    # Try yfinance method for S&P 500 components first
    try:
        import pandas as pd
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        df = pd.read_html(url)[0]
        table = df['Symbol'].tolist()
    except Exception:
        # fallback if yfinance or pandas fails
        table = []
    # Remove symbols like ^GSPC (index tickers)
    table = [s for s in table if not str(s).startswith('^')]
    return table

def upsert_symbols_to_db(symbols, db_path="local_db/market_data.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            symbol TEXT PRIMARY KEY,
            pe_ratio REAL,
            dividend_yield REAL,
            market_cap REAL,
            sector TEXT,
            industry TEXT
        )
    """)
    for symbol in symbols:
        cur.execute("""
            INSERT OR IGNORE INTO fundamentals (symbol)
            VALUES (?)
        """, (symbol,))
    conn.commit()
    conn.close()
    print(f"Added/ensured {len(symbols)} symbols in fundamentals table.")

if __name__ == "__main__":
    symbols = fetch_sp500_symbols()
    print(f"Fetched {len(symbols)} S&P 500 symbols.")
    upsert_symbols_to_db(symbols)
    print("Symbols upserted to database.")
    print("You can now run the data collector to fetch OHLCV data for these symbols.")
    print("Run 'python src/data/collector_main.py' to start data collection.")
    print("After data collection, you can run the strategy engine to analyze the data.")
    print("Run 'python src/strategy_engine.py' to start the strategy engine.")
    print("Make sure to have the local_db/market_data.db file created before running the collector.")
    print("If you haven't created the database yet, run 'python src/data/fundamentals_main.py' to initialize it.")
    print("You can also run 'python src/data/news_main.py' to fetch news data for the symbols.")
    print("All set! Happy trading!")
    print("If you encounter any issues, please check the logs for more details.")
    print("For more information, refer to the documentation or the README file.")   