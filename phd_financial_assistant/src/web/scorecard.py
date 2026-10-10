"""Bot-vs-S&P 500 scorecard math. Pure functions over (date, value) series; dates are 'YYYY-MM-DD'."""

from __future__ import annotations

import bisect
from datetime import datetime
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")
EVEN_PTS = 0.5  # differences smaller than this many percentage points read as "Even"


def parse_history(ph: dict) -> list[tuple[str, float]]:
    """Alpaca /v2/account/portfolio/history (timeframe=1D) → [(date, equity)], skipping empty days.

    Daily points are stamped 20:00 New York time on the trading day, so read the date in that zone
    (in UTC they would land on the next day)."""
    out = []
    for ts, eq in zip(ph.get("timestamp", []), ph.get("equity", [])):
        if eq:
            out.append((datetime.fromtimestamp(ts, MARKET_TZ).strftime("%Y-%m-%d"), float(eq)))
    return out


def parse_spy(bars: dict) -> list[tuple[str, float]]:
    """Alpaca daily bars (adjustment=all, so dividends are folded in) → [(date, close)]."""
    return [(b["t"][:10], float(b["c"])) for b in bars.get("bars", [])]


def value_on_or_before(series: list[tuple[str, float]], date: str) -> float | None:
    """Value at `date`, or the last one before it (weekends, holidays); None if the series starts later."""
    dates = [d for d, _ in series]
    i = bisect.bisect_right(dates, date) - 1
    return series[i][1] if i >= 0 else None


def window(equity: list[tuple[str, float]], spy: list[tuple[str, float]], start: str,
           end: str = "9999") -> dict | None:
    """Returns from `start` to `end` (first/last equity day inside them) for the bot and for SPY."""
    eq = [(d, v) for d, v in equity if start <= d <= end]
    if len(eq) < 2:
        return None
    (d0, e0), (d1, e1) = eq[0], eq[-1]
    s0, s1 = value_on_or_before(spy, d0), value_on_or_before(spy, d1)
    if not s0 or not s1:
        return None
    bot, idx = e1 / e0 - 1, s1 / s0 - 1
    diff = (bot - idx) * 100
    return {
        "start": d0, "end": d1,
        "bot_pct": round(bot * 100, 2), "spy_pct": round(idx * 100, 2),
        "diff_pts": round(diff, 2), "verdict": verdict(diff),
        "bot_value": round(e1, 2), "spy_value": round(e0 * (1 + idx), 2),
    }


def verdict(diff_pts: float) -> str:
    if abs(diff_pts) < EVEN_PTS:
        return "even"
    return "ahead" if diff_pts > 0 else "behind"


def same_money_series(equity: list[tuple[str, float]], spy: list[tuple[str, float]], start: str,
                      others: dict[str, list[tuple[str, float]]] | None = None) -> list[dict]:
    """Daily bot equity next to what its starting value would be worth held in SPY (and in each
    of `others`, e.g. gold, silver, bitcoin), on the bot's trading days."""
    eq = [(d, v) for d, v in equity if d >= start]
    if not eq:
        return []
    assets = {"spy": spy, **(others or {})}
    base = {k: value_on_or_before(series, eq[0][0]) for k, series in assets.items()}
    out = []
    for d, v in eq:
        point = {"date": d, "bot": round(v, 2)}
        for k, series in assets.items():
            x = value_on_or_before(series, d)
            point[k] = round(eq[0][1] * x / base[k], 2) if x and base[k] else None
        out.append(point)
    return out
