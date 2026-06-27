from __future__ import annotations

import base64
import html
import os
import tempfile
from io import BytesIO
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import quantstats as qs

from .models import parse_payload
from .portfolio import build_portfolio


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _portfolio_section(config, assets: list[dict[str, str]]) -> str:
    asset_rows = [asset for asset in assets if asset.get("weight") != "benchmark"]
    benchmark_rows = [asset for asset in assets if asset.get("weight") == "benchmark"]

    rows = "\n".join(
        f"""
        <tr>
          <td>{_escape(asset["name"])}</td>
          <td>{_escape(asset["symbol"])}</td>
          <td>{float(asset["weight"]):.2%}</td>
          <td>{_escape(asset["source"])}</td>
        </tr>
        """
        for asset in asset_rows
    )

    if benchmark_rows:
        benchmark = benchmark_rows[0]
        benchmark_html = f"""
        <div class="pc-benchmark">
          <h3>Benchmark</h3>
          <p>
            <strong>{_escape(benchmark["name"])}</strong>
            <span>{_escape(benchmark["symbol"])}</span>
            <em>Fuente: {_escape(benchmark["source"])}</em>
          </p>
        </div>
        """
    else:
        benchmark_html = """
        <div class="pc-benchmark">
          <h3>Benchmark</h3>
          <p><em>No se ha incluido benchmark.</em></p>
        </div>
        """

    end_date = config.end_date or "Ultima fecha disponible"
    return f"""
    <section class="portfolio-input">
      <h2>Cartera introducida</h2>
      <p class="pc-period">
        Periodo solicitado: {_escape(config.start_date)} - {_escape(end_date)}.
        Moneda Morningstar: {_escape(config.currency)}.
      </p>
      <table class="pc-table">
        <thead>
          <tr>
            <th>Fondo / activo</th>
            <th>ISIN / ticker introducido</th>
            <th>Peso</th>
            <th>Fuente usada</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {benchmark_html}
    </section>
    """


def _simulate_monte_carlo(returns, config):
    if len(returns) < config.sessions:
        raise ValueError(f"Se necesitan al menos {config.sessions} rendimientos diarios para Monte Carlo.")

    full_result = qs.stats.montecarlo(
        returns,
        sims=config.simulations,
        bust=config.bust,
        goal=config.goal,
        seed=config.seed,
    )
    data = full_result.data.iloc[: config.sessions].copy()
    original = full_result.original.iloc[: config.sessions].copy()
    result = type(full_result)(
        data=data,
        original=original,
        bust_threshold=config.bust,
        goal_threshold=config.goal,
    )

    terminal = result.data.iloc[-1]
    summary = {
        "p5": float(terminal.quantile(0.05)),
        "p25": float(terminal.quantile(0.25)),
        "p50": float(terminal.quantile(0.50)),
        "p75": float(terminal.quantile(0.75)),
        "p95": float(terminal.quantile(0.95)),
        "lossProbability": float((terminal < 0).mean()),
        "goalProbability": float(result.goal_probability),
        "bustProbability": float(result.bust_probability),
    }
    return result, summary


def _monte_carlo_chart(result) -> str:
    fig = qs.plots.montecarlo(
        result,
        title="Monte Carlo QuantStats",
        figsize=(12, 5.8),
        fontname="DejaVu Sans",
        confidence_level=0.90,
        subtitle=True,
        show=False,
    )
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _monte_carlo_section(returns, config, summary, chart: str) -> str:
    start = returns.index[0].strftime("%d/%m/%Y")
    end = returns.index[-1].strftime("%d/%m/%Y")

    def pct(value: float) -> str:
        return f"{value:+.2%}"

    return f"""
    <section class="montecarlo">
      <h2>Prediccion Monte Carlo</h2>
      <p>
        Simulacion de {config.simulations:,} trayectorias durante {config.sessions}
        sesiones bursatiles, calibrada con retornos diarios entre {start} y {end}.
      </p>
      <div class="mc-grid">
        <div><strong>Escenario pesimista (P5)</strong><span>{pct(summary["p5"])}</span></div>
        <div><strong>Percentil 25</strong><span>{pct(summary["p25"])}</span></div>
        <div><strong>Escenario central</strong><span>{pct(summary["p50"])}</span></div>
        <div><strong>Percentil 75</strong><span>{pct(summary["p75"])}</span></div>
        <div><strong>Escenario optimista (P95)</strong><span>{pct(summary["p95"])}</span></div>
        <div><strong>Probabilidad de perdida</strong><span>{summary["lossProbability"]:.2%}</span></div>
        <div><strong>Probabilidad objetivo</strong><span>{summary["goalProbability"]:.2%}</span></div>
        <div><strong>Probabilidad drawdown</strong><span>{summary["bustProbability"]:.2%}</span></div>
      </div>
      <img class="mc-chart" src="data:image/png;base64,{chart}" alt="Simulacion Monte Carlo">
      <p class="mc-note">
        Estimacion estadistica basada en rendimientos historicos; no es una garantia
        ni una recomendacion de inversion. No incluye comisiones ni impuestos.
      </p>
    </section>
    """


def _insert_section(html: str, section: str) -> str:
    styles = """
    <style>
      .montecarlo {
        box-sizing: border-box;
        margin: 28px auto 36px;
        width: 960px;
        max-width: 960px;
        padding: 24px 28px;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        background: #f8fbff;
        page-break-after: always;
      }
      .montecarlo h2 { margin: 0 0 10px; color: #084594; }
      .portfolio-input {
        box-sizing: border-box;
        margin: 28px auto 36px;
        width: 960px;
        max-width: 960px;
        padding: 24px 28px;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        background: #ffffff;
      }
      .portfolio-input h2 { margin: 0 0 10px; color: #084594; }
      .pc-period { margin: 0 0 16px; color: #52606d; }
      .pc-table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0 18px;
      }
      .pc-table th,
      .pc-table td {
        padding: 9px 10px;
        border-bottom: 1px solid #d9e2ec;
        text-align: left;
      }
      .pc-table th {
        background: #f1f6fb;
        color: #334e68;
        font-size: 12px;
        text-transform: uppercase;
      }
      .pc-benchmark {
        padding: 14px 16px;
        border: 1px solid #d9e2ec;
        border-radius: 6px;
        background: #f8fbff;
      }
      .pc-benchmark h3 { margin: 0 0 8px; color: #084594; }
      .pc-benchmark p { margin: 0; }
      .pc-benchmark span,
      .pc-benchmark em { margin-left: 12px; color: #52606d; }
      .mc-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin: 18px 0;
      }
      .mc-grid div {
        padding: 12px;
        border-radius: 5px;
        background: white;
        border: 1px solid #d9e2ec;
      }
      .mc-grid strong, .mc-grid span { display: block; }
      .mc-grid span { margin-top: 6px; font-size: 20px; color: #084594; }
      .mc-chart { display: block; width: 100%; max-width: 1050px; margin: 10px auto; }
      .mc-note { font-size: 11px; color: #52606d; }
      svg, img { max-width: 100%; }
    </style>
    """
    html = html.replace("</head>", f"{styles}</head>", 1)
    position = html.find("<hr>")
    if position == -1:
        body_position = html.find("<body>")
        position = body_position + len("<body>") if body_position != -1 else 0
    return html[:position] + section + html[position:]


def _quantstats_html(returns, benchmark) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "report.html"
        qs.reports.html(
            returns,
            benchmark=benchmark,
            output=str(output),
            title="PortfolioCheck",
        )
        return output.read_text(encoding="utf-8")


def analyze_portfolio(payload: dict) -> dict:
    config = parse_payload(payload)
    returns, benchmark, assets, warnings = build_portfolio(config)
    html = _quantstats_html(returns, benchmark)
    monte_carlo_result, monte_carlo_summary = _simulate_monte_carlo(returns, config.monte_carlo)
    chart = _monte_carlo_chart(monte_carlo_result)
    initial_section = _portfolio_section(config, assets)
    monte_carlo_section = _monte_carlo_section(returns, config.monte_carlo, monte_carlo_summary, chart)
    html = _insert_section(html, initial_section + monte_carlo_section)

    return {
        "html": html,
        "summary": {
            "startDate": str(returns.index[0].date()),
            "endDate": str(returns.index[-1].date()),
            "sessions": int(len(returns)),
            "monteCarlo": monte_carlo_summary,
        },
        "assets": assets,
        "warnings": warnings,
    }
