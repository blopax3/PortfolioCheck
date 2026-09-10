from __future__ import annotations

import base64
import html
import os
import tempfile
from datetime import datetime
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


def _report_header(config, assets: list[dict[str, str]], returns) -> str:
    benchmark = next((asset for asset in assets if asset.get("weight") == "benchmark"), None)
    benchmark_name = benchmark["name"] if benchmark else "Sin benchmark"
    asset_count = sum(asset.get("weight") != "benchmark" for asset in assets)

    return f"""
    <header class="pc-report-header">
      <p class="pc-brand">PortfolioCheck</p>
      <h1>Informe de rentabilidad y riesgo</h1>
      <p class="pc-report-intro">Resumen histórico de la cartera, riesgo y escenarios probabilísticos.</p>
      <dl class="pc-report-meta">
        <div><dt>Periodo</dt><dd>{returns.index[0]:%d/%m/%Y} — {returns.index[-1]:%d/%m/%Y}</dd></div>
        <div><dt>Benchmark</dt><dd>{_escape(benchmark_name)}</dd></div>
        <div><dt>Moneda</dt><dd>{_escape(config.currency)}</dd></div>
        <div><dt>Composición</dt><dd>{asset_count} activo{'s' if asset_count != 1 else ''}</dd></div>
        <div><dt>Sesiones/año</dt><dd>252</dd></div>
        <div><dt>Tipo sin riesgo</dt><dd>0,00 %</dd></div>
      </dl>
    </header>
    """


def _report_footer() -> str:
    generated = datetime.now().astimezone().strftime("%d/%m/%Y")
    return f"""
    <footer class="pc-report-footer">
      <p>Resultados históricos; no constituyen asesoramiento financiero.</p>
      <p>Generado el {generated} con <a href="https://quantstats.io">QuantStats</a> v. {_escape(qs.__version__)}.</p>
    </footer>
    """


def _insert_section(html: str, header: str, section: str, footer: str) -> str:
    styles = """
    <style>
      body {
        background: #eef3f8;
        color: #243b53;
      }
      .container > h1,
      .container > h4 { display: none; }
      .pc-report-header {
        box-sizing: border-box;
        margin: 0 auto 28px;
        padding: 32px;
        border-radius: 14px;
        background: linear-gradient(135deg, #073b66, #0b67a3);
        box-shadow: 0 12px 30px rgba(7, 59, 102, .18);
        color: white;
      }
      .pc-brand {
        margin: 0 0 8px;
        color: #9ed8ff;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .pc-report-header h1 { margin: 0; font-size: 30px; font-weight: 700; }
      .pc-report-intro { margin: 8px 0 24px; color: #d9efff; font-size: 14px; }
      .pc-report-meta {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin: 0;
      }
      .pc-report-meta div {
        min-width: 0;
        padding: 11px 12px;
        border: 1px solid rgba(255,255,255,.2);
        border-radius: 7px;
        background: rgba(255,255,255,.08);
      }
      .pc-report-meta dt { color: #9ed8ff; font-size: 10px; text-transform: uppercase; }
      .pc-report-meta dd { overflow-wrap: anywhere; margin: 3px 0 0; font-weight: 700; }
      .montecarlo {
        box-sizing: border-box;
        margin: 28px auto 36px;
        width: 960px;
        max-width: 960px;
        padding: 24px 28px;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        background: #f8fbff;
        box-shadow: 0 8px 24px rgba(36, 59, 83, .08);
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
        box-shadow: 0 8px 24px rgba(36, 59, 83, .08);
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
      .pc-report-footer {
        clear: both;
        max-width: 960px;
        margin: 36px auto 0;
        padding: 20px 0;
        border-top: 1px solid #bcccdc;
        color: #627d98;
        font-size: 11px;
      }
      .pc-report-footer p { margin: 3px 0; }
      .pc-report-footer a { color: #0b67a3; }
      svg, img { max-width: 100%; }
      @media (max-width: 720px) {
        body { margin: 12px; }
        .pc-report-header { padding: 24px 20px; }
        .pc-report-meta { grid-template-columns: repeat(2, 1fr); }
        .portfolio-input, .montecarlo { width: 100%; padding: 20px; }
        .pc-table { display: block; overflow-x: auto; }
        .mc-grid { grid-template-columns: 1fr; }
      }
      @media print {
        body { background: white; }
        .pc-report-header, .portfolio-input, .montecarlo { box-shadow: none; }
      }
    </style>
    """
    html = html.replace("</head>", f"{styles}</head>", 1)
    position = html.find("<hr>")
    if position == -1:
        body_position = html.find("<body>")
        position = body_position + len("<body>") if body_position != -1 else 0
        html = html[:position] + header + section + html[position:]
    else:
        html = html[:position] + header + "<hr>" + section + html[position + len("<hr>") :]
    return html.replace("</body>", f"{footer}</body>", 1)


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
    header = _report_header(config, assets, returns)
    initial_section = _portfolio_section(config, assets)
    monte_carlo_section = _monte_carlo_section(returns, config.monte_carlo, monte_carlo_summary, chart)
    html = _insert_section(
        html,
        header,
        initial_section + monte_carlo_section,
        _report_footer(),
    )

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
