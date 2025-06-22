from src.data.fundamentals import init_fundamentals_table, fetch_and_store_fundamentals

if __name__ == "__main__":
    init_fundamentals_table()
    symbols = ["AAPL", "MSFT", "SPY", "TSLA"]
    for symbol in symbols:
        print(f"Fetching fundamentals for {symbol}...")
        fetch_and_store_fundamentals(symbol)
    print("Done.")
# This script initializes the fundamentals table and fetches financial data for a list of symbols.
# It uses the yfinance library to get the latest financial metrics and stores them in a local SQLite database.
# The database is located at src/local_db/market_data.db, and the table is named "fundamentals".
# Each symbol's data includes the P/E ratio, dividend yield, market cap, sector, and industry.
# If the symbol already exists in the database, it will be updated with the latest data.
# The script can be run directly to populate the database with the specified symbols.
# Make sure to have the yfinance library installed in your Python environment.
# You can install it using pip:
# pip install yfinance  