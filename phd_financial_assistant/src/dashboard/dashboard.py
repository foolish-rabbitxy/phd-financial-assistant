# src/dashboard/dashboard.py

import streamlit as st
from src.strategy.engine import load_candidates, filter_and_score, allocate_portfolio, generate_explanation, enrich_sentiment
import sqlite3
from datetime import datetime
import pandas as pd
from streamlit import rerun
import os

st.set_page_config(page_title="📊 Financial Assistant Dashboard", layout="wide")
st.title("📈 AI Financial Assistant")

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

# Draw the input box
allocation_input = st.text_input(
    "💰 Enter Suggested Allocation Amount (USD):",
    value=st.session_state["allocation_input"],
    key="allocation_input",
    max_chars=10,
    help="Enter a positive amount in US Dollars for your simulated investment."
)

allocation = parse_usd_amount(st.session_state["allocation_input"])

# Persist value on change, only if it's a valid amount
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

def make_html_link(name, url):
    return f'<a href="{url}" target="_blank">{name}</a>'

st.subheader("🏆 Top Picks")
table_data = []
for s in ranked[:10]:
    table_data.append({
        "Symbol": s["symbol"],
        "Score": s["score"],
        "P/E": s["pe_ratio"],
        "Yield": s["dividend_yield"],
        "Sentiment": s.get("avg_sentiment", 0),
        "30d Return": s.get("return_30d"),
        "Volatility": s.get("volatility_30d"),
        "Fidelity": make_html_link("Fidelity", f"https://digital.fidelity.com/prgw/digital/research/quote/dashboard/summary?symbol={s['symbol']}"),
        "Yahoo Finance": make_html_link("Yahoo Finance", f"https://finance.yahoo.com/quote/{s['symbol']}/"),
    })

df_links = pd.DataFrame(table_data)
st.markdown(
    df_links.to_html(escape=False, index=False),
    unsafe_allow_html=True
)

# --- Wrapped Allocation & Explanation Table ---
st.subheader(f"📝 Suggested Allocation & Rationale (${allocation:,.2f})")

def wrap_text_cell(text):
    # Ensures long explanations wrap in the table
    return f'<div style="white-space: pre-wrap; word-break: break-word; max-width: 500px;">{text}</div>'

allocation_table = []
for stock in portfolio:
    allocation_table.append({
        "Symbol": stock["symbol"],
        "Allocation ($)": f"${stock['allocation']:,.2f}",
        "Score": f"{stock['score']:.4f}",
        "Explanation": wrap_text_cell(generate_explanation(stock))
    })

df_alloc = pd.DataFrame(allocation_table)

# Custom CSS for wider table and wrapped text
st.markdown("""
<style>
table {width:100% !important;}
th, td {padding: 8px !important; vertical-align:top !important;}
td div {white-space: pre-wrap; word-break: break-word; max-width: 500px;}
</style>
""", unsafe_allow_html=True)

st.markdown(
    df_alloc.to_html(escape=False, index=False),
    unsafe_allow_html=True
)

from src.strategy.portfolio import buy_portfolio, get_portfolio_snapshot, reset_portfolio, create_portfolio_table

# Ensure the portfolio table exists
create_portfolio_table()

st.subheader("📦 Simulated Portfolio Holdings")
portfolio_df = get_portfolio_snapshot()
if not portfolio_df.empty:
    st.dataframe(portfolio_df)
else:
    st.info("No simulated portfolio yet. Click below to 'buy' the latest picks.")

col1, col2 = st.columns(2)
with col1:
    if st.button("💸 Simulate Buy Top Picks"):
        buy_portfolio(portfolio)
        st.success("Bought top picks! Refreshing dashboard...")
        rerun()
with col2:
    if st.button("🗑️ Reset Portfolio"):
        reset_portfolio()
        st.success("Simulated portfolio reset. Refreshing dashboard...")
        rerun()

from src.strategy.portfolio import get_portfolio_performance

st.subheader("📊 Portfolio Analytics")
performance = get_portfolio_performance()
if performance:
    st.markdown(f"""
    - **Total Return:** {performance['total_return']}%
    - **Annualized Volatility:** {performance['annual_volatility']}%
    - **Sharpe Ratio:** {performance['sharpe_ratio']}
    - **Start Value:** ${performance['start_value']}
    - **End Value:** ${performance['end_value']}
    - **Days Tracked:** {performance['num_days']}
    """)
else:
    st.info("Not enough data to calculate portfolio analytics yet.")

if st.button("🔄 Refresh Data"):
    st.session_state.last_refresh = datetime.now()
    st.success("Data refreshed successfully!")
    st.rerun()

st.sidebar.title("📂 Navigation")
st.sidebar.markdown("- [Home](#)")
st.sidebar.markdown("- [Top Picks](#top-picks)")
st.sidebar.markdown("- [Suggested Allocation](#suggested-allocation)")
st.sidebar.markdown("- [Explanations](#explanation-for-each-pick)")
st.sidebar.markdown("- [Refresh Data](#)")
st.sidebar.markdown("- [Contact](#contact)")

st.markdown("""
<style>
footer {
    position: fixed;
    bottom: 0;
    width: 100%;
    text-align: center;
    padding: 10px;
    background-color: #f1f1f1;
    font-size: 14px;
}
</style>
<footer>
    <p>© 2025 AI Financial Assistant. All rights reserved.</p>
</footer>
""", unsafe_allow_html=True)
