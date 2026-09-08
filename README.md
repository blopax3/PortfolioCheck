# PortfolioCheck

PortfolioCheck is a Next.js and Python application for portfolio analysis. It lets users enter funds, ISINs or Yahoo Finance tickers, assign weights, store reusable portfolios in the browser, and generate an HTML performance report with QuantStats.

## Features

- Portfolio editor with ISINs or tickers and percentage weights.
- Browser-based saved portfolios using `localStorage`.
- Optional benchmark configuration.
- Exact ISIN lookup through Morningstar and direct Yahoo Finance lookup for tickers.
- QuantStats HTML report generation from a Python serverless API.
- Vercel-ready project structure with a Next.js frontend and Python API route.

## Tech Stack

- Next.js 15
- React 19
- TypeScript
- Python serverless function under `api/analyze.py`
- QuantStats, pandas, NumPy, matplotlib and yfinance

## Local Development

Install JavaScript dependencies:

```bash
npm install
```

Run the full local stack:

```bash
npm run dev
```

This starts:

- Next.js at `http://127.0.0.1:3000`
- The local Python API at `http://127.0.0.1:8765`

`npm run dev` does not use `vercel dev`. It starts a small local Python server and configures a Next.js rewrite to proxy `/api/analyze` to that server.

If port `8765` is already in use, choose another local API port:

```bash
LOCAL_API_PORT=8766 npm run dev
```

To run only the Next.js frontend without the local Python API:

```bash
npm run dev:next
```

## Python Dependencies

For local Python work, you can create a virtual environment manually:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

If `.venv` exists, `npm run dev` uses it. Otherwise, if `uv` is installed, the dev script runs Python with dependencies from `requirements.txt` in an isolated environment.

## Quality Checks

Run the production build:

```bash
npm run build
```

Run TypeScript checks:

```bash
npm run typecheck
```

`npm run lint` currently aliases the TypeScript check so CI does not trigger Next.js' deprecated interactive lint setup.

## Vercel Deployment

The project is ready to deploy on Vercel:

1. Push the repository to GitHub.
2. Import the GitHub repository in Vercel.
3. Keep the default framework preset as Next.js.
4. Use the default build command:

```bash
npm run build
```

Vercel installs JavaScript dependencies from `package-lock.json` and Python dependencies from `requirements.txt`.

The Python API is exposed through:

```text
POST /api/analyze
```

`vercel.json` sets a 60-second maximum duration for `api/analyze.py`.

## API

### `POST /api/analyze`

Example request:

```json
{
  "assets": [
    {
      "symbol": "ES0112611001",
      "weight": 50
    }
  ],
  "benchmark": {
    "symbol": "SGLD.MI"
  },
  "startDate": "2015-01-01",
  "endDate": null,
  "currency": "EUR"
}
```

Notes:

- `symbol` can be a real ISIN or a Yahoo Finance ticker.
- Asset and benchmark names are resolved from Morningstar or Yahoo Finance when available. The API still accepts `name` as a compatibility fallback.
- Weights can be sent as percentages (`50`) or decimals (`0.5`).
- Valid ISINs are resolved through Morningstar; Yahoo symbols are sent directly to Yahoo Finance.
- Monte Carlo uses 126 trading sessions and 1,000 simulations by default.
- The response includes the generated HTML report, summary metrics, data sources used for each asset, and fallback warnings.

## Repository Hygiene

The repository should include source files, `package-lock.json`, `requirements.txt`, and deployment configuration. It should not include:

- `node_modules/`
- `.next/`
- `.vercel/`
- `.venv/`
- Python `__pycache__/`
- TypeScript build info files
