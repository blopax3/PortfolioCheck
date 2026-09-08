import unittest
from unittest.mock import patch

import pandas as pd

from api.portfolio_analysis.data_sources import (
    ReturnSeries,
    download_returns,
    normalize_isin,
    normalize_yahoo_symbol,
)


class DataSourcesTest(unittest.TestCase):
    def test_identifiers_match_fondoscope_rules(self):
        self.assertEqual(normalize_isin(" ie00b4l5y983 "), "IE00B4L5Y983")
        self.assertEqual(normalize_isin("IE00B4L5Y984"), "")
        self.assertEqual(normalize_yahoo_symbol(" vwce.de "), "VWCE.DE")
        self.assertEqual(normalize_yahoo_symbol("https://finance.yahoo.com/quote/VWCE.DE"), "")

    @patch("api.portfolio_analysis.data_sources.download_yahoo_returns")
    @patch("api.portfolio_analysis.data_sources.download_morningstar_returns")
    def test_isins_use_morningstar_and_symbols_use_yahoo(self, morningstar, yahoo):
        series = pd.Series([0.01], index=pd.to_datetime(["2025-01-02"]))
        morningstar.return_value = (series, "Fund")
        yahoo.return_value = (series, "ETF")

        isin_result = download_returns("IE00B4L5Y983", "2025-01-01", None, "EUR", "Fund")
        symbol_result = download_returns("VWCE.DE", "2025-01-01", None, "EUR", "ETF")

        self.assertIsInstance(isin_result, ReturnSeries)
        self.assertEqual(isin_result.source, "morningstar")
        self.assertEqual(symbol_result.source, "yahoo")
        yahoo.assert_called_once_with("VWCE.DE", "2025-01-01", None)

    def test_invalid_isin_check_digit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ISIN"):
            download_returns("IE00B4L5Y984", "2025-01-01", None, "EUR", "Fund")


if __name__ == "__main__":
    unittest.main()
