# src/data/news.py

import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import sqlite3
from datetime import datetime

def fetch_news(symbol):
    """
    Fetches recent news headlines for a given stock symbol using Yahoo Finance RSS.
    Returns a list of dicts with keys: symbol, title, summary, published, sentiment.
    """
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    feed = feedparser.parse(url)
    analyzer = SentimentIntensityAnalyzer()
    items = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        published = entry.get("published", "")
        # Standardize published to ISO format
        try:
            dt = datetime(*entry.published_parsed[:6])
            published = dt.isoformat()
        except Exception:
            published = ""
        # Sentiment score
        sentiment = analyzer.polarity_scores(title + " " + summary)["compound"]
        items.append({
            "symbol": symbol,
            "title": title,
            "summary": summary,
            "published": published,
            "sentiment": sentiment
        })
    return items

def store_news(items):
    """
    Stores news items (as list of dicts) in the news table of the local SQLite DB.
    """
    if not items:
        return
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    # Create table if needed
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
    for item in items:
        cur.execute("""
            INSERT INTO news (symbol, title, summary, published, sentiment)
            VALUES (?, ?, ?, ?, ?)
        """, (
            item["symbol"],
            item["title"],
            item["summary"],
            item["published"],
            item["sentiment"]
        ))
    conn.commit()
    conn.close()
