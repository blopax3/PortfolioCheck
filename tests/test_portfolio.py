import unittest
from unittest.mock import patch

import pandas as pd

from api.portfolio_analysis.data_sources import ReturnSeries
from api.portfolio_analysis.models import parse_payload
from api.portfolio_analysis.portfolio import build_portfolio


class PortfolioTest(unittest.TestCase):
    def test_keeps_first_weighted_return_and_uses_common_dates(self):
        dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
        downloaded = {
            "A": ReturnSeries(pd.Series([0.10, 0.20], index=dates), "test", "A", "A", "EUR"),
            "B": ReturnSeries(pd.Series([0.00], index=dates[1:]), "test", "B", "B", "USD"),
        }

        with patch(
            "api.portfolio_analysis.portfolio.download_returns",
            side_effect=lambda symbol, **_: downloaded[symbol],
        ):
            returns, _, assets, _ = build_portfolio(
                parse_payload({"assets": [{"symbol": "A", "weight": 50}, {"symbol": "B", "weight": 50}]})
            )

        self.assertEqual(list(returns.index), [dates[1]])
        self.assertAlmostEqual(returns.iloc[0], 0.10)
        self.assertEqual([asset["currency"] for asset in assets], ["EUR", "USD"])

    def test_validates_payload_boundaries(self):
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            parse_payload([])
        with self.assertRaisesRegex(ValueError, "porcentajes"):
            parse_payload({"assets": [{"symbol": "A", "weight": 0}]})
        with self.assertRaisesRegex(ValueError, "fecha final"):
            parse_payload({"assets": [{"symbol": "A", "weight": 100}], "startDate": "2025-02-01", "endDate": "2025-01-01"})
        with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
            parse_payload({"assets": [{"symbol": "A", "weight": 100}], "startDate": "20250201"})
        with self.assertRaisesRegex(ValueError, "benchmark"):
            parse_payload({"assets": [{"symbol": "A", "weight": 100}], "benchmark": "SPY"})
        with self.assertRaisesRegex(ValueError, "5000"):
            parse_payload({"assets": [{"symbol": "A", "weight": 100}], "monteCarlo": {"simulations": 5001}})


if __name__ == "__main__":
    unittest.main()
