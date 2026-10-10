import json
import unittest
from pathlib import Path

from src.web import scorecard as sc

FIX = Path(__file__).resolve().parents[1] / "fixtures"


class ScorecardTest(unittest.TestCase):
    def setUp(self):
        self.eq = sc.parse_history(json.loads((FIX / "portfolio_history.json").read_text()))
        self.spy = sc.parse_spy(json.loads((FIX / "spy_bars.json").read_text()))

    def test_parse_real_data(self):
        self.assertEqual(self.eq[0], ("2025-06-18", 100000.0))
        self.assertEqual(self.eq[-1][0], "2026-10-09")  # Friday's close, not Saturday
        self.assertEqual(self.eq[-1][1], 102245.56)
        self.assertTrue(all(a[0] < b[0] for a, b in zip(self.spy, self.spy[1:])))

    def test_since_account_opened_is_far_behind(self):
        w = sc.window(self.eq, self.spy, "0000")
        self.assertEqual(w["start"], "2025-06-18")
        self.assertAlmostEqual(w["bot_pct"], 2.25, places=1)
        self.assertGreater(w["spy_pct"], 20)
        self.assertEqual(w["verdict"], "behind")
        self.assertAlmostEqual(w["diff_pts"], w["bot_pct"] - w["spy_pct"], places=1)

    def test_since_autopilot_window_starts_on_first_scorecard_day(self):
        w = sc.window(self.eq, self.spy, "2026-10-05")
        self.assertEqual(w["start"], "2026-10-05")
        self.assertLess(abs(w["bot_pct"]), 5)

    def test_window_with_end(self):
        w = sc.window(self.eq, self.spy, "0000", "2026-10-09")
        self.assertEqual((w["start"], w["end"]), ("2025-06-18", "2026-10-09"))
        mid = sc.window(self.eq, self.spy, "0000", "2025-12-31")
        self.assertLessEqual(mid["end"], "2025-12-31")

    def test_same_money_series_starts_equal(self):
        s = sc.same_money_series(self.eq, self.spy, "0000")
        self.assertEqual(s[0]["bot"], s[0]["spy"])
        self.assertEqual(len(s), len(self.eq))
        self.assertGreater(s[-1]["spy"], s[-1]["bot"])

    def test_weekend_uses_prior_close_and_missing_start_is_none(self):
        spy = [("2026-10-02", 100.0), ("2026-10-05", 110.0)]
        self.assertEqual(sc.value_on_or_before(spy, "2026-10-04"), 100.0)
        self.assertIsNone(sc.value_on_or_before(spy, "2026-10-01"))

    def test_verdict_and_short_window(self):
        self.assertEqual(sc.verdict(0.3), "even")
        self.assertEqual(sc.verdict(1.0), "ahead")
        self.assertEqual(sc.verdict(-1.0), "behind")
        self.assertIsNone(sc.window([("2026-01-01", 1.0)], [("2026-01-01", 1.0)], "0000"))


if __name__ == "__main__":
    unittest.main()
