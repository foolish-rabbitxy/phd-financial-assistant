import os
import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import time

# Add XGBoost import
try:
    from xgboost import XGBRegressor
except ImportError:
    raise ImportError("Please install xgboost: pip install xgboost")

# Ensure the model directory exists
os.makedirs("model", exist_ok=True) 
# Ensure the local_db directory exists
os.makedirs("local_db", exist_ok=True)
# Ensure the database file exists
if not os.path.exists("local_db/market_data.db"):
    # Create an empty database file if it doesn't exist
    conn = sqlite3.connect("local_db/market_data.db")
    conn.close()
    print("Created empty market_data.db in local_db directory.")

# This script trains a stock scoring model using fundamentals and news sentiment data.
# It assumes the database is already populated with the necessary data.

# Check if the model is current based on the latest data in the database
def model_is_current(model_path="model/stock_score_model.pkl"):
    if not os.path.exists(model_path):
        return False
    model_mtime = os.path.getmtime(model_path)
    conn = sqlite3.connect("local_db/market_data.db")
    cur = conn.cursor()
    cur.execute("SELECT MAX(timestamp) FROM ohlcv")
    ohlcv_max = cur.fetchone()[0]
    cur.execute("SELECT MAX(published) FROM news")
    news_max = cur.fetchone()[0]
    cur.execute("SELECT MAX(rowid) FROM fundamentals")
    fundamentals_max = cur.fetchone()[0]
    conn.close()
    import time
    latest_data_time = max([
        int(time.mktime(time.strptime(str(t), "%Y-%m-%d"))) if t else 0
        for t in [ohlcv_max[:10] if ohlcv_max else None, news_max[:10] if news_max else None]
    ] + [fundamentals_max or 0])
    return model_mtime > latest_data_time


DB_PATH = "local_db/market_data.db"

# Load features + target
def load_training_data():
    conn = sqlite3.connect(DB_PATH)
    df_fund = pd.read_sql_query("SELECT * FROM fundamentals", conn)
    df_news = pd.read_sql_query("SELECT symbol, AVG(sentiment) AS sentiment FROM news GROUP BY symbol", conn)
    conn.close()

    df = pd.merge(df_fund, df_news, on="symbol", how="left")

    # Fill missing numeric values with defaults
    df["pe_ratio"] = pd.to_numeric(df["pe_ratio"], errors="coerce").fillna(30.0)
    df["dividend_yield"] = pd.to_numeric(df["dividend_yield"], errors="coerce").fillna(0.0)
    df["market_cap"] = pd.to_numeric(df["market_cap"], errors="coerce").fillna(1e9)
    df["sentiment"] = pd.to_numeric(df["sentiment"], errors="coerce").fillna(0.0)

    # Simulated labels for now (to be replaced later)
    df["future_return"] = (
        0.05 * (1 / df["pe_ratio"]) +
        0.1 * df["dividend_yield"] +
        df["sentiment"]
    )

    print(f"Loaded {len(df)} rows for training.")

    features = df[["pe_ratio", "dividend_yield", "market_cap", "sentiment"]]
    target = df["future_return"]

    return train_test_split(features, target, test_size=0.2, random_state=42)


# Train models
X_train, X_test, y_train, y_test = load_training_data()

# --- RandomForest ---
rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)
rf_preds = rf_model.predict(X_test)
rf_rmse = np.sqrt(mean_squared_error(y_test, rf_preds))
print(f"✅ RandomForest Model trained. RMSE = {rf_rmse:.4f}")

# Save RandomForest model
joblib.dump(rf_model, "model/stock_score_model.pkl")
print("✅ RandomForest Model saved to model/stock_score_model.pkl")

# --- XGBoost ---
xgb_model = XGBRegressor(n_estimators=100, max_depth=3, random_state=42, use_label_encoder=False, eval_metric='rmse')
xgb_model.fit(X_train, y_train)
xgb_preds = xgb_model.predict(X_test)
xgb_rmse = np.sqrt(mean_squared_error(y_test, xgb_preds))
print(f"✅ XGBoost Model trained. RMSE = {xgb_rmse:.4f}")

# Save XGBoost model
joblib.dump(xgb_model, "model/xgb_stock_score_model.pkl")
print("✅ XGBoost Model saved to model/xgb_stock_score_model.pkl")
