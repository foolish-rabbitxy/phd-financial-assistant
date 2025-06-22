from alpaca_trade_api.rest import TimeFrame
from src.data.collector import fetch_and_store
from src.data.storage import init_db

if __name__ == "__main__":
    init_db()
    symbols = ["AAPL", "MSFT", "SPY", "TSLA"]
    for symbol in symbols:
        fetch_and_store(symbol, timeframe=TimeFrame.Day, limit=100)
