from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetInput:
    name: str
    symbol: str
    weight: float


@dataclass(frozen=True)
class BenchmarkInput:
    name: str
    symbol: str


@dataclass(frozen=True)
class MonteCarloConfig:
    sessions: int = 126
    simulations: int = 200
    seed: int = 42
    goal: float = 0.05
    bust: float = -0.10


@dataclass(frozen=True)
class AnalysisInput:
    assets: list[AssetInput]
    benchmark: BenchmarkInput | None
    start_date: str
    end_date: str | None
    currency: str
    monte_carlo: MonteCarloConfig


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _parse_weight(value: Any) -> float:
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", ".").strip()
    try:
        weight = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Todos los pesos deben ser numericos.") from error
    return weight / 100 if weight > 1 else weight


def parse_payload(payload: dict[str, Any]) -> AnalysisInput:
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError("Introduce al menos un activo.")

    assets: list[AssetInput] = []
    for index, raw_asset in enumerate(raw_assets, start=1):
        if not isinstance(raw_asset, dict):
            raise ValueError(f"El activo {index} no tiene un formato valido.")

        symbol = _clean_string(
            raw_asset.get("symbol")
            or raw_asset.get("identifier")
            or raw_asset.get("isin")
            or raw_asset.get("yahooSymbol")
        ).upper()
        name = _clean_string(raw_asset.get("name")) or symbol or f"Activo {index}"
        weight = _parse_weight(raw_asset.get("weight"))

        if not symbol:
            raise ValueError(f"El activo {index} necesita ISIN o ticker Yahoo.")
        if weight < 0:
            raise ValueError("Los pesos no pueden ser negativos.")

        assets.append(
            AssetInput(
                name=name,
                symbol=symbol,
                weight=weight,
            )
        )

    total_weight = sum(asset.weight for asset in assets)
    if abs(total_weight - 1.0) > 0.0001:
        raise ValueError(f"Los pesos deben sumar 100%. Suman {total_weight:.2%}.")

    benchmark = None
    raw_benchmark = payload.get("benchmark")
    if isinstance(raw_benchmark, dict):
        benchmark_symbol = _clean_string(
            raw_benchmark.get("symbol")
            or raw_benchmark.get("identifier")
            or raw_benchmark.get("isin")
            or raw_benchmark.get("yahooSymbol")
        ).upper()
        benchmark_name = (
            _clean_string(raw_benchmark.get("name"))
            or benchmark_symbol
            or "Benchmark"
        )
        if benchmark_symbol:
            benchmark = BenchmarkInput(
                name=benchmark_name,
                symbol=benchmark_symbol,
            )

    raw_monte_carlo = payload.get("monteCarlo") if isinstance(payload.get("monteCarlo"), dict) else {}
    monte_carlo = MonteCarloConfig(
        sessions=int(raw_monte_carlo.get("sessions") or 126),
        simulations=int(raw_monte_carlo.get("simulations") or 200),
        seed=int(raw_monte_carlo.get("seed") or 42),
        goal=float(raw_monte_carlo.get("goal") or 0.05),
        bust=float(raw_monte_carlo.get("bust") or -0.10),
    )
    if monte_carlo.sessions < 20:
        raise ValueError("El horizonte Monte Carlo debe ser de al menos 20 sesiones.")
    if monte_carlo.simulations < 20:
        raise ValueError("Monte Carlo necesita al menos 20 simulaciones.")

    return AnalysisInput(
        assets=assets,
        benchmark=benchmark,
        start_date=_clean_string(payload.get("startDate")) or "2015-01-01",
        end_date=_clean_string(payload.get("endDate")) or None,
        currency=_clean_string(payload.get("currency")) or "EUR",
        monte_carlo=monte_carlo,
    )
