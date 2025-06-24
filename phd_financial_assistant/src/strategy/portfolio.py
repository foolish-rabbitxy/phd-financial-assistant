# Track portfolio, compute performance metrics
import sqlite3
import pandas as pd
import numpy as np
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

def get_portfolio_performance():
    """
    Compute portfolio return, volatility, Sharpe ratio, based on simulated buys and daily price changes.
    """
    import sqlite3
    import pandas as pd

    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    # Get distinct buy dates in order (oldest first)
    dates = pd.read_sql_query(
        "SELECT DISTINCT buy_date FROM portfolio ORDER BY buy_date", conn
    )["buy_date"].tolist()
    if not dates:
        conn.close()
        return None

    # Get all buys
    buys = pd.read_sql_query(
        "SELECT symbol, qty, cost_basis, buy_date FROM portfolio", conn
    )

    # For each day, compute value of all positions
    symbols = buys["symbol"].unique()
    values_by_day = {}
    for day in dates:
        day_value = 0
        for symbol in symbols:
            # Find all buys of this symbol up to and including this day
            symbol_buys = buys[(buys["symbol"] == symbol) & (buys["buy_date"] <= day)]
            if symbol_buys.empty:
                continue
            total_qty = symbol_buys["qty"].sum()
            # Find latest close on or before this day
            price_df = pd.read_sql_query(
                "SELECT close FROM ohlcv WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
                conn,
                params=(symbol, day)
            )
            if price_df.empty:
                continue
            latest_price = price_df["close"].iloc[0]
            day_value += total_qty * latest_price
        values_by_day[day] = day_value

    conn.close()
    # If less than 2 data points, can't calculate return/volatility
    if len(values_by_day) < 2:
        return None

    days = list(values_by_day.keys())
    values = np.array([values_by_day[d] for d in days])
    daily_returns = np.diff(values) / values[:-1]
    total_return = (values[-1] - values[0]) / values[0]
    avg_daily_return = np.mean(daily_returns)
    volatility = np.std(daily_returns)
    sharpe = avg_daily_return / volatility * np.sqrt(252) if volatility > 0 else 0

    return {
        "total_return": round(total_return * 100, 2),
        "annual_volatility": round(volatility * np.sqrt(252) * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "start_value": round(values[0], 2),
        "end_value": round(values[-1], 2),
        "num_days": len(days)
    }
