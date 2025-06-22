# Pull data from Alpaca or Yahoo Finance
from alpaca_trade_api.rest import TimeFrame
from src.trading.alpaca_client import api
from src.data.storage import init_db, save_ohlcv

from datetime import datetime, timedelta, timezone

def fetch_and_store(symbol: str, timeframe: TimeFrame = TimeFrame.Day, limit: int = 100):
    print(f"Fetching OHLCV for {symbol}...")

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=200)

    # Format as RFC3339 without microseconds
    start_str = start_date.replace(microsecond=0).isoformat()
    end_str = end_date.replace(microsecond=0).isoformat()

    bars = api.get_bars(
        symbol.upper(),
        timeframe,
        start=start_str,
        end=end_str,
        feed='iex'  # 🟢 Required for free paper trading accounts
    )
    if not bars:
        print(f"No bars returned for {symbol}.")
        return

    save_ohlcv(symbol, list(bars))
    print(f"Saved {len(bars)} bars for {symbol}.")
