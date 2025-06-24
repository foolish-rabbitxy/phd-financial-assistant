# Submit orders and read portfolio from Alpaca
import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

load_dotenv()  # Load keys from .env

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL")

# Initialize client
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

def get_account_info():
    account = api.get_account()
    return {
        "cash": account.cash,
        "portfolio_value": account.portfolio_value,
        "status": account.status,
    }

def get_latest_price(symbol: str):
    """
    Fetch the latest trade price for a given stock symbol.
    """
    try:
        quote = api.get_latest_trade(symbol)
        return {
            "symbol": symbol.upper(),
            "price": quote.price,
            "timestamp": quote.timestamp,
        }
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def get_price_history(symbol, days=30):
    import sqlite3
    import pandas as pd
    conn = sqlite3.connect("local_db/market_data.db")
    df = pd.read_sql_query(
        "SELECT timestamp, close FROM ohlcv WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
        conn,
        params=(symbol, days)
    )

    print(f"{symbol}: {df.shape[0]} bars fetched")  # Debug line

    conn.close()
    # Ensure it's sorted in ascending timestamp order
    df = df.sort_values("timestamp")
    if len(df) < 2:
        return None
    # Return pandas Series with timestamps as index, close price as values
    return pd.Series(df["close"].values, index=pd.to_datetime(df["timestamp"]))


def submit_order(symbol: str, qty: int, side: str = "buy", type_: str = "market", time_in_force: str = "gtc"):
    """
    Submit a basic market order.

    Args:
        symbol (str): Stock ticker (e.g., AAPL)
        qty (int): Number of shares
        side (str): 'buy' or 'sell'
        type_ (str): 'market' or 'limit'
        time_in_force (str): e.g., 'gtc' (good till canceled)
    """
    try:
        order = api.submit_order(
            symbol=symbol.upper(),
            qty=qty,
            side=side,
            type=type_,
            time_in_force=time_in_force
        )
        print(f"Order submitted: {side.upper()} {qty} {symbol.upper()}")
        return order
    except Exception as e:
        print(f"Error submitting order for {symbol}: {e}")
        return None

from alpaca_trade_api.rest import TimeFrame

def get_ohlc_bars(symbol: str, timeframe: TimeFrame = TimeFrame.Day, limit: int = 30):
    """
    Fetch OHLC bars for a given stock symbol.
    """
    try:
        bars = api.get_bars(symbol.upper(), timeframe, limit=limit)
        bars_list = list(bars)
        if not bars_list:
            print(f"No bars returned for {symbol}.")
        return bars_list
    except Exception as e:
        print(f"Error fetching OHLC bars for {symbol}: {e}")
        return []


if __name__ == "__main__":
    info = get_account_info()
    print("Account Status:", info["status"])
    print("Cash Balance:", info["cash"])
    print("Portfolio Value:", info["portfolio_value"])

    # Show live prices
    for symbol in ["AAPL", "SPY", "TSLA"]:
        quote = get_latest_price(symbol)
        if quote:
            print(f"{quote['symbol']} price: ${quote['price']} at {quote['timestamp']}")

    # Submit a test paper trade
    test_order = submit_order("AAPL", qty=1, side="buy")
    if test_order:
        print(f"Order ID: {test_order.id}")
