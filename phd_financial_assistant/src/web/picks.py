"""Today's picks from the multi-factor brain, reshaped for the page (view-only)."""

from __future__ import annotations

import math

TOP_TABLE = 25


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def shape(scored, picks: list[str], current: set[str], reasons) -> dict:
    rows = []
    for rank, (sym, r) in enumerate(scored.head(TOP_TABLE).iterrows(), 1):
        rows.append({
            "rank": rank, "symbol": sym, "sector": r.get("sector"), "score": _num(r.get("score")),
            "mom_12_1": _num(r.get("mom_12_1")), "mom_6_1": _num(r.get("mom_6_1")),
            "vol_1y": _num(r.get("vol_1y")), "pe_ratio": _num(r.get("pe_ratio")),
            "dividend_yield": _num(r.get("dividend_yield")), "roe": _num(r.get("roe")),
            "picked": sym in picks, "held": sym in current,
        })
    weight = round(100 / len(picks), 1) if picks else 0
    return {
        "count": len(scored),
        "top": rows,
        "allocation": [{"symbol": s, "weight_pct": weight, "why": reasons(scored.loc[s]),
                        "sector": scored.loc[s].get("sector"), "held": s in current} for s in picks],
    }


def compute(current_fn=None) -> dict:
    from src.strategy import live_picks, multifactor
    current = set(current_fn()) if current_fn else set()
    scored, picks = live_picks.run(current)
    return shape(scored, picks, current, multifactor.reasons)
