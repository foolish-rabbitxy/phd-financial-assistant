# src/strategy/engine.py

import sqlite3
from typing import List, Dict
import joblib
import os
import pandas as pd

MODEL_PATH = "model/stock_score_model.pkl"
model = None
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)

def load_candidates(symbols: List[str] = None) -> List[Dict]:
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    if symbols and len(symbols) > 0:
        placeholder = ",".join(["?"] * len(symbols))
        cur.execute(
            f"SELECT symbol, pe_ratio, dividend_yield, market_cap, sector, industry FROM fundamentals WHERE symbol IN ({placeholder})",
            symbols
        )
    else:
        cur.execute(
            "SELECT symbol, pe_ratio, dividend_yield, market_cap, sector, industry FROM fundamentals"
        )
    rows = cur.fetchall()
    conn.close()
    stocks = []
    for row in rows:
        stocks.append({
            "symbol": row[0],
            "pe_ratio": row[1],
            "dividend_yield": row[2],
            "market_cap": row[3],
            "sector": row[4],
            "industry": row[5],
        })
    return stocks

def enrich_sentiment(stocks: List[Dict]) -> List[Dict]:
    # Attach avg_sentiment from news table (if available)
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    for stock in stocks:
        cur.execute("SELECT AVG(sentiment) FROM news WHERE symbol=?", (stock["symbol"],))
        result = cur.fetchone()
        stock["avg_sentiment"] = result[0] if result and result[0] is not None else 0
    conn.close()
    return stocks

def filter_and_score(candidates: List[Dict]) -> List[Dict]:
    filtered = []
    for stock in candidates:
        # Basic filters
        if not stock["pe_ratio"] or stock["pe_ratio"] > 40:
            continue
        if stock["dividend_yield"] is not None and stock["dividend_yield"] < 0.01:
            continue

        pe = stock["pe_ratio"]
        div = stock["dividend_yield"] or 0
        sentiment = stock.get("avg_sentiment", 0) or 0

        # Add historical return/volatility if available
        try:
            from src.trading.alpaca_client import get_price_history
            series = get_price_history(stock["symbol"], days=30)
            # series should be a pandas Series of prices
            if series is not None and hasattr(series, "__len__") and len(series) >= 2:
                pct_return = (series.iloc[-1] - series.iloc[0]) / series.iloc[0]
                volatility = series.pct_change().std()
                stock["return_30d"] = round(float(pct_return) * 100, 2)
                stock["volatility_30d"] = round(float(volatility) * 100, 2)
            else:
                stock["return_30d"] = None
                stock["volatility_30d"] = None
        except Exception as e:
            stock["return_30d"] = None
            stock["volatility_30d"] = None

        # ML-based prediction or fallback score
        score = 0
        if model:
            feature_df = pd.DataFrame([{
                "pe_ratio": pe,
                "dividend_yield": div,
                "market_cap": stock.get("market_cap", 0),
                "sentiment": sentiment
            }])
            score = float(model.predict(feature_df)[0])
        else:
            # Fallback: simple scoring
            score = 0.05 * (1 / pe) + 0.1 * div + sentiment

        stock["score"] = round(score, 4)
        filtered.append(stock)

    # Filter out stocks with no score
    filtered = [s for s in filtered if "score" in s and s["score"] is not None]
    return sorted(filtered, key=lambda x: x["score"], reverse=True)

def allocate_portfolio(ranked: List[Dict], budget: float = 1000.0) -> List[Dict]:
    total_score = sum(stock["score"] for stock in ranked[:5]) or 1.0
    portfolio = []
    for stock in ranked[:5]:
        allocation = round((stock["score"] / total_score) * budget, 2)
        entry = stock.copy()
        entry["allocation"] = allocation
        portfolio.append(entry)
    return portfolio

def generate_explanation(stock):
    """
    Generate an HTML-formatted explanation for a stock's selection, summarizing its key metrics and sentiment.

    Args:
        stock (dict): A dictionary containing stock data and computed metrics.

    Returns:
        str: An HTML string explaining the rationale for the stock's selection.
    """

VOLATILITY_LOW_THRESHOLD = 2.0  # Define a threshold for low volatility (in percent)

def generate_explanation(stock):
    def fmt(val, pct=False, currency=False):
        if val is None:
            return "N/A"
        if pct:
            return f"{val:.2f}%" if val is not None else "N/A"
        if currency:
            return f"${val:,.2f}"
        if isinstance(val, float):
            return f"{val:,.2f}"
        return str(val)
    avg_sentiment = stock.get('avg_sentiment', 0)
    if avg_sentiment > 0.1:
        sentiment_label = "(positive)"
        sentiment_summary = "strong positive news sentiment"
    elif abs(avg_sentiment) < 0.1:
        sentiment_label = "(neutral)"
        sentiment_summary = "neutral news sentiment"
    else:
        sentiment_label = "(negative)"
        sentiment_summary = "negative news sentiment"
    volatility = stock.get('volatility_30d', 0)
    if volatility is None:
        volatility = 0
    volatility_label = 'low' if volatility < VOLATILITY_LOW_THRESHOLD else 'high'
    sentiment_desc = f"{avg_sentiment:.2f} {sentiment_label}"
    volatility = stock.get('volatility_30d', 0)
    volatility_label = 'low' if volatility < VOLATILITY_LOW_THRESHOLD else 'high'
    html = (
        f"<strong>Symbol:</strong> {stock['symbol']}<br>"
        f"<strong>Sector/Industry:</strong> {stock.get('sector','N/A')} / {stock.get('industry','N/A')}<br>"
        f"<strong>Market Cap:</strong> {fmt(stock.get('market_cap'), currency=True)}<br>"
        f"<strong>P/E Ratio:</strong> {fmt(stock.get('pe_ratio'))}<br>"
        f"<strong>Dividend Yield:</strong> {fmt(stock.get('dividend_yield'), pct=True)}<br>"
        f"<strong>30d Return:</strong> {fmt(stock.get('return_30d'), pct=True)}<br>"
        f"<strong>30d Volatility:</strong> {fmt(stock.get('volatility_30d'), pct=True)}<br>"
        f"<strong>Sentiment Score:</strong> {sentiment_desc}<br>"
        f"<strong>Summary:</strong> Selected due to attractive P/E ratio ({fmt(stock.get('pe_ratio'))}), "
        f"solid dividend yield ({fmt(stock.get('dividend_yield'), pct=True)}), "
        f"{sentiment_summary}, "
        f"and {volatility_label} recent volatility ({fmt(stock.get('volatility_30d'), pct=True)})."
    )
    return html

