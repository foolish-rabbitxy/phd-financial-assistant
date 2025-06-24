#!/bin/bash
set -e

pip install -r requirements.txt
# This script installs the required Python packages from requirements.txt
# Ensure that you have Python and pip installed in your environment.
# You can run this script from the terminal to install all dependencies.

echo "=== Step 1: Loading latest S&P 500 tickers into database ==="
python3 src/sp500_loader.py
# This step loads the latest S&P 500 tickers into the database.
# Ensure that the sp500_loader script is correctly set up to connect to your database.

echo "=== Step 2: Fetching fundamentals for all symbols ==="
python3 -m src.data.fundamentals_main
# This step collects fundamental data for all symbols in the database.
# Ensure that the fundamentals collection script is correctly set up to fetch data from your data source.

echo "=== Step 3: Fetching OHLCV bars for all symbols ==="
python3 -m src.data.collector_main
# This step collects OHLCV (Open, High, Low, Close, Volume) data for all symbols in the database.
# Ensure that the collector script is correctly set up to fetch data from your data source.

echo "=== Step 4: Fetching news for all symbols ==="
python3 -m src.data.news_main
# This step collects news articles related to the symbols in the database.
# Ensure that the news collection script is correctly set up to fetch data from your news source.

echo "=== Step 5: Training ML model ==="
python3 -m src.strategy.train_model
# This step trains the machine learning model using the collected data.
# Ensure that the training script is correctly set up to use the data from previous steps.

echo "=== Step 6: Launching dashboard in your browser! ==="
# Launch Streamlit dashboard in background, logs to dashboard.log
PYTHONPATH=$(pwd) ~/.local/bin/streamlit run src/dashboard/dashboard.py --server.port 8501 > dashboard.log 2>&1 &
# This command runs the Streamlit dashboard and redirects output to dashboard.log
# You can check the log file for any errors or output from the dashboard.

echo "=== Step 7: Sending daily portfolio email ==="
python3 -m src.strategy.run_strategy --email
# This step runs the strategy and sends a daily portfolio email to the user.
# Ensure that you have configured your email settings in the strategy module.

echo "=== All steps completed! ==="
echo "The dashboard is running at http://localhost:8501"
# run_all.sh
# This script orchestrates the entire workflow of loading data, training the model, and launching the
# dashboard. Each step is executed sequentially, and errors will stop the execution due to 'set -e'.

# This script runs all the necessary steps to prepare the data and train the model.
# Ensure that you have the required Python packages installed in your environment.
# You can run this script from the terminal to execute all steps sequentially.
# Usage: ./run_all.sh