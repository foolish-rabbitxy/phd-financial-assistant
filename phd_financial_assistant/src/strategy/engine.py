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
    Produce a detailed, readable explanation of why this stock was chosen.
    """
    explanations = []
    symbol = stock.get("symbol", "")
    pe = stock.get("pe_ratio")
    div = stock.get("dividend_yield")
    market_cap = stock.get("market_cap")
    sector = stock.get("sector", "")
    industry = stock.get("industry", "")
    sentiment = stock.get("avg_sentiment", 0)
    ret = stock.get("return_30d")
    vol = stock.get("volatility_30d")

    explanations.append(f"**Symbol**: {symbol}")
    if sector or industry:
        explanations.append(f"**Sector/Industry**: {sector or ''} / {industry or ''}")
    if market_cap:
        explanations.append(f"**Market Cap**: ${market_cap/1e9:,.2f}B")
    if pe:
        explanations.append(f"**P/E Ratio**: {pe:.2f}")
    if div is not None:
        explanations.append(f"**Dividend Yield**: {div:.2%}")
    if ret is not None:
        explanations.append(f"**30d Return**: {ret}%")
    if vol is not None:
        explanations.append(f"**30d Volatility**: {vol}%")
    explanations.append(f"**Sentiment Score**: {sentiment:.2f} " +
        ("(positive)" if sentiment > 0 else "(neutral)" if sentiment == 0 else "(negative)")
    )
    # Summary
    summary = "Selected due to"
    if pe and pe < 25:
        summary += f" attractive P/E ratio ({pe:.2f}),"
    if div and div > 0.01:
        summary += f" solid dividend yield ({div:.2%}),"
    if sentiment and abs(sentiment) > 0.1:
        summary += f" strong {'positive' if sentiment > 0 else 'negative'} news sentiment,"
    if ret and ret > 0:
        summary += f" recent price momentum ({ret}% return in last 30d),"
    if vol and vol < 10:
        summary += f" low recent volatility ({vol}%),"
    if not summary.endswith(","):
        summary = summary.rstrip(",")
    summary = summary.rstrip(",") + "."
    explanations.append("**Summary:** " + summary)
    return "  \n".join(explanations)

