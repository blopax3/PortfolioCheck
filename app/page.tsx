"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

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
    createdAt: typeof candidate.createdAt === "string" ? candidate.createdAt : new Date().toISOString(),
    updatedAt: typeof candidate.updatedAt === "string" ? candidate.updatedAt : new Date().toISOString()
  };
}

export default function Home() {
  const [assets, setAssets] = useState<Asset[]>(initialAssets);
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([]);
  const [portfolioName, setPortfolioName] = useState("");
  const [portfolioNotice, setPortfolioNotice] = useState("");
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
    setSavedPortfolios(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      setPortfolioNotice("No se pudo guardar en este navegador.");
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
      createdAt: existingIndex >= 0 ? next[existingIndex].createdAt : now,
      updatedAt: now
    };

    if (existingIndex >= 0) {
      next[existingIndex] = record;
    } else {
      next.unshift(record);
    }

    persistPortfolios(next);
    setPortfolioName(cleanName);
    setPortfolioNotice(`Portfolio "${cleanName}" guardado en este navegador.`);
  }

  function loadPortfolio(portfolio: SavedPortfolio) {
    setAssets(
      portfolio.assets.map((asset) => ({
        ...asset,
        id: makeId()
      }))
    );
    setPortfolioName(portfolio.name);
    setResult(null);
    setError("");
    setPortfolioNotice(`Portfolio "${portfolio.name}" cargado.`);
  }

  function deletePortfolio(id: string) {
    const selected = savedPortfolios.find((portfolio) => portfolio.id === id);
    persistPortfolios(savedPortfolios.filter((portfolio) => portfolio.id !== id));
    setPortfolioNotice(selected ? `Portfolio "${selected.name}" eliminado.` : "");
  }

  function downloadReport() {
    if (!result) return;
    const blob = new Blob([result.html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "portfoliocheck-report.html";
    link.click();
    URL.revokeObjectURL(url);
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

            {portfolioNotice && <p className="inline-notice">{portfolioNotice}</p>}
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
