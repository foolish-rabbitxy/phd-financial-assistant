# src/dashboard/dashboard.py
import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import os
from src.trading.alpaca_client import buy_top_picks_with_alpaca, get_alpaca_portfolio, get_recent_alpaca_orders
from src.strategy.engine import load_candidates, filter_and_score, allocate_portfolio, generate_explanation, enrich_sentiment
from src.strategy.portfolio import rebalance_alpaca_portfolio

st.set_page_config(page_title="📊 Financial Assistant Dashboard", layout="wide")
st.title("📈 AI Financial Assistant")

st.markdown("""
<div>
<strong>Legend:</strong><br>
    <ul>
        <li><b>RF Score:</b> <i>RandomForest model's prediction</i> – a machine learning score predicting future stock potential; higher is better.</li>
        <li><b>XGB Score:</b> <i>XGBoost model's prediction</i> – an advanced machine learning score for stock ranking; higher is better.</li>
        <li><b>P/E:</b> <i>Price-to-Earnings ratio</i> – This tells you how much investors are willing to pay today for $1 of a company’s earnings. It is calculated as the current stock price divided by earnings per share (EPS).
            <ul>
                <li><b>Low P/E</b> (relative to sector) can suggest a stock is undervalued or that the company’s growth prospects are modest.</li>
                <li><b>High P/E</b> can indicate strong expected future growth, but can also mean the stock is overpriced.</li>
                <li>Compare P/E ratios within the same industry for best results.</li>
            </ul>
        </li>
        <li><b>Yield:</b> <i>Dividend Yield (%)</i> – how much a company pays in dividends each year as a percentage of its stock price.</li>
        <li><b>Sentiment:</b> <i>News Sentiment Score</i> – a measure of recent news positivity (positive, neutral, or negative) about the stock.</li>
        <li><b>30d Return:</b> <i>30-Day Price Change (%)</i> – the percent gain or loss in stock price over the past 30 days.</li>
        <li><b>Volatility:</b> <i>30-Day Volatility (%)</i> – how much the stock price has fluctuated over the last 30 days (higher = riskier, lower = more stable).</li>
    </ul>
</div>
""", unsafe_allow_html=True)


# --- Persistent Allocation Value (File-Backed) ---
PERSIST_FILE = "local_db/allocation.txt"

def save_allocation(val):
    try:
        os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
        with open(PERSIST_FILE, "w") as f:
            f.write(str(val))
    except Exception:
        pass

def load_allocation():
    try:
        if os.path.exists(PERSIST_FILE):
            with open(PERSIST_FILE, "r") as f:
                val = f.read()
                if val:
                    return val.strip()
    except Exception:
        pass
    return "1000"

if "allocation_input" not in st.session_state:
    st.session_state["allocation_input"] = load_allocation()

def parse_usd_amount(val):
    import re
    cleaned = re.sub(r"[^\d.]", "", str(val))
    try:
        usd = float(cleaned)
        if usd <= 0 or usd > 1_000_000_000:
            return None
        return round(usd, 2)
    except Exception:
        return None

allocation_input = st.text_input(
    "💰 Enter Suggested Allocation Amount (USD):",
    value=st.session_state["allocation_input"],
    key="allocation_input",
    max_chars=10,
    help="Enter a positive amount in US Dollars for your simulated investment."
)

allocation = parse_usd_amount(st.session_state["allocation_input"])

if allocation is not None:
    save_allocation(allocation)

if allocation is None:
    st.error("Please enter a valid positive dollar amount (e.g., 1000, 5,000, $2500.75), up to $1 billion.")
    st.stop()

# --- Sidebar controls ---
conn = sqlite3.connect("local_db/market_data.db")
df = None
try:
    df = (
        st.cache_data(show_spinner=False)(
            lambda: pd.read_sql_query(
                "SELECT * FROM fundamentals", conn
            )
        )()
    )
except Exception as e:
    st.warning(f"Failed to load fundamentals: {e}")
finally:
    conn.close()

st.sidebar.title("📂 Navigation")
st.sidebar.markdown("- [Home](#)")
st.sidebar.markdown("- [Top Picks](#top-picks)")
st.sidebar.markdown("- [Suggested Allocation](#suggested-allocation)")
st.sidebar.markdown("- [Explanations](#explanation-for-each-pick)")
st.sidebar.markdown("- [Refresh Data](#)")
st.sidebar.markdown("- [Contact](#contact)")

filtered_symbols = None
if df is not None:
    st.sidebar.header("🔎 Filter Stocks")
    all_sectors = sorted(df["sector"].dropna().unique())
    sector = st.sidebar.multiselect("Sector", all_sectors, default=all_sectors)
    min_cap = st.sidebar.number_input("Min Market Cap ($B)", min_value=0.0, value=0.0)
    search = st.sidebar.text_input("Symbol search", "")
    filtered = df[
        (df["sector"].isin(sector)) &
        (df["market_cap"].fillna(0) / 1e9 >= min_cap) &
        (df["symbol"].str.contains(search.upper()))
    ]
    filtered_symbols = filtered["symbol"].tolist()
else:
    filtered_symbols = []

# Show current timestamp with milliseconds, persistent with session_state
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
formatted_time = st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
st.caption(f"🕒 Last refreshed: {formatted_time}")

with st.spinner("Loading data..."):
    stocks = load_candidates(symbols=filtered_symbols)
    stocks = enrich_sentiment(stocks)
    ranked = filter_and_score(stocks)
    portfolio = allocate_portfolio(ranked, budget=allocation)

if not ranked:
    st.warning("No qualified stocks to show. Try updating your dataset or adjusting filters.")
    st.stop()

def make_markdown_link(label, url):
    return f"[{label}]({url})"

# --- Top 10 Picks Table (interactive, sortable, with rank, clickable links) ---
st.subheader("🏆 Top 10 Overall Picks")
table_data = []
for i, s in enumerate(ranked[:10], 1):
    table_data.append({
        "Rank": i,
        "Symbol": s["symbol"],
        "Score": s["score"],
        "RF Score": round(s["rf_score"], 4) if s.get("rf_score") is not None else None,
        "XGB Score": round(s["xgb_score"], 4) if s.get("xgb_score") is not None else None,
        "P/E": s["pe_ratio"],
        "Yield": s["dividend_yield"],
        "Sentiment": s.get("avg_sentiment", 0),
        "30d Return": s.get("return_30d"),
        "Volatility": s.get("volatility_30d"),
        "Fidelity": f'<a href="https://digital.fidelity.com/prgw/digital/research/quote/dashboard/summary?symbol={s["symbol"]}" target="_blank">Fidelity</a>',
        "Yahoo Finance": f'<a href="https://finance.yahoo.com/quote/{s["symbol"]}/" target="_blank">Yahoo Finance</a>',
    })
df_links = pd.DataFrame(table_data)

st.markdown("""
<style>
table { width: 100% !important; border-collapse: separate !important; }
th, td {
    text-align: left !important;
    padding: 10px 8px !important;
    vertical-align: top !important;
    font-size: 15px;
}
th {
    background: #fafafc;
    color: #222;
    border-bottom: 2px solid #f1f1f1;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    df_links.to_html(escape=False, index=False),
    unsafe_allow_html=True
)

# --- Suggested Allocation Table with Explanations (Top 5) ---
st.subheader(f"📝 Suggested Allocation Top 5 Picks & Rationale (${allocation:,.2f})")

allocation_table = []
for i, stock in enumerate(portfolio[:5], 1):
    allocation_table.append({
        "Rank": i,
        "Symbol": stock["symbol"],
        "Allocation ($)": f"${stock['allocation']:,.2f}",
        "Score": f"{stock['score']:.4f}",
        "RF Score": round(stock["rf_score"], 4) if stock.get("rf_score") is not None else None,
        "XGB Score": round(stock["xgb_score"], 4) if stock.get("xgb_score") is not None else None,
        "Explanation": generate_explanation(stock)
    })
df_alloc = pd.DataFrame(allocation_table)

# CSS for better line-wrapping and left alignment in Explanation
st.markdown("""
    <style>
    .st-emotion-cache-10trblm, .st-emotion-cache-1avcm0n, .st-emotion-cache-16txtl3 {
        white-space: pre-wrap !important;
        word-break: break-word !important;
        text-align: left !important;
        font-size: 14px;
        min-width: 350px !important;
    }
    th { text-align: left !important; }
    </style>
""", unsafe_allow_html=True)

def explanation_html(row):
    return f'<div>{row}</div>'

# Show table with explanations as HTML, for full formatting:
df_alloc_html = df_alloc.copy()
df_alloc_html["Explanation"] = df_alloc_html["Explanation"].apply(explanation_html)
st.markdown(
    df_alloc_html.to_html(escape=False, index=False),
    unsafe_allow_html=True
)

# --- Alpaca Live Portfolio Section ---
st.subheader("🤖 Alpaca Paper Trading Portfolio - Positions (Live)")
alpaca_port = get_alpaca_portfolio()
if alpaca_port:
    df_alpaca = pd.DataFrame(alpaca_port)
    st.dataframe(df_alpaca)
else:
    st.info("No live positions found in your Alpaca paper trading account.")

from src.strategy.portfolio import compute_live_portfolio_performance

if alpaca_port:
    perf = compute_live_portfolio_performance(alpaca_port)
    st.markdown(f"""
    - **Total Market Value:** ${perf['total_market_value']}
    - **Total Unrealized P/L:** ${perf['total_unrealized_pl']}
    - **Positions:** {perf['num_positions']}
    """)

# --- Combined Button Section (unique keys!) ---
col3, col4 = st.columns(2)
with col3:
    if st.button("🤖 Buy Top Picks with Alpaca Paper Trading", key="alpaca_buy"):
        results = buy_top_picks_with_alpaca(portfolio)
        if results and hasattr(results, "__iter__"):
            for line in results:
                st.info(line)
            st.success("Orders submitted to Alpaca! Refresh the Alpaca portfolio section below in a moment.")
        else:
            st.warning("No orders were submitted or an error occurred.")
        st.rerun()
with col4:
    if st.button("🔁 Rebalance Alpaca Portfolio to Model", key="rebalance"):
        st.warning("This will place market orders to match your model's suggested allocation. Are you sure?")
        if st.button("✅ Yes, rebalance now", key="confirm_rebalance"):
            actions = rebalance_alpaca_portfolio(portfolio)  # 'portfolio' is your suggested allocation list
            if actions:
                for act in actions:
                    st.info(act)
                st.success("Rebalancing submitted! Wait a moment for Alpaca to update positions.")
            else:
                st.info("No rebalancing actions were necessary or an error occurred.")
            st.rerun()

# --- Alpaca Recent Orders Section ---
st.subheader("📝 Recent Alpaca Paper Trading Orders")
recent_orders = get_recent_alpaca_orders()
if recent_orders:
    df_orders = pd.DataFrame(recent_orders)
    st.dataframe(df_orders)
else:
    st.info("No recent Alpaca orders found.")

from src.strategy.portfolio import compute_alpaca_portfolio_analytics

st.subheader("📊 Alpaca Portfolio Analytics")
alpaca_analytics = compute_alpaca_portfolio_analytics()
if alpaca_analytics:
    st.markdown(f"""
    - **Total Return:** {alpaca_analytics['total_return']}%
    - **Annualized Volatility:** {alpaca_analytics['annual_volatility']}%
    - **Sharpe Ratio:** {alpaca_analytics['sharpe_ratio']}
    - **Start Value:** ${alpaca_analytics['start_value']}
    - **End Value:** ${alpaca_analytics['end_value']}
    - **Days Tracked:** {alpaca_analytics['num_days']}
    """)
else:
    st.info("Not enough price history to calculate Alpaca portfolio analytics yet.")

if st.button("🔄 Refresh Data"):
    st.session_state.last_refresh = datetime.now()
    st.success("Data refreshed successfully!")
    st.rerun()

import matplotlib.pyplot as plt

from src.strategy.portfolio import build_alpaca_portfolio_history

st.subheader("📉 Alpaca Portfolio Value Over Time")
history = build_alpaca_portfolio_history()
if history is not None and "portfolio_value" in history.columns:
    fig, ax = plt.subplots(figsize=(8,3))
    history["portfolio_value"].plot(ax=ax, label="Portfolio Value ($)", color="dodgerblue")
    ax.set_ylabel("Portfolio Value ($)")
    ax.set_xlabel("Date")
    ax.set_title("Equity Curve")
    ax.legend()
    st.pyplot(fig)
else:
    st.info("Not enough history to show Alpaca portfolio value chart yet.")

import numpy as np

st.subheader("📊 Alpaca Portfolio Allocation")
if alpaca_port and isinstance(alpaca_port, list) and len(alpaca_port) > 0:
    alloc = {pos["symbol"]: float(pos["market_value"]) for pos in alpaca_port if float(pos.get("market_value",0)) > 0}
    if alloc:
        fig2, ax2 = plt.subplots(figsize=(5, 5))
        ax2.pie(list(alloc.values()), labels=list(alloc.keys()), autopct="%1.1f%%", startangle=90)
        ax2.axis('equal')
        ax2.set_title("Portfolio Allocation")
        st.pyplot(fig2)
    else:
        st.info("No active Alpaca positions to show allocation.")
else:
    st.info("No active Alpaca positions to show allocation.")

import pandas as pd

st.subheader("⬇️ Download Alpaca Positions as CSV")
if alpaca_port:
    df_alpaca = pd.DataFrame(alpaca_port)
    csv = df_alpaca.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="alpaca_positions.csv",
        mime="text/csv",
    )


st.markdown("""
<style>
footer {
    position: fixed;
    bottom: 0;
    width: 100%;
    text-align: center;
    padding: 10px;
    font-size: 14px;
}
</style>
<footer>
    <p>© 2025 AI Financial Assistant. All rights reserved.</p>
</footer>
""", unsafe_allow_html=True)
