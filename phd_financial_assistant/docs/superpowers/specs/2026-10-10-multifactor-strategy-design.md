# Multi-factor Strategy ("new brain") — Design

Date: 2026-10-10. Status: approved in conversation ("write it up and build it").
Paper account only. Goal: replace the synthetic-target XGBoost score with a transparent,
evidence-based factor ranking, validated by an honest backtest before it trades.

## Universe & filters

S&P 500 (fundamentals table, ~508 tickers). A stock is eligible only if all hold:
- **Profitable:** P/E > 0 (replaces "P/E ≤ 40", which excluded growth leaders).
- **Uptrend:** last close > 200-trading-day average.
- **Enough history:** ≥ 253 daily closes.
Dividends are a scoring input, not a filter; yields are stored as percent (9.56 = 9.56 %), which
the old `< 0.01` check misread (it filtered almost nothing).

## Score

Each factor is converted to a percentile rank (0–1) across eligible stocks; missing data → 0.5
(neutral). Score = weighted sum.

| Factor | Definition | Weight | Backtestable |
|---|---|---|---|
| mom_12_1 | close[t−21] / close[t−252] − 1 | 0.35 | yes |
| mom_6_1 | close[t−21] / close[t−126] − 1 | 0.15 | yes |
| low_vol | −stdev of daily returns, last 252 days | 0.15 | yes |
| value | earnings yield = 1 / P/E | 0.10 | snapshot |
| quality | mean rank of ROE, profit margin, −debt/equity (Yahoo Finance) | 0.15 | snapshot |
| dividend | dividend yield | 0.05 | snapshot |
| sentiment | mean news sentiment | 0.05 | no |

## Portfolio

Top 15, equal weight, ≤ 3 per sector. Hysteresis: a current holding is kept while it stays eligible
and ranks in the top 25, so the weekly rebalance doesn't churn. Prices: Alpaca daily bars,
split/dividend adjusted.

## Validation

`src.backtest.run_backtest` gains a `multifactor_price` rule (the three price factors + trend filter
+ sector cap, top 15 equal weight, monthly) compared with SPY 2017–2026, 10 bps costs. Caveat:
today's S&P list (survivorship bias) — shown next to the result. The snapshot and sentiment factors
cannot be backtested and carry 35 % of the live weight.

## Rollout

1. Build + backtest, report to the user. 2. On approval, the autopilot and dashboard switch to
`src.strategy.multifactor` (old engine kept for reference). The scorecard keeps measuring vs SPY.
