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

def is_fundamental_up_to_date(symbol):
    import sqlite3
    conn = sqlite3.connect("local_db/market_data.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM fundamentals WHERE symbol=?", (symbol,))
    exists = c.fetchone()[0] > 0
    conn.close()
    return exists

if __name__ == "__main__":
    symbols = get_all_symbols()
    for symbol in symbols:
        if is_fundamental_up_to_date(symbol):
            continue  # skip if already present
        # fetch and store...
        print(f"Fetching fundamentals for {symbol}...")
        try:
            fetch_and_store_fundamentals(symbol)
        except Exception as e:
            print(f"Error fetching fundamentals for {symbol}: {e}")
    print("Done.")
