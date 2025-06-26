#!/bin/bash
set -e

echo "=== Stopping any running Streamlit dashboard... ==="
pkill -f "streamlit run src/dashboard/dashboard.py" || true

sleep 2

echo "=== Launching dashboard in your browser! ==="
# Launch Streamlit dashboard in background, logs to dashboard.log
PYTHONPATH=$(pwd) ~/.local/bin/streamlit run src/dashboard/dashboard.py --server.port 8501 > dashboard.log 2>&1 &
# This command runs the Streamlit dashboard and redirects output to dashboard.log
# You can check the log file for any errors or output from the dashboard.

echo "Dashboard restarted! You can view it at http://localhost:8501"
