import unittest

from src.web.alpaca_data import TTLCache, group_fills


class GroupFillsTest(unittest.TestCase):
    def test_merges_partial_fills_per_day_symbol_side(self):
        rows = [
            {"transaction_time": "2026-10-05T13:35:11Z", "symbol": "BBY", "side": "buy", "qty": "2", "price": "87.82"},
            {"transaction_time": "2026-10-05T13:33:54Z", "symbol": "BBY", "side": "buy", "qty": "98", "price": "88.10"},
            {"transaction_time": "2026-10-05T13:33:00Z", "symbol": "VZ", "side": "sell", "qty": "64", "price": "45.89"},
            {"transaction_time": "2025-06-26T13:30:00Z", "symbol": "BBY", "side": "sell", "qty": "5", "price": "68.10"},
        ]
        t = group_fills(rows)
        self.assertEqual(len(t), 3)
        bby = t[0]
        self.assertEqual((bby["symbol"], bby["side"], bby["qty"]), ("BBY", "buy", 100.0))
        self.assertAlmostEqual(bby["price"], (2 * 87.82 + 98 * 88.10) / 100, places=2)
        self.assertEqual(t[-1]["date"], "2025-06-26")


class TTLCacheTest(unittest.TestCase):
    def test_caches_and_keeps_last_good_value(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 2:
                raise OSError("down")
            return len(calls)

        c = TTLCache(fn, ttl=60)
        self.assertEqual(c.get(now=100), 1)
        self.assertEqual(c.get(now=150), 1)
        self.assertEqual(c.get(now=200), 1)  # refresh failed, old value kept
        self.assertIn("down", c.error)


if __name__ == "__main__":
    unittest.main()
