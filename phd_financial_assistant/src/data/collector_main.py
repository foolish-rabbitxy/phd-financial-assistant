# src/data/collector_main.py

from src.data.collector import fetch_and_store
from alpaca_trade_api.rest import TimeFrame
import sqlite3

def get_all_symbols():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM fundamentals")
    symbols = [row[0] for row in cur.fetchall()]
    conn.close()
    # Filter out index symbols (those starting with ^)
    return [s for s in symbols if not s.startswith('^')]

def has_ohlcv_for_today(symbol):
    import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("local_db/market_data.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol=? AND timestamp LIKE ?", (symbol, f"{today}%"))
    exists = c.fetchone()[0] > 0
    conn.close()
    return exists

if __name__ == "__main__":
    symbols = get_all_symbols()
    for symbol in symbols:
        if has_ohlcv_for_today(symbol):
            continue  # Skip if up to date
        # fetch and store bars
        print(f"Fetching OHLCV for {symbol}...")
        try:
            fetch_and_store(symbol, timeframe=TimeFrame.Day, limit=100)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    print("Data collection complete.")
    print("All symbols processed.")
    print("You can now run the strategy engine to analyze the data.")