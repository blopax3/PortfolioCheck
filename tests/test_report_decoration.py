import unittest

from api.portfolio_analysis.report import _insert_section


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


if __name__ == "__main__":
    unittest.main()
