"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { parsePortfolioFile, PortfolioFile } from "./portfolio-file";

type Asset = {
  id: string;
  symbol: string;
  weight: string;
};

type ApiAsset = {
  name: string;
  symbol: string;
  source: string;
  weight: string;
};

type AnalysisResult = {
  html: string;
  summary: {
    startDate: string;
    endDate: string;
    sessions: number;
    monteCarlo: Record<string, number>;
  };
  assets: ApiAsset[];
  warnings: string[];
};

type SavedPortfolio = {
  id: string;
  name: string;
  assets: Omit<Asset, "id">[];
  benchmarkSymbol: string;
  startDate: string;
  endDate: string;
  currency: "EUR";
  createdAt: string;
  updatedAt: string;
};

const STORAGE_KEY = "portfoliocheck.savedPortfolios.v1";

const initialAssets: Asset[] = [
  { id: "1", symbol: "", weight: "" }
];

function parseWeight(value: string) {
  const normalized = Number(value.replace(",", "."));
  return Number.isFinite(normalized) ? normalized : 0;
}

function percent(value: number) {
  return new Intl.NumberFormat("es-ES", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
}

function makeId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeSavedPortfolio(value: unknown): SavedPortfolio | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as Partial<SavedPortfolio>;
  const name = typeof candidate.name === "string" ? candidate.name.trim() : "";
  const assets = Array.isArray(candidate.assets)
    ? candidate.assets
        .map((asset) => {
          if (!asset || typeof asset !== "object") {
            return null;
          }

          const item = asset as Partial<Omit<Asset, "id">>;
          const symbol = typeof item.symbol === "string" ? item.symbol.trim() : "";
          if (!symbol) {
            return null;
          }

          return {
            symbol,
            weight: typeof item.weight === "string" ? item.weight.trim() : String(item.weight ?? "0")
          };
        })
        .filter((asset): asset is Omit<Asset, "id"> => Boolean(asset))
    : [];

  if (!name || !assets.length) {
    return null;
  }

  return {
    id: typeof candidate.id === "string" ? candidate.id : makeId(),
    name,
    assets,
    benchmarkSymbol: typeof candidate.benchmarkSymbol === "string" ? candidate.benchmarkSymbol.trim() : "",
    startDate: typeof candidate.startDate === "string" ? candidate.startDate : "2015-01-01",
    endDate: typeof candidate.endDate === "string" ? candidate.endDate : "",
    currency: "EUR",
    createdAt: typeof candidate.createdAt === "string" ? candidate.createdAt : new Date().toISOString(),
    updatedAt: typeof candidate.updatedAt === "string" ? candidate.updatedAt : new Date().toISOString()
  };
}

export default function Home() {
  const [assets, setAssets] = useState<Asset[]>(initialAssets);
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([]);
  const [portfolioName, setPortfolioName] = useState("");
  const [portfolioNotice, setPortfolioNotice] = useState("");
  const [portfolioNoticeError, setPortfolioNoticeError] = useState(false);
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("");
  const [benchmarkSymbol, setBenchmarkSymbol] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const totalWeight = useMemo(
    () => assets.reduce((sum, asset) => sum + parseWeight(asset.weight), 0),
    [assets]
  );
  const isWeightValid = Math.abs(totalWeight - 100) < 0.01;

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;

      setSavedPortfolios(
        parsed
          .map(normalizeSavedPortfolio)
          .filter((portfolio): portfolio is SavedPortfolio => Boolean(portfolio))
      );
    } catch {
      setSavedPortfolios([]);
    }
  }, []);

  function persistPortfolios(next: SavedPortfolio[]) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setSavedPortfolios(next);
      return true;
    } catch {
      setPortfolioNotice("No se pudo guardar en este navegador.");
      setPortfolioNoticeError(true);
      return false;
    }
  }

  function updateAsset(id: string, field: keyof Asset, value: string) {
    setAssets((current) =>
      current.map((asset) => (asset.id === id ? { ...asset, [field]: value } : asset))
    );
  }

  function addAsset() {
    setAssets((current) => [
      ...current,
      { id: makeId(), symbol: "", weight: "0" }
    ]);
  }

  function removeAsset(id: string) {
    setAssets((current) => current.filter((asset) => asset.id !== id));
  }

  function savePortfolio() {
    const cleanAssets = assets
      .map((asset) => ({
        symbol: asset.symbol.trim(),
        weight: asset.weight.trim() || "0"
      }))
      .filter((asset) => asset.symbol);

    if (!cleanAssets.length) {
      setPortfolioNotice("Introduce al menos un ISIN o ticker antes de guardar.");
      setPortfolioNoticeError(true);
      return;
    }

    const cleanName = portfolioName.trim() || `Portfolio ${new Date().toLocaleDateString("es-ES")}`;
    const now = new Date().toISOString();
    const existingIndex = savedPortfolios.findIndex(
      (portfolio) => portfolio.name.toLowerCase() === cleanName.toLowerCase()
    );
    const next = [...savedPortfolios];
    const record: SavedPortfolio = {
      id: existingIndex >= 0 ? next[existingIndex].id : makeId(),
      name: cleanName,
      assets: cleanAssets,
      benchmarkSymbol: benchmarkSymbol.trim(),
      startDate,
      endDate,
      currency: "EUR",
      createdAt: existingIndex >= 0 ? next[existingIndex].createdAt : now,
      updatedAt: now
    };

    if (existingIndex >= 0) {
      next[existingIndex] = record;
    } else {
      next.unshift(record);
    }

    if (persistPortfolios(next)) {
      setPortfolioName(cleanName);
      setPortfolioNotice(`Portfolio "${cleanName}" guardado en este navegador.`);
      setPortfolioNoticeError(false);
    }
  }

  function loadPortfolio(portfolio: SavedPortfolio) {
    setAssets(
      portfolio.assets.map((asset) => ({
        ...asset,
        id: makeId()
      }))
    );
    setPortfolioName(portfolio.name);
    setBenchmarkSymbol(portfolio.benchmarkSymbol);
    setStartDate(portfolio.startDate);
    setEndDate(portfolio.endDate);
    setResult(null);
    setError("");
    setPortfolioNotice(`Portfolio "${portfolio.name}" cargado.`);
    setPortfolioNoticeError(false);
  }

  function deletePortfolio(id: string) {
    const selected = savedPortfolios.find((portfolio) => portfolio.id === id);
    if (persistPortfolios(savedPortfolios.filter((portfolio) => portfolio.id !== id))) {
      setPortfolioNotice(selected ? `Portfolio "${selected.name}" eliminado.` : "");
      setPortfolioNoticeError(false);
    }
  }

  function downloadFile(contents: string, type: string, filename: string) {
    const url = URL.createObjectURL(new Blob([contents], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function downloadPortfolio() {
    const candidate: PortfolioFile = {
      version: 1,
      name: portfolioName.trim() || `Portfolio ${new Date().toLocaleDateString("es-ES")}`,
      assets: assets.map((asset) => ({
        symbol: asset.symbol.trim(),
        weight: Number(asset.weight.replace(",", "."))
      })),
      benchmark: benchmarkSymbol.trim() ? { symbol: benchmarkSymbol.trim() } : null,
      period: { startDate, endDate: endDate || null },
      currency: "EUR"
    };

    try {
      const portfolio = parsePortfolioFile(JSON.stringify(candidate));
      const filename = `${portfolio.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "portfolio"}.json`;
      downloadFile(JSON.stringify(portfolio, null, 2), "application/json;charset=utf-8", filename);
      setPortfolioName(portfolio.name);
      setPortfolioNotice(`Cartera "${portfolio.name}" descargada.`);
      setPortfolioNoticeError(false);
    } catch (fileError) {
      setPortfolioNotice(fileError instanceof Error ? fileError.message : "No se pudo descargar la cartera.");
      setPortfolioNoticeError(true);
    }
  }

  async function importPortfolio(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;

    try {
      if (file.size > 1_000_000) throw new Error("El archivo JSON no puede superar 1 MB.");
      const portfolio = parsePortfolioFile(await file.text());
      setAssets(portfolio.assets.map((asset) => ({
        id: makeId(),
        symbol: asset.symbol,
        weight: String(asset.weight)
      })));
      setPortfolioName(portfolio.name);
      setBenchmarkSymbol(portfolio.benchmark?.symbol || "");
      setStartDate(portfolio.period.startDate);
      setEndDate(portfolio.period.endDate || "");
      setResult(null);
      setError("");
      setPortfolioNotice(`Cartera "${portfolio.name}" cargada desde JSON.`);
      setPortfolioNoticeError(false);
    } catch (fileError) {
      setPortfolioNotice(fileError instanceof Error ? fileError.message : "No se pudo cargar el archivo.");
      setPortfolioNoticeError(true);
    } finally {
      input.value = "";
    }
  }

  function downloadReport() {
    if (!result) return;
    downloadFile(result.html, "text/html;charset=utf-8", "portfoliocheck-report.html");
  }

  function openReport(html: string) {
    if (reportUrl) {
      URL.revokeObjectURL(reportUrl);
    }

    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    setReportUrl(url);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);

    if (!isWeightValid) {
      setError(`Los pesos deben sumar 100%. Ahora suman ${totalWeight.toFixed(2)}%.`);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assets: assets.map((asset) => ({
            symbol: asset.symbol,
            weight: parseWeight(asset.weight) / 100
          })),
          benchmark: benchmarkSymbol.trim()
            ? {
                symbol: benchmarkSymbol.trim()
              }
            : null,
          startDate,
          endDate: endDate || null,
          currency: "EUR"
        })
      });
      const responseText = await response.text();
      const contentType = response.headers.get("content-type") || "";
      let payload: Partial<AnalysisResult> & { error?: string } = {};

      if (contentType.includes("application/json")) {
        payload = JSON.parse(responseText);
      } else {
        const preview = responseText.replace(/\s+/g, " ").slice(0, 180);
        throw new Error(
          `/api/analyze no devolvio JSON. Arranca el proyecto con "npm run dev" para usar la API Python local, no con "npm run dev:next". Respuesta: ${preview}`
        );
      }

      if (!response.ok) {
        throw new Error(payload.error || "No se pudo generar el informe.");
      }
      const analysisResult = payload as AnalysisResult;
      setResult(analysisResult);
      openReport(analysisResult.html);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="workspace">
      <section className="workspace__masthead">
        <header className="workspace__header">
          <h1>PortfolioCheck</h1>
          <p className="workspace__subtitle">
            Analisis de portfolios con Morningstar, Yahoo Finance y QuantStats.
          </p>
        </header>

        <dl className="workspace__summary" aria-label="Resumen del portfolio">
          <div className="workspace__summary-item">
            <dt>Activos</dt>
            <dd>{assets.length}</dd>
          </div>
          <div className="workspace__summary-item">
            <dt>Peso total</dt>
            <dd>{totalWeight.toFixed(2)}%</dd>
          </div>
          <div className="workspace__summary-item">
            <dt>Guardados</dt>
            <dd>{savedPortfolios.length}</dd>
          </div>
        </dl>
      </section>

      <form className="workspace__content" onSubmit={submit}>
        <aside className="control-rail">
          <section className="panel-section portfolio-controls" aria-label="Portfolios guardados">
            <div className="panel-section__header panel-section__header--compact">
              <div className="portfolio-controls__header">
                <strong>Portfolios guardados</strong>
                {savedPortfolios.length ? <span>{savedPortfolios.length} en este navegador</span> : null}
              </div>
              <p>Guarda la composicion actual para reutilizar fondos, ISIN o ticker y pesos mas adelante.</p>
            </div>

            <div className="portfolio-controls__bar">
              <div className="portfolio-inline-group">
                <input
                  className="portfolio-controls__name"
                  value={portfolioName}
                  onChange={(event) => setPortfolioName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      savePortfolio();
                    }
                  }}
                  placeholder="Nombre para guardar"
                />
                <button type="button" className="btn btn--secondary" onClick={savePortfolio}>
                  Guardar
                </button>
              </div>
            </div>

            <div className="portfolio-file-actions" aria-label="Importar o exportar cartera">
              <label className="btn btn--secondary file-button">
                Cargar JSON
                <input type="file" accept=".json,application/json" onChange={importPortfolio} />
              </label>
              <button type="button" className="btn btn--secondary" onClick={downloadPortfolio}>
                Descargar cartera
              </button>
            </div>

            <div className="portfolio-list" data-empty={savedPortfolios.length ? "false" : "true"}>
              {savedPortfolios.length ? (
                savedPortfolios.map((portfolio) => (
                  <div key={portfolio.id} className="portfolio-item">
                    <button
                      type="button"
                      className="portfolio-item__meta"
                      onClick={() => loadPortfolio(portfolio)}
                      title="Cargar portfolio"
                    >
                      <span className="portfolio-item__name">{portfolio.name}</span>
                      <span className="portfolio-item__count">{portfolio.assets.length} activos</span>
                    </button>
                    <button
                      type="button"
                      className="portfolio-item__delete"
                      onClick={() => deletePortfolio(portfolio.id)}
                      title="Eliminar portfolio"
                      aria-label={`Eliminar portfolio ${portfolio.name}`}
                    >
                      x
                    </button>
                  </div>
                ))
              ) : (
                <p className="portfolio-list__empty">Aun no hay portfolios guardados.</p>
              )}
            </div>

            {portfolioNotice && (
              <p className={`inline-notice${portfolioNoticeError ? " inline-notice--error" : ""}`} role="status">
                {portfolioNotice}
              </p>
            )}
          </section>

          <section className="panel-section">
            <div className="panel-section__header">
              <h2>Periodo</h2>
              <p>Define el rango historico que se usara para generar el informe.</p>
            </div>
            <div className="fields">
              <label>
                Fecha inicial
                <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </label>
              <label>
                Fecha final
                <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              </label>
            </div>
          </section>

          <section className="panel-section">
            <div className="panel-section__header">
              <h2>Benchmark</h2>
              <p>Comparador opcional para el informe. Se usara si introduces un ISIN o ticker.</p>
            </div>
            <div className="fields">
              <label>
                ISIN o ticker Yahoo
                <input
                  value={benchmarkSymbol}
                  onChange={(event) => setBenchmarkSymbol(event.target.value)}
                />
              </label>
            </div>
          </section>
        </aside>

        <section className="analysis-column">
          <section className="panel-section">
            <div className="panel-title">
              <div className="panel-section__header panel-section__header--compact">
                <h2>Portfolio</h2>
                <p>Los pesos pueden escribirse como porcentaje. Deben sumar 100%.</p>
              </div>
              <div className={isWeightValid ? "weight ok" : "weight error"}>
                {totalWeight.toFixed(2)}%
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ISIN o ticker Yahoo</th>
                    <th>Peso %</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {assets.map((asset) => (
                    <tr key={asset.id}>
                      <td>
                        <input
                          className="symbol"
                          value={asset.symbol}
                          onChange={(event) => updateAsset(asset.id, "symbol", event.target.value)}
                          placeholder="ES0112611001 o SGLD.MI"
                        />
                      </td>
                      <td>
                        <input
                          className="number"
                          value={asset.weight}
                          onChange={(event) => updateAsset(asset.id, "weight", event.target.value)}
                          inputMode="decimal"
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => removeAsset(asset.id)}
                          title="Eliminar activo"
                          aria-label={`Eliminar ${asset.symbol || "activo"}`}
                        >
                          x
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel-footer">
              <button type="button" className="btn btn--secondary" onClick={addAsset}>
                Anadir activo
              </button>
            </div>
          </section>

          {error && <div className="message error-message">{error}</div>}

          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={loading || !isWeightValid}>
              {loading ? "Generando informe..." : "Generar informe"}
            </button>
            <button type="button" className="btn btn--secondary" disabled={!result} onClick={downloadReport}>
              Descargar HTML
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              disabled={!result || !reportUrl}
              onClick={() => reportUrl && window.open(reportUrl, "_blank", "noopener,noreferrer")}
            >
              Abrir informe
            </button>
          </div>
        </section>
      </form>

      {result && (
        <section className="results analysis-column">
          <div className="summary-bar">
            <div>
              <span>Periodo</span>
              <strong>
                {result.summary.startDate} - {result.summary.endDate}
              </strong>
            </div>
            <div>
              <span>Sesiones</span>
              <strong>{result.summary.sessions}</strong>
            </div>
            <div>
              <span>Monte Carlo mediana</span>
              <strong>{percent(result.summary.monteCarlo.p50)}</strong>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="message warning-message">
              {result.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}

          <div className="source-list">
            {result.assets.map((asset) => (
              <span key={`${asset.name}-${asset.weight}`}>
                {asset.name}: {asset.source}
              </span>
            ))}
          </div>

          <div className="message report-message">
            El informe se ha abierto en una nueva pestana. Si el navegador lo ha bloqueado, usa el boton Abrir informe.
          </div>
        </section>
      )}
    </main>
  );
}
