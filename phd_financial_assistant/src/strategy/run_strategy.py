# src/strategy/run_strategy.py

import sys
from src.strategy.engine import load_candidates, filter_and_score, allocate_portfolio, generate_explanation
from src.utils.mail import send_email

def main(send_mail=False):
    print("📊 Loading candidates...")
    stocks = load_candidates()
    print("✅ Filtering and scoring...")
    ranked = filter_and_score(stocks)
    portfolio = allocate_portfolio(ranked, budget=1000.0)

    print("\n📈 Top picks:")
    for stock in ranked[:5]:
        print(f"{stock['symbol']}: Score={stock['score']}, P/E={stock['pe_ratio']}, Yield={stock['dividend_yield']}, Sentiment={stock.get('avg_sentiment', 0)}")

    print("\n💰 Suggested allocation ($1000):")
    for stock in portfolio:
        print(f"{stock['symbol']}: ${stock['allocation']} → Score: {stock['score']}")

    print("\n📊 Details with 30d Return & Volatility:")
    for stock in portfolio:
        print(f"{stock['symbol']}: Score={stock['score']}, P/E={stock['pe_ratio']}, Yield={stock['dividend_yield']}, Sentiment={stock.get('avg_sentiment', 0)}, 30d Return={stock.get('return_30d')}%, Volatility={stock.get('volatility_30d')}%")

    print("\n🧠 Explanation for each pick:")
    for stock in portfolio:
        print(f"- {generate_explanation(stock)}")

    # ---- Email summary as HTML ----
    if send_mail:
        html = "<h2>Daily Portfolio Picks</h2>"
        html += "<table border=1 cellpadding=6><tr><th>Symbol</th><th>Score</th><th>P/E</th><th>Yield</th><th>Sentiment</th><th>30d Return</th><th>Volatility</th></tr>"
        for stock in portfolio:
            html += f"<tr><td>{stock['symbol']}</td><td>{stock['score']}</td><td>{stock['pe_ratio']}</td><td>{stock['dividend_yield']}</td><td>{stock.get('avg_sentiment', 0)}</td><td>{stock.get('return_30d')}</td><td>{stock.get('volatility_30d')}</td></tr>"
        html += "</table>"

        html += "<h3>Explanations</h3><ul>"
        for stock in portfolio:
            html += f"<li>{generate_explanation(stock)}</li>"
        html += "</ul>"

        try:
            send_email(
                subject="Daily Portfolio Picks",
                html_body=html
            )
            print("✅ Email sent.")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    send_mail = "--email" in sys.argv
    main(send_mail=send_mail)
