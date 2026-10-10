import unittest

import numpy as np
import pandas as pd

from src.strategy import multifactor as mf


def make_prices(n=300, **trends):
    """Synthetic adjusted closes: each symbol grows at its daily rate, with optional noise."""
    idx = pd.bdate_range("2025-01-01", periods=n)
    rng = np.random.default_rng(0)
    data = {}
    for sym, (rate, noise) in trends.items():
        steps = 1 + rate + rng.normal(0, noise, n)
        data[sym] = 100 * np.cumprod(steps)
    return pd.DataFrame(data, index=idx)


class FactorTest(unittest.TestCase):
    def test_momentum_skips_last_month_and_trend(self):
        p = make_prices(UP=(0.002, 0.0), DOWN=(-0.002, 0.0))
        f = mf.price_factors(p)
        expected = p["UP"].iloc[-22] / p["UP"].iloc[-253] - 1
        self.assertAlmostEqual(f.loc["UP", "mom_12_1"], expected)
        self.assertTrue(f.loc["UP", "uptrend"])
        self.assertFalse(f.loc["DOWN", "uptrend"])

    def test_filters_unprofitable_downtrend_and_short_history(self):
        p = make_prices(A=(0.002, 0.01), B=(0.001, 0.01), LOSS=(0.003, 0.01), DOWN=(-0.002, 0.01))
        p.loc[p.index[:100], "B"] = np.nan  # only 200 days of history
        fund = pd.DataFrame({"pe_ratio": [20, 15, -5, 10]}, index=["A", "B", "LOSS", "DOWN"])
        s = mf.score(p, fund)
        self.assertEqual(list(s.index), ["A"])

    def test_scores_prefer_momentum_and_quality(self):
        p = make_prices(FAST=(0.003, 0.01), SLOW=(0.0005, 0.01))
        fund = pd.DataFrame({"pe_ratio": [25, 25], "roe": [0.3, -0.05], "profit_margin": [0.2, -0.01],
                             "debt_to_equity": [20, 150], "dividend_yield": [0.5, 9.5], "sector": ["Tech", "Materials"]},
                            index=["FAST", "SLOW"])
        s = mf.score(p, fund)
        self.assertEqual(s.index[0], "FAST")
        self.assertGreater(s.loc["SLOW", "r_dividend"], s.loc["FAST", "r_dividend"])  # yields read as percent
        self.assertIn("momentum", mf.reasons(s.loc["FAST"]))

    def test_missing_fundamentals_are_neutral(self):
        p = make_prices(A=(0.002, 0.01))
        s = mf.score(p, pd.DataFrame({"pe_ratio": [20]}, index=["A"]))
        self.assertEqual(s.loc["A", "r_quality"], 0.5)


class SelectTest(unittest.TestCase):
    def scored(self, sectors):
        idx = [f"S{i}" for i in range(len(sectors))]
        return pd.DataFrame({"score": np.linspace(1, 0, len(idx)), "sector": sectors}, index=idx)

    def test_sector_cap_and_size(self):
        s = self.scored(["Tech"] * 5 + ["Energy"] * 5 + ["Health"] * 10)
        picks = mf.select(s, top_n=6, per_sector=2)
        self.assertEqual(picks, ["S0", "S1", "S5", "S6", "S10", "S11"])

    def test_hysteresis_keeps_current_holdings_within_keep_rank(self):
        s = self.scored(["A", "B", "C", "D", "E", "F", "G", "H"])
        picks = mf.select(s, current={"S6", "S7"}, top_n=3, per_sector=3, keep_rank=7)
        self.assertEqual(picks, ["S6", "S0", "S1"])  # S6 kept (rank 7); S7 (rank 8) dropped


if __name__ == "__main__":
    unittest.main()
