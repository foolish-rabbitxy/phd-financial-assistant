#!/bin/bash
PYTHONPATH=$(pwd) ~/.local/bin/streamlit run src/dashboard/dashboard.py
# This script sets the PYTHONPATH to the current directory and runs the Streamlit dashboard.
# Ensure that the Streamlit package is installed in your Python environment.
# You can run this script from the terminal to start the dashboard.
# Usage: ./run_dashboard.sh 