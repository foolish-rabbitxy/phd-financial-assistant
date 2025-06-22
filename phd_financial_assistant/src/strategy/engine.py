import sqlite3
from typing import List, Dict
from math import sqrt
import joblib
import pandas as pd
import os
model = joblib.load("model/stock_score_model.pkl")

# Load trained model
MODEL_PATH = "model/stock_score_model.pkl"
model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
# Ensure model is loaded
if model is None:
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Please train the model first.")  

DB_PATH = "local_db/market_data.db"

def load_candidates() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT f.symbol, f.pe_ratio, f.dividend_yield, f.market_cap,
               f.sector, f.industry,
               AVG(n.sentiment) AS avg_sentiment
        FROM fundamentals f
        LEFT JOIN news n ON f.symbol = n.symbol
        GROUP BY f.symbol
    ''')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def filter_and_score(candidates: List[Dict]) -> List[Dict]:
    filtered = []

    for stock in candidates:
        # Basic filters
        if not stock["pe_ratio"] or stock["pe_ratio"] > 40:
            continue
        if stock["dividend_yield"] is not None and stock["dividend_yield"] < 0.01:
            continue

        # Get fundamentals
        pe = stock["pe_ratio"]
        div = stock["dividend_yield"] or 0
        sentiment = stock["avg_sentiment"] or 0

        # Default metrics
        pct_return = None
        volatility = None

        # Add historical return/volatility
        try:
            series = get_price_history(stock["symbol"], days=30)
            if len(series) >= 2:
                pct_return = (series.iloc[-1] - series.iloc[0]) / series.iloc[0]
                volatility = series.pct_change().std()
                stock["return_30d"] = round(pct_return * 100, 2)
                stock["volatility_30d"] = round(volatility * 100, 2)
            else:
                stock["return_30d"] = None
                stock["volatility_30d"] = None
        except Exception as e:
            print(f"Warning: could not get price data for {stock['symbol']}: {e}")
            stock["return_30d"] = None
            stock["volatility_30d"] = None

        # ML-based scoring using trained model
        try:

            features = pd.DataFrame([{
                "pe_ratio": pe,
                "dividend_yield": div,
                "market_cap": stock.get("market_cap", 0),
                "sentiment": sentiment
            }])
            if features.isnull().values.any():
                print(f"Warning: missing features for {stock['symbol']}, skipping scoring.")
                continue
            # Ensure features are numeric
            features = features.apply(pd.to_numeric, errors='coerce').fillna(0)
            if features.empty:
                print(f"Warning: empty features for {stock['symbol']}, skipping scoring.")
                continue
            # Predict score
            if model is None:
                print("Error: Model is not loaded. Cannot score stocks.")
                continue
            if not hasattr(model, 'predict'):
                print("Error: Loaded model does not have a predict method.")
                continue
            if features.shape[1] != model.n_features_in_:
                print(f"Error: Feature shape mismatch for {stock['symbol']}. Expected {model.n_features_in_}, got {features.shape[1]}.")
                continue

            score = model.predict(features)[0]
            stock["score"] = round(score, 4)
        except Exception as e:
            print(f"Warning: model scoring failed for {stock['symbol']}: {e}")
            continue
        # Add to filtered list
        stock["symbol"] = stock["symbol"].upper()
        stock["pe_ratio"] = round(pe, 2)
        stock["dividend_yield"] = round(div, 4)
        stock["avg_sentiment"] = round(sentiment, 2)
        stock["score"] = round(stock["score"], 4)
        filtered.append(stock)

        return sorted(filtered, key=lambda x: x["score"], reverse=True)
from typing import List, Dict 


def allocate_portfolio(ranked: List[Dict], budget: float = 1000.0, top_n: int = 3) -> List[Dict]:
    """
    Allocate capital across top N stocks using score-based weights.
    """
    top = ranked[:top_n]
    total_score = sum(stock["score"] for stock in top)

    for stock in top:
        weight = stock["score"] / total_score
        stock["allocation"] = round(budget * weight, 2)

    return top

import pandas as pd
from alpaca_trade_api.rest import TimeFrame
from src.trading.alpaca_client import api

def get_price_history(symbol: str, days: int = 30):
    bars = api.get_bars(
        symbol.upper(),
        TimeFrame.Day,
        limit=days,
        feed='iex'
    )
    closes = [bar.c for bar in bars]
    return pd.Series(closes)

def generate_explanation(stock: Dict) -> str:
    symbol = stock["symbol"]
    reasons = []

    # Valuation
    if stock["pe_ratio"] and stock["pe_ratio"] < 25:
        reasons.append("attractive valuation (low P/E ratio)")
    elif stock["pe_ratio"]:
        reasons.append(f"P/E of {round(stock['pe_ratio'], 1)}")

    # Yield
    if stock["dividend_yield"] and stock["dividend_yield"] > 0.02:
        reasons.append("solid dividend yield")

    # Sentiment
    if stock["avg_sentiment"] and stock["avg_sentiment"] > 0.1:
        reasons.append("positive media sentiment")

    # Return
    if stock.get("return_30d") and stock["return_30d"] > 2:
        reasons.append(f"30-day price momentum of {stock['return_30d']}%")

    # Volatility
    if stock.get("volatility_30d") and stock["volatility_30d"] < 2:
        reasons.append("low recent volatility")

    if not reasons:
        reasons.append("scored well on overall metrics")

    explanation = f"{symbol} was selected due to " + ", ".join(reasons) + "."
    return explanation
