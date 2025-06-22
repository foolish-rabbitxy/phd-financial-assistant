from src.data.news import fetch_news, store_news
from src.data.storage import init_news_table

if __name__ == "__main__":
    init_news_table()
    symbols = ["AAPL", "MSFT", "TSLA"]
    for symbol in symbols:
        print(f"Fetching news for {symbol}...")
        items = fetch_news(symbol)
        store_news(items)
    print("News stored.")
# This script initializes the news table and fetches news articles for a list of stock symbols.
# It uses the yfinance library to get the latest news articles and stores them in a local SQLite database.
# The database is located at src/local_db/market_data.db, and the table is named "news".
# Each news item includes the symbol, title, content, and publication date.
# If the symbol already exists in the database, it will be updated with the latest news.
# The script can be run directly to populate the database with the specified symbols.
# Make sure to have the yfinance library installed in your Python environment.
# You can install it using pip:
# pip install yfinance  