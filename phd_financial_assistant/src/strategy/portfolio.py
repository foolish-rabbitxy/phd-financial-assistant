# Track portfolio, compute performance metrics
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from src.trading.alpaca_client import get_alpaca_portfolio, get_recent_alpaca_orders
from src.trading.alpaca_client import get_price_history

def build_alpaca_portfolio_history():
    """Reconstruct daily portfolio value for the Alpaca paper account."""
    positions = get_alpaca_portfolio()
    if not positions or not isinstance(positions, list):
        return None

    symbols = [pos['symbol'] for pos in positions]
    # Get historical prices for each symbol (30 days)
    price_histories = {}
    for sym in symbols:
        s = get_price_history(sym, days=30)
        if isinstance(s, pd.Series):
            price_histories[sym] = s

    # Build value over time (for days present in any symbol)
    all_dates = pd.to_datetime(sorted(
        {date for series in price_histories.values() for date in series.index}
    ))
    history = pd.DataFrame(index=all_dates)

    # Sum market value for each symbol at each date
    for sym in symbols:
        qty = 0
        # Find quantity for this symbol (from positions)
        for pos in positions:
            if pos['symbol'] == sym:
                try:
                    qty = float(pos['qty'])
                except Exception:
                    qty = 0
        if sym in price_histories:
            s = price_histories[sym]
            # Align series to the DataFrame index (do not fill yet)
            s = s.reindex(history.index)
            history[sym] = s * qty

    # Fill forward missing prices for all symbols at once
    history = history.fillna(method='ffill')

    # Add up all positions for total value per day
    history["portfolio_value"] = history.sum(axis=1)
    return history

def compute_alpaca_portfolio_analytics():
    """
    Returns dict with total_return (percent), annual_volatility (percent), sharpe_ratio, etc.
    Note: annual_volatility is reported as a percentage, matching the calculation.
    """
    hist = build_alpaca_portfolio_history()
    if hist is None or hist["portfolio_value"].isnull().all():
        return None

    hist = hist.dropna(subset=["portfolio_value"])
    if len(hist) < 3:
        return None

    values = hist["portfolio_value"]
    returns = values.pct_change().dropna()
    total_return = (values.iloc[-1] / values.iloc[0] - 1) * 100
    annual_volatility = returns.std() * (252**0.5) * 100  # percent
    sharpe = (returns.mean() / returns.std()) * (252**0.5) if returns.std() > 0 else None
    
    return {
        "total_return": round(total_return, 2),
        "annual_volatility": f"{round(annual_volatility, 2)}%" if annual_volatility else "N/A",
        "sharpe_ratio": round(sharpe, 2) if sharpe is not None else "N/A",
        "start_value": round(values.iloc[0], 2),
        "end_value": round(values.iloc[-1], 2),
        "num_days": len(values),
    }


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
        qty = int(allocation / price)
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

# Add to src/strategy/portfolio.py or as a new function in engine.py

def compute_live_portfolio_performance(holdings):
    """
    Calculate performance metrics for the Alpaca portfolio.
    This is a placeholder for your analytics logic.
    """
    # Example: total market value, unrealized PL, etc.
    total_market_value = sum(h.get("market_value", 0) for h in holdings)
    total_unrealized_pl = sum(h.get("unrealized_pl", 0) for h in holdings)
    # Add more as desired
    return {
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pl": round(total_unrealized_pl, 2),
        "num_positions": len(holdings)
    }


from src.trading.alpaca_client import submit_order

def rebalance_alpaca_portfolio(suggested_allocation, min_diff=5.0):
    """
    Automatically trades Alpaca paper account to match the suggested allocation.

    WARNING: This function performs live trades via submit_order and will modify the Alpaca paper account.

    - suggested_allocation: list of dicts with 'symbol', 'allocation' (target $ amount)
    - min_diff: Minimum $ difference to trigger trade
    Returns list of actions taken.
    """
    current_port = get_alpaca_portfolio()
    current_holdings = {p['symbol']: float(p['market_value']) for p in current_port}
    actions = []

    # Step 1: For each symbol in target allocation, determine buy/sell
    for s in suggested_allocation:
        symbol = s['symbol']
        target_amt = s['allocation']
        current_amt = current_holdings.get(symbol, 0.0)
        diff = target_amt - current_amt

        if abs(diff) < min_diff:
            continue  # Skip minor adjustments

        price = s.get('last_price') or s.get('price') or 0
        if price <= 0:
            continue  # No valid price, can't trade

        qty = calculate_trade_quantity(diff, price)
        if qty < 1:
            continue

        if diff > 0:
            submit_order(symbol, qty, side='buy')
            actions.append(f"BUY {qty} shares of {symbol} (need +${diff:.2f})")
        elif diff < 0:
            submit_order(symbol, qty, side='sell')
            actions.append(f"SELL {qty} shares of {symbol} (over by ${-diff:.2f})")

    # Step 2: Close out any positions not in target
    target_symbols = {s['symbol'] for s in suggested_allocation}
    for sym in current_holdings:
        if sym not in target_symbols:
            qty = int(float(next((p['qty'] for p in current_port if p['symbol']==sym), 0)))
            if qty > 0:
                submit_order(sym, qty, side='sell')
                actions.append(f"SELL ALL {qty} shares of {sym} (not in target picks)")

    if not actions:
        actions.append("No trades needed. Portfolio already matches suggested allocation.")

        return actions
    
    def calculate_trade_quantity(diff, price):
        """
        Helper function to calculate the number of shares to trade based on the dollar difference and price.
        """
        if price <= 0:
            return 0
        return int(abs(diff) // price)
