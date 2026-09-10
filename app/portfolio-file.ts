export type PortfolioFile = {
  version: 1;
  name: string;
  assets: { symbol: string; weight: number }[];
  benchmark: { symbol: string } | null;
  period: { startDate: string; endDate: string | null };
  currency: "EUR";
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().startsWith(value);
}

export function parsePortfolioFile(text: string): PortfolioFile {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("El archivo no contiene un JSON valido.");
  }

  if (!isRecord(value) || value.version !== 1) {
    throw new Error("El archivo no es una cartera PortfolioCheck version 1.");
  }

  const name = typeof value.name === "string" ? value.name.trim() : "";
  if (!name) throw new Error("La cartera necesita un nombre.");
  if (!Array.isArray(value.assets) || !value.assets.length) {
    throw new Error("La cartera necesita al menos un activo.");
  }

  const assets = value.assets.map((asset, index) => {
    if (!isRecord(asset)) throw new Error(`El activo ${index + 1} no es valido.`);
    const symbol = typeof asset.symbol === "string" ? asset.symbol.trim() : "";
    if (!symbol) throw new Error(`El activo ${index + 1} necesita un ISIN o ticker.`);
    if (typeof asset.weight !== "number" || !Number.isFinite(asset.weight) || asset.weight < 0) {
      throw new Error(`El peso del activo ${index + 1} debe ser un numero no negativo.`);
    }
    return { symbol, weight: asset.weight };
  });

  const totalWeight = assets.reduce((sum, asset) => sum + asset.weight, 0);
  if (Math.abs(totalWeight - 100) >= 0.01) {
    throw new Error(`Los pesos del archivo deben sumar 100%. Suman ${totalWeight.toFixed(2)}%.`);
  }

  let benchmark: PortfolioFile["benchmark"] = null;
  if (value.benchmark !== null) {
    if (!isRecord(value.benchmark) || typeof value.benchmark.symbol !== "string" || !value.benchmark.symbol.trim()) {
      throw new Error("El benchmark debe contener un ISIN o ticker valido.");
    }
    benchmark = { symbol: value.benchmark.symbol.trim() };
  }

  if (!isRecord(value.period)) {
    throw new Error("La fecha inicial del archivo no es valida.");
  }
  const startDate = value.period.startDate;
  if (!isDate(startDate)) throw new Error("La fecha inicial del archivo no es valida.");
  let endDate: string | null = null;
  if (value.period.endDate !== null) {
    if (!isDate(value.period.endDate)) throw new Error("La fecha final del archivo no es valida.");
    endDate = value.period.endDate;
  }
  if (endDate && endDate < startDate) {
    throw new Error("La fecha final no puede ser anterior a la inicial.");
  }
  if (value.currency !== "EUR") {
    throw new Error("PortfolioCheck solo admite carteras en EUR.");
  }

  return {
    version: 1,
    name,
    assets,
    benchmark,
    period: { startDate, endDate },
    currency: "EUR"
  };
}
