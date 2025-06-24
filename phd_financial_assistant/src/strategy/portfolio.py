# Track portfolio, compute performance metrics
import sqlite3
import pandas as pd
from datetime import datetime

def create_portfolio_table():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            cost_basis REAL NOT NULL,
            buy_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def buy_portfolio(picks, buy_date=None):
    if buy_date is None:
        buy_date = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    for pick in picks:
        symbol = pick['symbol']
        allocation = pick['allocation']
        # Get the latest close price from ohlcv
        price_df = pd.read_sql_query(
            "SELECT close FROM ohlcv WHERE symbol=? ORDER BY timestamp DESC LIMIT 1",
            conn,
            params=(symbol,)
        )
        if price_df.empty:
            continue
        price = price_df['close'].iloc[0]
        qty = int(allocation // price)
        if qty <= 0:
            continue
        # Insert the "buy"
        cur.execute("""
            INSERT INTO portfolio (symbol, qty, cost_basis, buy_date)
            VALUES (?, ?, ?, ?)
        """, (symbol, qty, price, buy_date))
        print(f"Bought {qty} shares of {symbol} at {price} on {buy_date}")
    conn.commit()
    conn.close()

def get_portfolio_snapshot():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    df = pd.read_sql_query(
        "SELECT symbol, SUM(qty) as qty, AVG(cost_basis) as avg_cost, MIN(buy_date) as first_buy FROM portfolio GROUP BY symbol",
        conn
    )
    if df.empty:
        conn.close()
        return pd.DataFrame()
    # Get latest prices
    for idx, row in df.iterrows():
        symbol = row['symbol']
        price_df = pd.read_sql_query(
            "SELECT close FROM ohlcv WHERE symbol=? ORDER BY timestamp DESC LIMIT 1",
            conn, params=(symbol,)
        )
        latest = price_df['close'].iloc[0] if not price_df.empty else None
        df.at[idx, 'latest_price'] = latest
        if latest:
            df.at[idx, 'market_value'] = round(latest * row['qty'], 2)
            df.at[idx, 'gain'] = round((latest - row['avg_cost']) * row['qty'], 2)
            df.at[idx, 'return_pct'] = round(100 * (latest - row['avg_cost']) / row['avg_cost'], 2)
        else:
            df.at[idx, 'market_value'] = None
            df.at[idx, 'gain'] = None
            df.at[idx, 'return_pct'] = None
    conn.close()
    return df

def reset_portfolio():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM portfolio")
    conn.commit()
    conn.close()
    print("Simulated portfolio reset.")
    print(f"Order submitted: {side} {qty} shares of {symbol} at {type_} price")
    print(f"Order ID: {order.id}")