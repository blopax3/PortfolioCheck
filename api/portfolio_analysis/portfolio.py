from __future__ import annotations

import pandas as pd

from .data_sources import ReturnSeries, download_returns
from .models import AnalysisInput


def build_portfolio(config: AnalysisInput) -> tuple[pd.Series, pd.Series | None, list[dict[str, str]], list[str]]:
    downloaded: list[ReturnSeries] = []
    metadata: list[dict[str, str]] = []
    warnings: list[str] = []

    for asset in config.assets:
        result = download_returns(
            symbol=asset.symbol,
            start=config.start_date,
            end=config.end_date,
            currency=config.currency,
            label=asset.name,
        )
        downloaded.append(result)
        if result.warning:
            warnings.append(result.warning)
        metadata.append(
            {
                "name": asset.name,
                "symbol": asset.symbol,
                "source": result.source,
                "weight": f"{asset.weight:.6f}",
            }
        )

    first_common_date = max(series.returns.first_valid_index() for series in downloaded)
    asset_returns = pd.DataFrame(
        {series.returns.name: series.returns for series in downloaded}
    ).sort_index()
    asset_returns = asset_returns.loc[first_common_date:].fillna(0)

    weights = pd.Series({asset.name: asset.weight for asset in config.assets}, dtype=float)
    growth = (1 + asset_returns).cumprod()
    growth = growth.div(growth.iloc[0])
    value = growth.mul(weights).sum(axis=1)
    portfolio_returns = value.pct_change().dropna().rename("PortfolioCheck")

    benchmark_returns = None
    if config.benchmark is not None:
        benchmark = download_returns(
            symbol=config.benchmark.symbol,
            start=str(asset_returns.index[0].date()),
            end=config.end_date,
            currency=config.currency,
            label=config.benchmark.name,
        )
        if benchmark.warning:
            warnings.append(benchmark.warning)
        metadata.append(
            {
                "name": config.benchmark.name,
                "symbol": config.benchmark.symbol,
                "source": benchmark.source,
                "weight": "benchmark",
            }
        )
        common = pd.concat([portfolio_returns, benchmark.returns], axis=1, join="inner").dropna()
        portfolio_returns = common["PortfolioCheck"]
        benchmark_returns = common[config.benchmark.name]

    if portfolio_returns.empty:
        raise ValueError("No hay suficientes datos comunes para construir el portfolio.")

    return portfolio_returns, benchmark_returns, metadata, warnings
