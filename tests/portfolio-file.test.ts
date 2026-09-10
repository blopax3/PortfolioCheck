import assert from "node:assert/strict";
import { parsePortfolioFile } from "../app/portfolio-file";

const portfolio = parsePortfolioFile(JSON.stringify({
  version: 1,
  name: "Cartera permanente",
  assets: [
    { symbol: "ES0112611001", weight: 60 },
    { symbol: "SGLD.MI", weight: 40 }
  ],
  benchmark: { symbol: "^STOXX50E" },
  period: { startDate: "2015-01-01", endDate: null },
  currency: "EUR"
}));

assert.equal(portfolio.assets.length, 2);
assert.equal(portfolio.benchmark?.symbol, "^STOXX50E");
assert.throws(
  () => parsePortfolioFile(JSON.stringify({ ...portfolio, assets: [{ symbol: "VWCE.DE", weight: 90 }] })),
  /sumar 100%/
);
