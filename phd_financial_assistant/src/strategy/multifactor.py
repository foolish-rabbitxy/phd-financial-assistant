# src/strategy/multifactor.py
#
# Transparent multi-factor stock ranking (replaces the synthetic-target XGBoost score).
# Design: docs/superpowers/specs/2026-10-10-multifactor-strategy-design.md
#
# Pure functions over a price DataFrame (index = trading days, columns = symbols, values =
# split/dividend-adjusted closes) plus a per-symbol fundamentals table.

from __future__ import annotations

import pandas as pd

WEIGHTS = {
    "mom_12_1": 0.35,
    "mom_6_1": 0.15,
    "low_vol": 0.15,
    "value": 0.10,
    "quality": 0.15,
    "dividend": 0.05,
    "sentiment": 0.05,
}
PRICE_FACTORS = ("mom_12_1", "mom_6_1", "low_vol")
TOP_N, PER_SECTOR, KEEP_RANK = 15, 3, 25
MIN_HISTORY, TREND_DAYS, SKIP, YEAR, HALF = 253, 200, 21, 252, 126


def price_factors(prices: pd.DataFrame) -> pd.DataFrame:
    """Momentum (skipping the last month), volatility and trend from adjusted closes."""
    p = prices.ffill()
    enough = p.notna().sum() >= MIN_HISTORY
    last, skip = p.iloc[-1], p.iloc[-1 - SKIP]
    out = pd.DataFrame({
        "mom_12_1": skip / p.iloc[-1 - YEAR] - 1,
        "mom_6_1": skip / p.iloc[-1 - HALF] - 1,
        "vol_1y": p.iloc[-YEAR - 1:].pct_change().std(),
        "uptrend": last > p.iloc[-TREND_DAYS:].mean(),
        "enough_history": enough,
    })
    out["low_vol"] = -out["vol_1y"]
    return out


def _rank(s: pd.Series) -> pd.Series:
    """Percentile rank 0–1 (higher = better); missing values sit in the middle."""
    return s.rank(pct=True).fillna(0.5)


def score(prices: pd.DataFrame, fundamentals: pd.DataFrame | None = None,
          weights: dict = WEIGHTS) -> pd.DataFrame:
    """One row per eligible symbol with each factor's rank and the weighted score, best first.

    `fundamentals` columns (all optional): pe_ratio, dividend_yield (percent units), sector,
    roe, profit_margin, debt_to_equity, sentiment.
    """
    f = price_factors(prices)
    if fundamentals is not None:
        f = f.join(fundamentals, how="left")
    pe = f["pe_ratio"] if "pe_ratio" in f else pd.Series(1.0, index=f.index)
    eligible = f["enough_history"] & f["uptrend"].fillna(False) & (pe > 0)
    f = f[eligible].copy()
    if f.empty:
        return f
    ranks = pd.DataFrame(index=f.index)
    for name in PRICE_FACTORS:
        ranks[name] = _rank(f[name])
    col = lambda c: f[c] if c in f else pd.Series(index=f.index, dtype=float)
    ranks["value"] = _rank(1 / col("pe_ratio"))
    ranks["dividend"] = _rank(col("dividend_yield").fillna(0.0))
    ranks["quality"] = pd.concat(
        [_rank(col("roe")), _rank(col("profit_margin")), _rank(-col("debt_to_equity"))], axis=1).mean(axis=1)
    ranks["sentiment"] = _rank(col("sentiment"))
    used = {k: w for k, w in weights.items() if k in ranks}
    total = sum(used.values())
    f["score"] = sum(ranks[k] * w for k, w in used.items()) / total
    for k in used:
        f[f"r_{k}"] = ranks[k]
    return f.sort_values("score", ascending=False)


def select(scored: pd.DataFrame, current: set[str] = frozenset(), top_n: int = TOP_N,
           per_sector: int = PER_SECTOR, keep_rank: int = KEEP_RANK) -> list[str]:
    """Pick `top_n` names, ≤ `per_sector` per sector. Current holdings still ranked within
    `keep_rank` are kept first, so a small rank change doesn't cause a trade."""
    order = list(scored.index)
    sector = scored["sector"] if "sector" in scored else pd.Series("?", index=scored.index)
    picks, per = [], {}

    def take(sym):
        sec = sector.get(sym) or "?"
        if per.get(sec, 0) < per_sector and sym not in picks and len(picks) < top_n:
            picks.append(sym)
            per[sec] = per.get(sec, 0) + 1

    for sym in order[:keep_rank]:
        if sym in current:
            take(sym)
    for sym in order:
        take(sym)
    return picks


def reasons(row: pd.Series) -> str:
    """Plain-English summary of a pick's strongest factors."""
    labels = {"mom_12_1": "strong 12-month momentum", "mom_6_1": "strong 6-month momentum",
              "low_vol": "low volatility", "value": "cheap vs. earnings", "quality": "high-quality business",
              "dividend": "solid dividend", "sentiment": "upbeat news"}
    top = sorted(((row.get(f"r_{k}", 0.5), k) for k in labels), reverse=True)[:3]
    parts = [f"{labels[k]} (top {max(1, round((1 - r) * 100))}%)" for r, k in top if r >= 0.6]
    m = row.get("mom_12_1")
    lead = f"Up {m * 100:.0f}% over the past year (excluding last month); " if pd.notna(m) else ""
    return lead + (", ".join(parts) if parts else "balanced across factors") + "."
