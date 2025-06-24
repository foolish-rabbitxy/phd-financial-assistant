# src/data/news_main.py

from src.data.news import fetch_news, store_news
import sqlite3
import time
from datetime import datetime

def has_today_news(symbol):
    import sqlite3
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM news WHERE symbol=? AND published LIKE ?",
        (symbol, f"{today}%")
    )
    count = cur.fetchone()[0]
    conn.close()
    return count > 0

def get_all_symbols():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM fundamentals")
    symbols = [row[0] for row in cur.fetchall()]
    conn.close()
    # Exclude index symbols (like ^GSPC)
    return [s for s in symbols if not s.startswith('^')]

if __name__ == "__main__":
    symbols = get_all_symbols()
    for symbol in symbols:
        if has_today_news(symbol):
            print(f"Skipping {symbol}: already have today's news.")
            continue
        # ... fetch and store as before
        print(f"Fetching news for {symbol}...")
        try:
            items = fetch_news(symbol)
            if items:
                store_news(items)
                print(f"Stored {len(items)} news items for {symbol}")
            else:
                print(f"No news found for {symbol}")
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
        time.sleep(1.0)  # Rate limiting: be nice to Yahoo!
    print("News stored.")
