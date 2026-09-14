from __future__ import annotations

import pandas as pd

from .data_sources import ReturnSeries, download_returns
from .models import AnalysisInput


def _unique_label(label: str, used: set[str]) -> str:
    if label not in used:
        used.add(label)
        return label

    index = 2
    while f"{label} ({index})" in used:
        index += 1
    unique = f"{label} ({index})"
    used.add(unique)
    return unique


def build_portfolio(config: AnalysisInput) -> tuple[pd.Series, pd.Series | None, list[dict[str, str]], list[str]]:
    downloaded: list[ReturnSeries] = []
    metadata: list[dict[str, str]] = []
    warnings: list[str] = []
    used_labels: set[str] = set()

    for asset in config.assets:
        result = download_returns(
            symbol=asset.symbol,
            start=config.start_date,
            end=config.end_date,
            label=asset.name,
        )
        label = _unique_label(result.name or asset.symbol, used_labels)
        result = ReturnSeries(
            returns=result.returns.rename(label),
            source=result.source,
            symbol=result.symbol,
            name=label,
            currency=result.currency,
            warning=result.warning,
        )
        downloaded.append(result)
        if result.warning:
            warnings.append(result.warning)
        metadata.append(
            {
                "name": result.name,
                "symbol": asset.symbol,
                "source": result.source,
                "currency": result.currency or "No disponible",
                "weight": f"{asset.weight:.6f}",
            }
        )

    asset_returns = pd.DataFrame(
        {series.returns.name: series.returns for series in downloaded}
    ).sort_index().dropna()
    if asset_returns.empty:
        raise ValueError("No hay fechas comunes suficientes entre los activos.")

    weights = pd.Series(
        {series.name: asset.weight for series, asset in zip(downloaded, config.assets, strict=True)},
        dtype=float,
    )
    growth = (1 + asset_returns).cumprod()
    value = growth.mul(weights).sum(axis=1)
    portfolio_returns = value.pct_change(fill_method=None)
    portfolio_returns.iloc[0] = value.iloc[0] - 1
    portfolio_returns = portfolio_returns.dropna().rename("PortfolioCheck")

    benchmark_returns = None
    if config.benchmark is not None:
        benchmark = download_returns(
            symbol=config.benchmark.symbol,
            start=str(asset_returns.index[0].date()),
            end=config.end_date,
            label=config.benchmark.name,
        )
        benchmark_label = _unique_label(benchmark.name or config.benchmark.symbol, used_labels)
        benchmark = ReturnSeries(
            returns=benchmark.returns.rename(benchmark_label),
            source=benchmark.source,
            symbol=benchmark.symbol,
            name=benchmark_label,
            currency=benchmark.currency,
            warning=benchmark.warning,
        )
        if benchmark.warning:
            warnings.append(benchmark.warning)
        metadata.append(
            {
                "name": benchmark.name,
                "symbol": config.benchmark.symbol,
                "source": benchmark.source,
                "currency": benchmark.currency or "No disponible",
                "weight": "benchmark",
            }
        )
        common = pd.concat([portfolio_returns, benchmark.returns], axis=1, join="inner").dropna()
        portfolio_returns = common["PortfolioCheck"]
        benchmark_returns = common[benchmark.name]

    if portfolio_returns.empty:
        raise ValueError("No hay suficientes datos comunes para construir el portfolio.")

    return portfolio_returns, benchmark_returns, metadata, warnings
