from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


DEFAULT_MONTE_CARLO_SIMULATIONS = 1000
MAX_ASSETS = 20
MAX_MONTE_CARLO_SESSIONS = 2520
MAX_MONTE_CARLO_SIMULATIONS = 5000
MAX_REQUEST_BYTES = 100_000


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
    simulations: int = DEFAULT_MONTE_CARLO_SIMULATIONS
    seed: int = 42
    goal: float = 0.05
    bust: float = -0.10


@dataclass(frozen=True)
class AnalysisInput:
    name: str
    assets: list[AssetInput]
    benchmark: BenchmarkInput | None
    start_date: str
    end_date: str | None
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
    if not 0 < weight <= 100:
        raise ValueError("Los pesos deben ser porcentajes mayores que 0 y menores o iguales que 100.")
    return weight / 100


def _parse_date(value: Any, label: str, default: str | None = None) -> str | None:
    clean = _clean_string(value) or default
    if clean is None:
        return None
    try:
        parsed = date.fromisoformat(clean)
    except ValueError as error:
        raise ValueError(f"{label} debe tener formato AAAA-MM-DD.") from error
    if parsed.isoformat() != clean:
        raise ValueError(f"{label} debe tener formato AAAA-MM-DD.")
    return clean


def parse_payload(payload: Any) -> AnalysisInput:
    if not isinstance(payload, dict):
        raise ValueError("La peticion debe contener un objeto JSON.")

    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError("Introduce al menos un activo.")
    if len(raw_assets) > MAX_ASSETS:
        raise ValueError(f"El portfolio admite un maximo de {MAX_ASSETS} activos.")

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
    if raw_benchmark is not None and not isinstance(raw_benchmark, dict):
        raise ValueError("El benchmark no tiene un formato valido.")
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

    start_date = _parse_date(payload.get("startDate"), "La fecha inicial", "2015-01-01")
    end_date = _parse_date(payload.get("endDate"), "La fecha final")
    if end_date and end_date < start_date:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")

    raw_monte_carlo = payload.get("monteCarlo")
    if raw_monte_carlo is not None and not isinstance(raw_monte_carlo, dict):
        raise ValueError("La configuracion Monte Carlo no es valida.")
    raw_monte_carlo = raw_monte_carlo or {}
    try:
        monte_carlo = MonteCarloConfig(
            sessions=int(raw_monte_carlo.get("sessions") or 126),
            simulations=int(raw_monte_carlo.get("simulations") or DEFAULT_MONTE_CARLO_SIMULATIONS),
            seed=int(raw_monte_carlo.get("seed") or 42),
            goal=float(raw_monte_carlo.get("goal") or 0.05),
            bust=float(raw_monte_carlo.get("bust") or -0.10),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("La configuracion Monte Carlo debe contener numeros validos.") from error
    if monte_carlo.sessions < 20:
        raise ValueError("El horizonte Monte Carlo debe ser de al menos 20 sesiones.")
    if monte_carlo.sessions > MAX_MONTE_CARLO_SESSIONS:
        raise ValueError(f"El horizonte Monte Carlo no puede superar {MAX_MONTE_CARLO_SESSIONS} sesiones.")
    if monte_carlo.simulations < 20:
        raise ValueError("Monte Carlo necesita al menos 20 simulaciones.")
    if monte_carlo.simulations > MAX_MONTE_CARLO_SIMULATIONS:
        raise ValueError(f"Monte Carlo no puede superar {MAX_MONTE_CARLO_SIMULATIONS} simulaciones.")

    return AnalysisInput(
        name=_clean_string(payload.get("name")) or "Portfolio",
        assets=assets,
        benchmark=benchmark,
        start_date=start_date,
        end_date=end_date,
        monte_carlo=monte_carlo,
    )
