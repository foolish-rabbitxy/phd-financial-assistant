import yfinance as yf
import sqlite3
from textblob import TextBlob
from datetime import datetime
from src.data.storage import DB_PATH

def fetch_news(symbol: str):
    ticker = yf.Ticker(symbol)
    news = ticker.news
    results = []

    for article in news:
        headline = article.get("title")
        summary = article.get("summary", "")

        timestamp = article.get("providerPublishTime")
        if not timestamp:
            continue  # Skip articles with missing publish time

        published = datetime.utcfromtimestamp(timestamp).isoformat()

        # Sentiment analysis
        blob = TextBlob(headline + " " + summary)
        sentiment = blob.sentiment.polarity  # -1 to 1

        results.append((symbol, headline, summary, published, sentiment))

    return results


def store_news(news_items):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT OR IGNORE INTO news (symbol, headline, summary, published_at, sentiment)
        VALUES (?, ?, ?, ?, ?)
    ''', news_items)
    conn.commit()
    conn.close()
