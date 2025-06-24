#!/bin/bash
set -e

pip install -r requirements.txt
# This script installs the required Python packages from requirements.txt
# Ensure that you have Python and pip installed in your environment.
# You can run this script from the terminal to install all dependencies.

echo "=== Step 1: Loading latest S&P 500 tickers into database ==="
python3 src/sp500_loader.py

echo "=== Step 2: Fetching fundamentals for all symbols ==="
python3 -m src.data.fundamentals_main

echo "=== Step 3: Fetching OHLCV bars for all symbols ==="
python3 -m src.data.collector_main

echo "=== Step 4: Fetching news for all symbols ==="
python3 -m src.data.news_main

echo "=== Step 5: Training ML model ==="
python3 -m src.strategy.train_model

echo "=== Step 6: Launching dashboard in your browser! ==="
# Launch Streamlit dashboard in background, logs to dashboard.log
PYTHONPATH=$(pwd) ~/.local/bin/streamlit run src/dashboard/dashboard.py > dashboard.log 2>&1 &

echo "=== Step 7: Sending daily portfolio email ==="
python3 -m src.strategy.run_strategy --email

echo "=== All steps completed! ==="
echo "The dashboard is running at http://localhost:8501"

# This script runs all the necessary steps to prepare the data and train the model.
# Ensure that you have the required Python packages installed in your environment.
# You can run this script from the terminal to execute all steps sequentially.
# Usage: ./run_all.sh