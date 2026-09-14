import unittest
from types import SimpleNamespace

import pandas as pd

from api.portfolio_analysis.report import _insert_section, _report_header


class ReportDecorationTest(unittest.TestCase):
    def test_places_custom_header_before_rule_and_content_after_it(self):
        result = _insert_section(
            "<html><head></head><body><div><h1>QuantStats</h1><hr><main>Metrics</main></div></body></html>",
            "<header>PortfolioCheck</header>",
            "<section>Portfolio</section>",
            "<footer>Legal</footer>",
        )

        self.assertLess(result.index("<header>"), result.index("<hr>"))
        self.assertLess(result.index("<hr>"), result.index("<section>"))
        self.assertLess(result.index("<main>"), result.index("<footer>"))
        self.assertIn(".pc-report-header", result)

    def test_header_uses_portfolio_context_instead_of_fixed_methodology(self):
        header = _report_header(
            SimpleNamespace(name="Cartera permanente"),
            [
                {"name": "Fondo", "weight": "0.6", "currency": "EUR"},
                {"name": "ETF", "weight": "0.4", "currency": "USD"},
            ],
            pd.Series([0.01], index=pd.to_datetime(["2025-01-02"])),
        )

        self.assertIn("Cartera permanente", header)
        self.assertIn("EUR, USD", header)
        self.assertNotIn("Sesiones/año", header)
        self.assertNotIn("Tipo sin riesgo", header)


if __name__ == "__main__":
    unittest.main()
