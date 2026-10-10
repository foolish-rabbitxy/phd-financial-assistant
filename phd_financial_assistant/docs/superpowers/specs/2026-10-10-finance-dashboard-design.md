# Finance Dashboard Rebuild — Design

Date: 2026-10-10
Status: approved in conversation ("write it up and build it").

## Goal

Replace the Streamlit page with a password-protected, view-only dashboard that answers
**"Is the bot beating the S&P 500?"** first, in the same visual and technical style as
`~/Projects/avalon-dashboard`. The bot's logic (Alpaca client, scoring, autopilot) is unchanged.

## Non-goals

- Manual trading from the page (no Buy / Rebalance buttons) — the weekly autopilot is the only
  trader, so the scorecard stays clean.
- Sector / symbol / market-cap filters.
- Real-money trading of any kind (paper endpoint only, as today).

## Architecture

Stdlib-only Python web app in `src/web/`, run as the existing systemd user service
`finance-dashboard` (`python3 -m src.web run`), listening on `0.0.0.0:8501`.

```
src/web/
  alpaca_data.py  thin REST client: account, positions, fills, portfolio history, SPY bars
  scorecard.py    pure functions: "same money in SPY" series, returns for a window, verdict
  picks.py        wraps engine.load_candidates/enrich_sentiment/filter_and_score/allocate
  auth.py         password hash, sessions, lockout, reset tokens (same design as avalon-dashboard)
  server.py       routes, caches, wiring
  __main__.py     run | setup
  web/            index.html, login/forgot/reset pages, app.js, style.css (no CDNs)
tests/web/        unittest suites using recorded Alpaca responses
```

## Page (top to bottom)

1. **Scorecard** — verdict badge ("Behind by 25.8 pts" red / "Ahead by …" green / "Even" neutral),
   bot vs SPY return for two windows: since account opened, since autopilot started
   (first `autopilot_scorecard` row).
2. **Bot vs S&P 500 chart** — daily account equity vs the same starting money held in SPY
   (dividend-adjusted closes); ranges 3M / 1Y / All; hover tooltip; bot blue, SPY gray.
3. **Status tiles** — account value, cash, today's change, positions count, next autopilot run
   (from the systemd timer), last weekly report date.
4. **Holdings** — per position: value, unrealized P/L ($ and %, green/red), weight bar.
5. **Weekly scorecard** — `autopilot_scorecard` rows: date, bot equity, SPY price,
   bot vs SPY since the first row.
6. **Recent trades** — last 20 fills.
7. **Today's picks** — top 10 (scores, P/E, yield, 30-day return, volatility) and the top 5's
   plain-English rationale from `engine.generate_explanation`. View-only.

## Scorecard math

For a window starting at day d0: bot return = equity[last] / equity[d0] − 1;
SPY return = spy_close[last] / spy_close[d0] − 1 (adjusted closes, nearest trading day on or
before each equity date). "Same money in SPY" series = equity[d0] × spy_close[t] / spy_close[d0].
Verdict = bot − SPY in percentage points; |diff| < 0.5 pts → "Even".

## Auth

Same as avalon-dashboard: PBKDF2 password, HttpOnly SameSite=Strict session cookie, 5 failures →
60 s lockout, CSRF header on POSTs, forgot-password one-time 15-minute link emailed via the app's
existing `EMAIL_*` settings, at most one email per 5 minutes, change-password form.
Config: `~/.config/finance-dashboard/config.json` (mode 600): password hash, public_url.

## Caching

Account/positions/fills/history: 60 s. Picks: computed in a background thread at start and hourly
(~4 s each). Version of everything served from memory; no new persistent storage.

## Testing

Unit: scorecard math against recorded portfolio history + SPY bars; auth + reset flow; routes
against fake data sources. Live: service up, screenshots light/dark/phone.
