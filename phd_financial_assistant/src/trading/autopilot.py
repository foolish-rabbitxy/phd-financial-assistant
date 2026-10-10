# src/trading/autopilot.py
#
# Weekly unattended run: refresh data, rank picks, rebalance the Alpaca PAPER
# account, and log a scorecard vs. buy-and-hold SPY. Refuses to run against a
# live account — graduating to real money must be a deliberate manual change.
#
# Usage: python3 -m src.trading.autopilot [--dry-run] [--skip-refresh] [--email]

import sqlite3
import subprocess
import sys
from datetime import datetime

from src.trading.alpaca_client import BASE_URL, get_account_info, get_alpaca_portfolio, get_latest_price
from src.strategy import live_picks, multifactor
from src.strategy.portfolio import rebalance_alpaca_portfolio

DB_PATH = "local_db/market_data.db"
CASH_BUFFER = 0.98  # leave 2% cash so market orders don't fail on price moves
REFRESH_STEPS = ["src.data.fundamentals_main", "src.data.collector_main", "src.data.news_main", "src.data.quality"]
EMAIL_FOOTER = ('<p>Scorecard: <a href="http://192.168.50.62:8501/">http://192.168.50.62:8501</a><br>'
                'All sites at home: <a href="http://192.168.50.62/">http://192.168.50.62</a></p>')
DRIFT_BAND = 0.25  # only resize a held position once it is >25% away from its equal-weight target


def require_paper_account():
    if not BASE_URL or "paper-api" not in BASE_URL:
        sys.exit("Refusing to run: ALPACA_BASE_URL is not the paper endpoint.")


def refresh_data():
    for module in REFRESH_STEPS:
        result = subprocess.run([sys.executable, "-m", module])
        if result.returncode != 0:
            print(f"WARNING: {module} failed (exit {result.returncode}); continuing with existing data.")


def record_scorecard(equity, spy_price):
    """Append today's equity + SPY price; return (bot_return_pct, spy_return_pct, start_date)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_scorecard (
            run_date TEXT PRIMARY KEY,
            equity REAL NOT NULL,
            spy_price REAL NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO autopilot_scorecard VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d"), equity, spy_price),
    )
    conn.commit()
    start_date, start_equity, start_spy = conn.execute(
        "SELECT run_date, equity, spy_price FROM autopilot_scorecard ORDER BY run_date LIMIT 1"
    ).fetchone()
    conn.close()
    return (
        100 * (equity / start_equity - 1),
        100 * (spy_price / start_spy - 1),
        start_date,
    )


def main(dry_run=False, skip_refresh=False, send_mail=False):
    require_paper_account()
    if not skip_refresh:
        refresh_data()

    equity = float(get_account_info()["portfolio_value"])
    current = {p["symbol"] for p in get_alpaca_portfolio()}
    scored, picks = live_picks.run(current)  # multi-factor brain (see docs/superpowers/specs)
    each = equity * CASH_BUFFER / len(picks)
    targets = [{"symbol": s, "allocation": each} for s in picks]
    min_diff = each * DRIFT_BAND

    if dry_run:
        planned = []
        record = lambda sym, qty, side: planned.append(f"{side.upper()} {qty} {sym}") or object()
        actions = rebalance_alpaca_portfolio(targets, min_diff=min_diff, order_fn=record)
    else:
        actions = rebalance_alpaca_portfolio(targets, min_diff=min_diff)

    spy = (get_latest_price("SPY") or {}).get("price")
    lines = [f"Equity: ${equity:,.2f}"]
    lines += [f"Target {s}: ${each:,.2f} - {multifactor.reasons(scored.loc[s])}" for s in picks]
    lines += actions
    if spy and not dry_run:
        bot_ret, spy_ret, start = record_scorecard(equity, float(spy))
        lines.append(f"Since {start}: bot {bot_ret:+.2f}% vs SPY {spy_ret:+.2f}% "
                     f"({'AHEAD' if bot_ret > spy_ret else 'BEHIND'} by {abs(bot_ret - spy_ret):.2f} pts)")

    report = "\n".join(("[DRY RUN] " if dry_run else "") + line for line in lines)
    print(report)

    if send_mail:
        from src.utils.mail import send_email
        try:
            send_email("Autopilot weekly report (paper)", "<pre>" + report + "</pre>" + EMAIL_FOOTER)
        except Exception as e:
            print(f"Email failed: {e}")


if __name__ == "__main__":
    main(
        dry_run="--dry-run" in sys.argv,
        skip_refresh="--skip-refresh" in sys.argv,
        send_mail="--email" in sys.argv,
    )
