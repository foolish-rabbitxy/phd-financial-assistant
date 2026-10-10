"""Read-only Alpaca REST access for the dashboard (paper account only)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT / "local_db" / "market_data.db"
DATA_URL = "https://data.alpaca.markets"
TIMEOUT = 20


class AlpacaError(Exception):
    pass


class Alpaca:
    def __init__(self, env_path: Path = PROJECT / ".env"):
        load_dotenv(env_path)
        base = os.getenv("ALPACA_BASE_URL", "").rstrip("/")
        if "paper-api" not in base:
            raise AlpacaError("ALPACA_BASE_URL is not the paper endpoint; refusing to start")
        self.base = base.removesuffix("/v2")  # tolerate a /v2 suffix; endpoints below add their own
        self.headers = {
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
        }

    def _get(self, url: str, **params):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except OSError as e:
            raise AlpacaError(f"Alpaca request failed: {e}") from e

    def account(self) -> dict:
        a = self._get(f"{self.base}/v2/account")
        return {k: a.get(k) for k in ("status", "equity", "last_equity", "cash", "created_at")}

    def positions(self) -> list[dict]:
        return [
            {
                "symbol": p["symbol"], "qty": float(p["qty"]), "value": float(p["market_value"]),
                "cost": float(p["cost_basis"]), "pl": float(p["unrealized_pl"]),
                "pl_pct": round(float(p["unrealized_plpc"]) * 100, 2),
                "today_pct": round(float(p.get("change_today") or 0) * 100, 2),
            }
            for p in self._get(f"{self.base}/v2/positions")
        ]

    def fills(self, limit: int = 20) -> list[dict]:
        rows = self._get(f"{self.base}/v2/account/activities/FILL", direction="desc", page_size=100)
        return group_fills(rows)[:limit]

    def portfolio_history(self) -> dict:
        return self._get(f"{self.base}/v2/account/portfolio/history", period="all", timeframe="1D")

    def spy_bars(self, start: str) -> dict:
        """Daily SPY bars since `start`, dividend-adjusted, all pages."""
        bars, token = [], None
        while True:
            params = {"timeframe": "1Day", "start": start, "limit": 10000, "adjustment": "all", "feed": "iex"}
            if token:
                params["page_token"] = token
            page = self._get(f"{DATA_URL}/v2/stocks/SPY/bars", **params)
            bars += page.get("bars") or []
            token = page.get("next_page_token")
            if not token:
                return {"bars": bars}


def group_fills(rows: list[dict]) -> list[dict]:
    """Alpaca reports partial fills separately; merge them into one trade per day/symbol/side."""
    trades: dict[tuple, dict] = {}
    for f in rows:
        key = (f["transaction_time"][:10], f["symbol"], f["side"])
        qty, px = float(f["qty"]), float(f["price"])
        t = trades.setdefault(key, {"date": key[0], "symbol": key[1], "side": key[2], "qty": 0.0, "cost": 0.0,
                                    "time": f["transaction_time"]})
        t["qty"] += qty
        t["cost"] += qty * px
        t["time"] = max(t["time"], f["transaction_time"])
    out = sorted(trades.values(), key=lambda t: t["time"], reverse=True)
    for t in out:
        t["price"] = round(t["cost"] / t["qty"], 2) if t["qty"] else None
        t["value"] = round(t.pop("cost"), 2)
    return out


def weekly_scorecard(db_path: Path = DB_PATH) -> list[dict]:
    """The autopilot's Monday rows (run_date, equity, spy_price); empty if it never ran."""
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = db.execute("SELECT run_date, equity, spy_price FROM autopilot_scorecard ORDER BY run_date").fetchall()
        db.close()
    except sqlite3.Error:
        return []
    return [{"date": d, "equity": e, "spy": s} for d, e, s in rows]


class TTLCache:
    """Call `fn` at most once per `ttl` seconds; keep the last good value if a refresh fails."""

    def __init__(self, fn, ttl: float):
        self.fn, self.ttl = fn, ttl
        self.value, self.at, self.error = None, 0.0, ""
        self._lock = threading.Lock()

    def get(self, now: float | None = None):
        now = now or time.time()
        with self._lock:
            if now - self.at >= self.ttl:
                self.at = now
                try:
                    self.value, self.error = self.fn(), ""
                except Exception as e:  # surface any data-source failure on the page, keep old data
                    self.error = str(e)
            return self.value
