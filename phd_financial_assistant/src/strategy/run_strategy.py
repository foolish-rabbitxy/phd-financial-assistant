# run_strategy.py

from src.strategy.engine import (
    load_candidates,
    filter_and_score,
    allocate_portfolio,
    generate_explanation,
)
from src.utils.mail import send_email
import os

def main():
    print("📊 Loading candidates...")
    stocks = load_candidates()

    print("✅ Filtering and scoring...")
    ranked = filter_and_score(stocks)

    if not ranked:
        print("⚠️ No valid stocks found.")
        return

    print("\n📈 Top picks:")
    for stock in ranked[:5]:
        print(f"{stock['symbol']}: Score={stock['score']}, P/E={stock['pe_ratio']}, Yield={stock['dividend_yield']}, Sentiment={round(stock['avg_sentiment'] or 0, 2)}")

    print("\n💰 Suggested allocation ($1000):")
    portfolio = allocate_portfolio(ranked, budget=1000.0)
    for stock in portfolio:
        print(f"{stock['symbol']}: ${stock['allocation']} → Score: {stock['score']}")

    print("\n📊 Details with 30d Return & Volatility:")
    for stock in portfolio:
        print(f"{stock['symbol']}: Score={stock['score']}, P/E={stock['pe_ratio']}, Yield={stock['dividend_yield']}, "
              f"Sentiment={round(stock['avg_sentiment'] or 0, 2)}, 30d Return={stock.get('return_30d')}%, "
              f"Volatility={stock.get('volatility_30d')}%")

    print("\n🧠 Explanation for each pick:")
    for stock in portfolio:
        explanation = generate_explanation(stock)
        print(f"- {explanation}")

    # =========================
    # 📧 Send HTML Email Report
    # =========================
    rows = ""
    for s in portfolio:
        rows += f"""
        <tr>
            <td>{s['symbol']}</td>
            <td>{s['score']}</td>
            <td>{s['pe_ratio']}</td>
            <td>{s['dividend_yield']}</td>
            <td>{s['avg_sentiment']}</td>
            <td>{s.get('return_30d', 'N/A')}</td>
            <td>{s.get('volatility_30d', 'N/A')}</td>
            <td>${s['allocation']}</td>
        </tr>
        """

    html_report = f"""
    <html>
    <head>
      <style>
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
        th {{ background-color: #f2f2f2; }}
      </style>
    </head>
    <body>
      <h2>📈 Daily Investment Report</h2>
      <table>
        <tr>
          <th>Symbol</th>
          <th>Score</th>
          <th>P/E Ratio</th>
          <th>Yield</th>
          <th>Sentiment</th>
          <th>30d Return</th>
          <th>Volatility</th>
          <th>Allocation ($)</th>
        </tr>
        {rows}
      </table>
    </body>
    </html>
    """

    send_email(
        subject="📈 Daily Investment Report",
        body=html_report,
        to_email=os.getenv("EMAIL_RECEIVER"),
        is_html=True
    )


if __name__ == "__main__":
    main()
