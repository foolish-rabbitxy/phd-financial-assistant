import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.web.auth import hash_password
from src.web.server import App, make_handler

FIX = Path(__file__).resolve().parents[1] / "fixtures"


class FakeAlpaca:
    def account(self):
        return {"status": "ACTIVE", "equity": "102245.56", "last_equity": "102000.00", "cash": "2095.29",
                "created_at": "2025-06-21T18:33:32Z"}

    def positions(self):
        return [{"symbol": "LYB", "qty": 418.0, "value": 25092.54, "cost": 24589.78, "pl": 502.76,
                 "pl_pct": 2.04, "today_pct": 0.0}]

    def fills(self):
        return [{"date": "2026-10-05", "symbol": "LYB", "side": "buy", "qty": 326.0, "price": 58.99,
                 "value": 19230.74, "time": "2026-10-05T13:32:43Z"}]

    def portfolio_history(self):
        return json.loads((FIX / "portfolio_history.json").read_text())

    def spy_bars(self, start):
        return json.loads((FIX / "spy_bars.json").read_text())

    def stock_bars(self, symbol, start):
        bars = json.loads((FIX / "spy_bars.json").read_text())["bars"]
        scale = {"GLD": 0.5, "SLV": 0.07}[symbol]  # any shape works; returns are what matter
        return {"bars": [{**b, "c": b["c"] * scale} for b in bars]}

    def crypto_bars(self, pair, start):
        return {"bars": [{"t": "2025-06-10T00:00:00Z", "c": 110000.0}, {"t": "2026-10-09T00:00:00Z", "c": 83000.0}]}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.mail = []
        cfg = {"dashboard_password_hash": hash_password("first-pass", iterations=1000),
               "public_url": "http://dash.local:8501", "listen_host": "127.0.0.1", "listen_port": 0}
        self.app = App(cfg, FakeAlpaca(), lambda subj, body: self.mail.append(body), lambda: {"top": []},
                       scorecard_rows=lambda: [{"date": "2026-10-05", "equity": 102449.05, "spy": 769.31}],
                       timer=lambda: {"next": "Mon 2026-10-12 08:30:00 EDT", "last": "", "active": True})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.opener = urllib.request.build_opener(NoRedirect)

    def tearDown(self):
        self.httpd.shutdown()

    def req(self, path, data=None, headers=None, cookie=None):
        h = dict(headers or {})
        if cookie:
            h["Cookie"] = cookie
        try:
            r = self.opener.open(urllib.request.Request(self.base + path, data=data, headers=h))
        except urllib.error.HTTPError as e:
            r = e
        return r.status, r.headers, r.read()

    def login(self, pw="first-pass"):
        _, h, _ = self.req("/login", data=f"password={pw}".encode())
        return (h.get("Set-Cookie") or "").split(";")[0]

    def test_everything_requires_login(self):
        self.assertEqual(self.req("/")[0], 303)
        self.assertEqual(self.req("/api/summary")[0], 401)
        self.assertEqual(self.req("/login")[0], 200)
        self.assertEqual(self.login("wrong"), "")

    def test_summary_scorecard(self):
        c = self.login()
        d = json.loads(self.req("/api/summary", cookie=c)[2])
        w = d["windows"]["since_open"]
        self.assertEqual(w["verdict"], "behind")
        self.assertLess(w["diff_pts"], -20)
        self.assertEqual(d["autopilot_start"], "2026-10-05")
        self.assertEqual(d["weekly"][0]["bot_pct"], 0.0)
        self.assertEqual(d["positions"][0]["symbol"], "LYB")
        self.assertEqual(len(d["csrf"]), 64)

    def test_chart_ranges(self):
        c = self.login()
        full = json.loads(self.req("/api/chart?range=all", cookie=c)[2])["series"]
        three = json.loads(self.req("/api/chart?range=3m", cookie=c)[2])["series"]
        self.assertGreater(len(full), len(three))
        self.assertEqual(three[0]["bot"], three[0]["spy"])
        for k in ("gold", "silver", "btc"):
            self.assertEqual(full[0][k], full[0]["bot"])  # every line starts from the same money
        self.assertAlmostEqual(full[-1]["btc"] / full[0]["btc"], 83000 / 110000, places=3)
        self.assertEqual(self.req("/api/chart?range=10y", cookie=c)[0], 400)

    def test_change_password_needs_csrf(self):
        c = self.login()
        csrf = json.loads(self.req("/api/summary", cookie=c)[2])["csrf"]
        body = json.dumps({"current": "first-pass", "new": "second-pass", "repeat": "second-pass"}).encode()
        self.assertEqual(self.req("/api/password", data=body, cookie=c)[0], 403)
        self.assertEqual(self.req("/api/password", data=body, cookie=c, headers={"X-CSRF-Token": csrf})[0], 200)
        self.assertNotEqual(self.login("second-pass"), "")

    def test_forgot_and_reset(self):
        self.req("/forgot", data=b"")
        self.req("/forgot", data=b"")  # rate-limited
        self.assertEqual(len(self.mail), 1)
        token = self.mail[0].split("reset?token=")[1].split('"')[0]
        status, h, _ = self.req("/reset", data=f"token={token}&password=brand-new-1&password2=brand-new-1".encode())
        self.assertEqual(h["Location"], "/login?reset=1")
        self.assertNotEqual(self.login("brand-new-1"), "")


if __name__ == "__main__":
    unittest.main()
