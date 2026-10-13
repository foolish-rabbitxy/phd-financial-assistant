"""HTTP server for the finance dashboard: auth, cached Alpaca data, scorecard, picks."""

from __future__ import annotations

import json
import secrets
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlparse

from . import scorecard as sc
from .alpaca_data import TTLCache, weekly_scorecard
from .auth import ResetTokens, Sessions, hash_password, password_problem, verify_password

log = logging.getLogger(__name__)

WEB = Path(__file__).parent / "web"
PICKS_EVERY_S = 3600
RANGES = {"new": "brain", "3m": 92, "1y": 366, "all": None}
# The multi-factor brain took over at the Monday 2026-10-12 08:30 run; its baseline is the account
# value at the previous close (Fri 2026-10-09), so Monday's trades and moves count toward it.
NEW_BRAIN_BASE = "2026-10-09"
NEW_BRAIN_FIRST_RUN = "2026-10-12"
# Extra lines on the comparison chart: name -> (kind, symbol). Gold and silver via their ETFs.
EXTRAS = {"gold": ("stock", "GLD"), "silver": ("stock", "SLV"), "btc": ("crypto", "BTC/USD")}
PUBLIC = {
    "/login": ("login.html", "text/html; charset=utf-8"),
    "/forgot": ("forgot.html", "text/html; charset=utf-8"),
    "/reset": ("reset.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css"),
    "/login.js": ("login.js", "application/javascript"),
    "/reset.js": ("reset.js", "application/javascript"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/favicon.ico": ("favicon.svg", "image/svg+xml"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}
PRIVATE = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "application/javascript")}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def autopilot_timer() -> dict:
    """Next / last run of the weekly autopilot from its systemd timer."""
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", "trading-autopilot.timer",
             "-p", "NextElapseUSecRealtime", "-p", "LastTriggerUSec", "-p", "ActiveState"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    props = dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)
    return {"next": props.get("NextElapseUSecRealtime", ""), "last": props.get("LastTriggerUSec", ""),
            "active": props.get("ActiveState") == "active"}


class App:
    def __init__(self, cfg: dict, alpaca, sender, picks_fn, save_config=lambda c: None,
                 scorecard_rows=weekly_scorecard, timer=autopilot_timer):
        self.cfg, self.alpaca, self.sender, self.save_config = cfg, alpaca, sender, save_config
        self.sessions = Sessions(cfg["dashboard_password_hash"])
        self.resets = ResetTokens()
        self.account = TTLCache(alpaca.account, 60)
        self.positions = TTLCache(alpaca.positions, 60)
        self.fills = TTLCache(alpaca.fills, 300)
        self.history = TTLCache(alpaca.portfolio_history, 900)
        self.weekly = TTLCache(scorecard_rows, 300)
        self.timer = TTLCache(timer, 300)
        self._spy = {}
        self.spy = TTLCache(self._load_spy, 900)
        self.extras = TTLCache(self._load_extras, 900)
        self.picks_fn = picks_fn
        self.picks, self.picks_at, self.picks_error = None, 0.0, ""

    # ---- data ------------------------------------------------------------
    def _equity(self) -> list[tuple[str, float]]:
        return sc.parse_history(self.history.get() or {})

    def _load_spy(self):
        eq = self._equity()
        if not eq:
            return []
        start = (datetime.fromisoformat(eq[0][0]) - timedelta(days=10)).strftime("%Y-%m-%d")
        return sc.parse_spy(self.alpaca.spy_bars(start))

    def _load_extras(self) -> dict:
        eq = self._equity()
        if not eq:
            return {}
        start = (datetime.fromisoformat(eq[0][0]) - timedelta(days=10)).strftime("%Y-%m-%d")
        out = {}
        for name, (kind, sym) in EXTRAS.items():
            bars = self.alpaca.crypto_bars(sym, start) if kind == "crypto" else self.alpaca.stock_bars(sym, start)
            out[name] = sc.parse_spy(bars)
        return out

    def refresh_picks_forever(self) -> None:
        while True:
            try:
                self.picks, self.picks_error = self.picks_fn(), ""
            except Exception as e:  # keep yesterday's picks visible if scoring fails
                log.exception("picks failed")
                self.picks_error = str(e)
            self.picks_at = time.time()
            time.sleep(PICKS_EVERY_S)

    def summary(self) -> dict:
        eq, spy = self._equity(), self.spy.get() or []
        weekly = self.weekly.get() or []
        windows = {
            "new_brain": sc.window(eq, spy, NEW_BRAIN_BASE),
            "old_brain": sc.window(eq, spy, "0000", NEW_BRAIN_BASE),
        }
        acct = self.account.get() or {}
        positions = self.positions.get() or []
        errors = [c.error for c in (self.account, self.positions, self.fills, self.history, self.spy) if c.error]
        return {
            "account": acct, "positions": positions, "trades": self.fills.get() or [],
            "windows": windows, "new_brain_base": NEW_BRAIN_BASE, "new_brain_first_run": NEW_BRAIN_FIRST_RUN,
            "weekly": self._weekly_vs_spy(weekly), "timer": self.timer.get() or {},
            "errors": errors, "as_of": eq[-1][0] if eq else None,
        }

    def glance(self) -> dict:
        """Tiny summary for the home portal (served to this PC only)."""
        d = self.summary()
        w = d["windows"]["new_brain"] or {}
        return {"verdict": w.get("verdict"), "diff_pts": w.get("diff_pts"), "bot_pct": w.get("bot_pct"),
                "spy_pct": w.get("spy_pct"), "since": NEW_BRAIN_FIRST_RUN, "equity": (d["account"] or {}).get("equity"),
                "next_run": (d["timer"] or {}).get("next")}

    @staticmethod
    def _weekly_vs_spy(rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        e0, s0 = rows[0]["equity"], rows[0]["spy"]
        return [{**r, "bot_pct": round((r["equity"] / e0 - 1) * 100, 2),
                 "spy_pct": round((r["spy"] / s0 - 1) * 100, 2)} for r in reversed(rows)]

    def chart(self, rng: str) -> dict:
        eq, spy = self._equity(), self.spy.get() or []
        days = RANGES[rng]
        start = "0000"
        if days == "brain":
            start = NEW_BRAIN_BASE
        elif days and eq:
            start = (datetime.fromisoformat(eq[-1][0]) - timedelta(days=days)).strftime("%Y-%m-%d")
        return {"series": sc.same_money_series(eq, spy, start, self.extras.get() or {}), "range": rng}

    # ---- passwords -------------------------------------------------------
    def _store_password(self, new: str, keep: str | None) -> None:
        h = hash_password(new)
        self.cfg["dashboard_password_hash"] = h
        self.save_config(self.cfg)
        self.sessions.set_password(h, keep=keep)

    def change_password(self, current, new, repeat, keep) -> tuple[bool, str]:
        if not verify_password(current, self.sessions.password_hash):
            return False, "Current password is wrong."
        problem = password_problem(new, repeat)
        if problem:
            return False, problem
        self._store_password(new, keep)
        return True, "Password changed. Other signed-in devices were signed out."

    def send_reset_email(self) -> None:
        token = self.resets.issue(time.time())
        if not token:
            return
        link = f"{self.cfg['public_url'].rstrip('/')}/reset?token={token}"
        try:
            self.sender(
                "Finance dashboard: reset your password",
                "<p>Someone (hopefully you) asked to reset the finance dashboard password.</p>"
                f'<p>Open this link from a device on your home network within 15 minutes:<br><a href="{link}">{link}</a></p>'
                "<p>The link works once. If you didn't ask for this, ignore this email.</p>"
                f'<p>All sites at home: <a href="{self.cfg.get("home_url", "")}">{self.cfg.get("home_url", "")}</a></p>',
            )
        except Exception:
            log.exception("reset email failed")

    def reset_password(self, token, new, repeat) -> tuple[bool, str]:
        problem = password_problem(new, repeat)
        if problem:
            return False, problem
        if not self.resets.consume(token, time.time()):
            return False, "This reset link has expired or was already used. Request a new one."
        self._store_password(new, None)
        return True, "ok"


def make_handler(app: App):
    # Behind the home portal every request has already passed the portal's login, and we listen on this
    # PC only, so there is one standing session (its CSRF token still guards actions).
    portal = SimpleNamespace(csrf=secrets.token_urlsafe(24)) if app.cfg.get("behind_portal") else None

    class Handler(BaseHTTPRequestHandler):
        server_version = "FinanceDashboard"

        def log_message(self, fmt, *args):
            log.debug("%s %s", self.address_string(), fmt % args)

        def _token(self):
            c = SimpleCookie(self.headers.get("Cookie", ""))
            return c["fsession"].value if "fsession" in c else None

        def _session(self):
            return portal or app.sessions.get(self._token(), time.time())

        def _send(self, code, body: bytes, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode(), "application/json")

        def _redirect(self, to, extra=None):
            self._send(HTTPStatus.SEE_OTHER, b"", "text/plain", {"Location": to, **(extra or {})})

        def _file(self, name, ctype):
            self._send(200, (WEB / name).read_bytes(), ctype)

        def _form(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            form = parse_qs(self.rfile.read(min(n, 10_000)).decode(errors="replace"))
            return {k: v[0] for k, v in form.items()}

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/internal/glance":
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    return self._send(404, b"not found", "text/plain")
                return self._json(app.glance())
            if url.path in PUBLIC:
                return self._file(*PUBLIC[url.path])
            sess = self._session()
            if not sess:
                return self._json({"error": "login required"}, 401) if url.path.startswith("/api/") else self._redirect("/login")
            if url.path in PRIVATE:
                return self._file(*PRIVATE[url.path])
            if url.path == "/api/summary":
                return self._json({**app.summary(), "csrf": sess.csrf, "portal": bool(portal)})
            if url.path == "/api/chart":
                rng = parse_qs(url.query).get("range", ["all"])[0]
                return self._json(app.chart(rng)) if rng in RANGES else self._json({"error": "bad range"}, 400)
            if url.path == "/api/picks":
                return self._json({"picks": app.picks, "computed_at": app.picks_at, "error": app.picks_error})
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == "/login":
                tok = app.sessions.login(self._form().get("password", ""), time.time())
                if not tok:
                    return self._redirect("/login?error=1")
                cookie = f"fsession={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={int(app.sessions.ttl)}"
                return self._redirect("/", {"Set-Cookie": cookie})
            if url.path == "/forgot":
                app.send_reset_email()
                return self._redirect("/forgot?sent=1")
            if url.path == "/reset":
                f = self._form()
                ok, msg = app.reset_password(f.get("token", ""), f.get("password", ""), f.get("password2", ""))
                if ok:
                    return self._redirect("/login?reset=1")
                return self._redirect(f"/reset?token={quote(f.get('token', ''))}&error={quote(msg)}")
            sess = self._session()
            if not sess:
                return self._json({"error": "login required"}, 401)
            if url.path == "/logout":
                app.sessions.logout(self._token())
                return self._redirect("/login", {"Set-Cookie": "fsession=; Max-Age=0; Path=/"})
            if self.headers.get("X-CSRF-Token") != sess.csrf:
                return self._json({"error": "bad csrf token"}, 403)
            if url.path == "/api/password":
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    p = json.loads(self.rfile.read(min(n, 10_000)) or b"{}")
                except json.JSONDecodeError:
                    return self._json({"error": "bad json"}, 400)
                ok, msg = app.change_password(p.get("current", ""), p.get("new", ""), p.get("repeat", ""), self._token())
                return self._json({"ok": ok, "message": msg}, 200 if ok else 400)
            self._send(404, b"not found", "text/plain")

    return Handler


def serve(app: App) -> None:
    threading.Thread(target=app.refresh_picks_forever, name="picks", daemon=True).start()
    host = "127.0.0.1" if app.cfg.get("behind_portal") else app.cfg["listen_host"]
    httpd = ThreadingHTTPServer((host, app.cfg["listen_port"]), make_handler(app))
    log.info("listening on %s:%s%s", host, app.cfg["listen_port"], " (behind the home portal)" if app.cfg.get("behind_portal") else "")
    httpd.serve_forever()
