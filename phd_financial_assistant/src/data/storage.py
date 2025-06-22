import os
import sqlite3
from typing import List, Tuple

# Define and ensure the local database directory exists
DATA_DIR = os.path.join(os.path.dirname(__file__), "../../local_db")
os.makedirs(DATA_DIR, exist_ok=True)

# Path to the SQLite database file
DB_PATH = os.path.join(DATA_DIR, "market_data.db")


def init_db(db_path=DB_PATH):
    """
    Initialize the SQLite database with an OHLCV table.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT,
            timestamp TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, timestamp)
        )
    ''')
    conn.commit()
    conn.close()


def save_ohlcv(symbol: str, bars: List[Tuple], db_path=DB_PATH):
    """
    Save a list of OHLCV bars to the database.
    Args:
        symbol (str): Stock symbol (e.g. 'AAPL')
        bars (List[Tuple]): List of bar objects from Alpaca
        db_path (str): Path to SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    rows = [(symbol, bar.t.isoformat(), bar.o, bar.h, bar.l, bar.c, bar.v) for bar in bars]
    cursor.executemany('''
        INSERT OR IGNORE INTO ohlcv (symbol, timestamp, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', rows)
    conn.commit()
    conn.close()

def init_news_table(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            symbol TEXT,
            headline TEXT,
            summary TEXT,
            published_at TEXT,
            sentiment REAL,
            PRIMARY KEY (symbol, headline)
        )
    ''')
    conn.commit()
    conn.close()
