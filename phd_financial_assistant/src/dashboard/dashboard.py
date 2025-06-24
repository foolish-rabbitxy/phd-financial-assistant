# src/dashboard/dashboard.py

import streamlit as st
from src.strategy.engine import load_candidates, filter_and_score, allocate_portfolio, generate_explanation, enrich_sentiment
import sqlite3
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="📊 Financial Assistant Dashboard", layout="wide")
st.title("📈 AI Financial Assistant")

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
    portfolio = allocate_portfolio(ranked, budget=1000.0)

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

st.subheader("💰 Suggested Allocation ($1000)")
st.dataframe([
    {
        "Symbol": s["symbol"],
        "Allocation ($)": s["allocation"],
        "Score": s["score"]
    }
    for s in portfolio
])

st.subheader("🧠 Explanation for Each Pick")
for stock in portfolio:
    st.markdown(f"**{stock['symbol']}**: {generate_explanation(stock)}")

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
        st.success("Bought top picks! Refresh the dashboard to see your holdings.")
with col2:
    if st.button("🗑️ Reset Portfolio"):
        reset_portfolio()
        st.success("Simulated portfolio reset. Refresh to verify.")

# Optionally, add explanations for portfolio performance, Sharpe ratio, etc. in future!


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
