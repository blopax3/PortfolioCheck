from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

MORNINGSTAR_ENDPOINT = (
    "https://lt.morningstar.com/api/rest.svc/"
    "timeseries_price/t92wz0sj7c"
)
MORNINGSTAR_SEARCH_ENDPOINT = (
    "https://lt.morningstar.com/api/rest.svc/t92wz0sj7c/security/screener"
)
MORNINGSTAR_UNIVERSES = ("FOEUR$$ALL", "FOESP$$ALL", "FOGBR$$ALL")
ISIN_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
YAHOO_SYMBOL_PATTERN = re.compile(r"[A-Z0-9^][A-Z0-9.^=-]{0,31}")


@dataclass(frozen=True)
class ReturnSeries:
    returns: pd.Series
    source: str
    symbol: str
    name: str
    warning: str | None = None


def normalize_isin(value: object) -> str:
    clean = value.strip().upper() if isinstance(value, str) else ""
    if not ISIN_PATTERN.fullmatch(clean):
        return ""
    digits = "".join(str(int(character, 36)) for character in clean)
    total = sum(
        (digit * 2 // 10 + digit * 2 % 10) if index % 2 else digit
        for index, digit in enumerate(map(int, reversed(digits)))
    )
    return clean if total % 10 == 0 else ""


def normalize_yahoo_symbol(value: object) -> str:
    clean = value.strip().upper() if isinstance(value, str) else ""
    return clean if YAHOO_SYMBOL_PATTERN.fullmatch(clean) else ""


def _search_morningstar(isin: str) -> list[tuple[str, str]]:
    params = {
        "page": 1,
        "pageSize": 100,
        "outputType": "json",
        "version": 1,
        "languageId": "es-ES",
        "universeIds": "|".join(MORNINGSTAR_UNIVERSES),
        "securityDataPoints": "SecId,Name,ISIN",
        "filters": f"ISIN:EQ:{isin}",
    }
    request = Request(
        f"{MORNINGSTAR_SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.morningstar.es/"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Respuesta del buscador de Morningstar invalida.")

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or normalize_isin(row.get("ISIN")) != isin:
            continue
        secid = row.get("SecId")
        if isinstance(secid, str) and secid.strip() and secid not in seen:
            seen.add(secid)
            candidates.append((secid.strip(), str(row.get("Name") or isin)))
    if not candidates:
        raise ValueError(f"Morningstar no encontro una coincidencia exacta para {isin}.")
    return candidates


def _request_morningstar(
    secid: str,
    universe: str,
    start: str,
    end: str | None,
    currency: str,
) -> pd.Series:
    params = {
        "currencyId": currency,
        "idtype": "Morningstar",
        "frequency": "daily",
        "outputType": "JSON",
        "startDate": pd.Timestamp(start).strftime("%Y-%m-%d"),
        "id": f"{secid}]2]0]{universe}",
    }
    url = f"{MORNINGSTAR_ENDPOINT}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    try:
        security = payload["TimeSeries"]["Security"][0]
        history = security["HistoryDetail"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Respuesta de Morningstar invalida.") from error

    prices = pd.Series(
        data=[float(record["Value"]) for record in history],
        index=pd.to_datetime([record["EndDate"] for record in history]),
        name=secid,
        dtype=float,
    ).sort_index()
    prices = prices[~prices.index.duplicated(keep="last")].dropna()
    if end is not None:
        prices = prices.loc[: pd.Timestamp(end)]
    if prices.empty:
        raise ValueError("Morningstar devolvio una serie vacia.")
    return prices


def looks_like_isin(symbol: str) -> bool:
    return bool(normalize_isin(symbol))


def download_morningstar_returns(identifier: str, start: str, end: str | None, currency: str) -> tuple[pd.Series, str]:
    errors: list[str] = []
    for secid, name in _search_morningstar(identifier):
        for universe in MORNINGSTAR_UNIVERSES:
            try:
                prices = _request_morningstar(secid, universe, start, end, currency)
                returns = prices.pct_change(fill_method=None).dropna()
                if returns.empty:
                    raise ValueError("Serie de retornos vacia.")
                returns.name = name
                return returns, name
            except Exception as error:
                errors.append(f"{secid} ({universe}): {error}")
    raise ValueError("; ".join(errors))


def _resolve_yahoo_name(ticker: yf.Ticker, symbol: str) -> str:
    try:
        info = ticker.get_info() or {}
    except Exception:
        info = {}

    for key in ("longName", "shortName", "displayName", "symbol"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return symbol


def download_yahoo_returns(symbol: str, start: str, end: str | None) -> tuple[pd.Series, str]:
    yf_end = None
    if end is not None:
        yf_end = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    ticker = yf.Ticker(symbol)
    history = ticker.history(
        start=pd.Timestamp(start).strftime("%Y-%m-%d"),
        end=yf_end,
        auto_adjust=True,
        actions=False,
    )
    if history.empty:
        raise ValueError(f"Yahoo Finance no devolvio datos para {symbol}.")

    price_column = "Close" if "Close" in history.columns else "Adj Close"
    prices = history[price_column].dropna().sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    returns = prices.pct_change(fill_method=None).dropna()
    if end is not None:
        returns = returns.loc[: pd.Timestamp(end)]
    name = _resolve_yahoo_name(ticker, symbol)
    returns.name = name
    if returns.empty:
        raise ValueError(f"Yahoo Finance no devolvio datos para {symbol}.")
    return returns, name


def download_returns(
    symbol: str,
    start: str,
    end: str | None,
    currency: str,
    label: str,
) -> ReturnSeries:
    clean_symbol = symbol.strip().upper()
    clean_label = label.strip()
    if not clean_symbol:
        raise ValueError(f"{label} necesita ISIN o ticker Yahoo.")

    if ISIN_PATTERN.fullmatch(clean_symbol) and not looks_like_isin(clean_symbol):
        raise ValueError(f"El ISIN de {label} no es valido.")

    if looks_like_isin(clean_symbol):
        try:
            returns, resolved_name = download_morningstar_returns(clean_symbol, start, end, currency)
            name = resolved_name or clean_label or clean_symbol
            returns.name = name
            return ReturnSeries(returns=returns, source="morningstar", symbol=clean_symbol, name=name)
        except Exception as morningstar_error:
            raise ValueError(
                f"No se pudieron descargar datos de {label} desde Morningstar."
            ) from morningstar_error

    yahoo_symbol = normalize_yahoo_symbol(clean_symbol)
    if not yahoo_symbol:
        raise ValueError(f"{label} necesita un ISIN o ticker Yahoo valido.")
    returns, resolved_name = download_yahoo_returns(yahoo_symbol, start, end)
    name = resolved_name or clean_label or clean_symbol
    returns = returns.rename(name)
    return ReturnSeries(returns=returns, source="yahoo", symbol=yahoo_symbol, name=name)
