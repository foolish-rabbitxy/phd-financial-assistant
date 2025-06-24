import sqlite3

def create_all_tables():
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()

    # OHLCV table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            timestamp TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER
        )
    """)

    # Fundamentals table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            pe_ratio REAL,
            dividend_yield REAL,
            market_cap REAL,
            sector TEXT,
            industry TEXT
        )
    """)

    # News table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            title TEXT,
            summary TEXT,
            published TEXT,
            sentiment REAL
        )
    """)

    # Portfolio table (for simulation)
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
    print("All tables created or verified.")

if __name__ == "__main__":
    create_all_tables()
