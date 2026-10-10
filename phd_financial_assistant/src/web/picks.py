"""Today's picks from the existing scoring engine, reshaped for the page (view-only)."""

from __future__ import annotations

import html
import re

TOP_N = 10
ALLOC_N = 5
FIELDS = ("symbol", "sector", "industry", "score", "rf_score", "xgb_score", "pe_ratio",
          "dividend_yield", "return_30d", "volatility_30d", "avg_sentiment", "market_cap")


def summary_from_explanation(expl_html: str) -> str:
    """engine.generate_explanation returns HTML; keep just the plain-text 'Summary:' sentence."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", expl_html))
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"Summary:\s*(.+)$", text)
    return m.group(1).strip() if m else text


def shape(ranked: list[dict], portfolio: list[dict], explain) -> dict:
    total = sum(p["allocation"] for p in portfolio) or 1.0
    return {
        "count": len(ranked),
        "top": [{k: s.get(k) for k in FIELDS} for s in ranked[:TOP_N]],
        "allocation": [
            {"symbol": p["symbol"], "weight_pct": round(p["allocation"] / total * 100, 1),
             "why": summary_from_explanation(explain(p))}
            for p in portfolio[:ALLOC_N]
        ],
    }


def compute() -> dict:
    from src.strategy.engine import (allocate_portfolio, enrich_sentiment, filter_and_score,
                                     generate_explanation, load_candidates)
    ranked = filter_and_score(enrich_sentiment(load_candidates(symbols=None)))
    return shape(ranked, allocate_portfolio(ranked, budget=100.0), generate_explanation)
