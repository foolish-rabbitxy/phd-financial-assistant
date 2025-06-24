# src/data/fundamentals_main.py

from src.data.fundamentals import fetch_and_store_fundamentals
import sqlite3

def get_all_symbols():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM fundamentals")
    symbols = [row[0] for row in cur.fetchall()]
    conn.close()
    return symbols

if __name__ == "__main__":
    symbols = get_all_symbols()
    for symbol in symbols:
        print(f"Fetching fundamentals for {symbol}...")
        try:
            fetch_and_store_fundamentals(symbol)
        except Exception as e:
            print(f"Error fetching fundamentals for {symbol}: {e}")
    print("Done.")
