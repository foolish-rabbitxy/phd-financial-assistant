import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib
import os

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


# Train model
X_train, X_test, y_train, y_test = load_training_data()

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

preds = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, preds))

print(f"✅ Model trained. RMSE = {rmse:.4f}")

# Ensure model directory exists
os.makedirs("model", exist_ok=True)

# Save model
joblib.dump(model, "model/stock_score_model.pkl")
print("✅ Model saved to model/stock_score_model.pkl")