# src/dashboard/dashboard.py
import streamlit as st
from src.strategy.engine import load_candidates, filter_and_score, allocate_portfolio, generate_explanation
from datetime import datetime

st.set_page_config(page_title="📊 Financial Assistant Dashboard", layout="wide")
st.title("📈 AI Financial Assistant")
# Set last refreshed time if not already present
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# Display the last refresh time in milliseconds
formatted_time = st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
st.caption(f"🕒 Last refreshed: {formatted_time}")

# Add a brief description
st.markdown("""
Welcome to the AI Financial Assistant Dashboard! This tool helps you identify top stock picks based on various financial metrics and AI-driven sentiment analysis. 
It provides a comprehensive overview of potential investments, including Price-to-Earnings (P/E) ratios, dividend yields, and market sentiment.
You can also view suggested portfolio allocations and detailed explanations for each stock pick.
""")


# Load candidates and process
with st.spinner("Loading data..."):
    stocks = load_candidates()
    ranked = filter_and_score(stocks)
    portfolio = allocate_portfolio(ranked, budget=1000.0)

if not ranked:
    st.warning("No qualified stocks to show. Try updating your dataset.")
    st.stop()

# Show top picks
st.subheader("🏆 Top Picks")
st.dataframe([
    {
        "Symbol": s["symbol"],
        "Score": s["score"],
        "P/E": s["pe_ratio"],
        "Yield": s["dividend_yield"],
        "Sentiment": s["avg_sentiment"],
        "30d Return": s.get("return_30d"),
        "Volatility": s.get("volatility_30d")
    }
    for s in ranked[:5]
])

# Show allocation
st.subheader("💰 Suggested Allocation ($1000)")
st.dataframe([
    {
        "Symbol": s["symbol"],
        "Allocation ($)": s["allocation"],
        "Score": s["score"]
    }
    for s in portfolio
])

# Show explanations
st.subheader("🧠 Explanation for Each Pick")
for stock in portfolio:
    st.markdown(f"**{stock['symbol']}**: {generate_explanation(stock)}")
# Add a button to refresh data
if st.button("🔄 Refresh Data"):
    with st.spinner("Refreshing data..."):
        stocks = load_candidates()
        ranked = filter_and_score(stocks)
        portfolio = allocate_portfolio(ranked, budget=1000.0)
        st.session_state.last_refresh = datetime.now()
    st.success("Data refreshed successfully!")
    ##############
    ##############
    # Restart the script to reflect changes
    ##############
    ##############
    st.rerun()  # Restart the script


# Sidebar
st.sidebar.title("📂 Navigation")  
st.sidebar.markdown("- [Home](#)")
st.sidebar.markdown("- [Top Picks](#top-picks)")
st.sidebar.markdown("- [Suggested Allocation](#suggested-allocation)")      
st.sidebar.markdown("- [Explanations](#explanation-for-each-pick)")
st.sidebar.markdown("- [Refresh Data](#)")
st.sidebar.markdown("- [Contact](#)")

# Footer
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
