from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

MORNINGSTAR_ENDPOINT = (
    "https://lt.morningstar.com/api/rest.svc/"
    "timeseries_price/t92wz0sj7c"
)
YAHOO_SEARCH_ENDPOINT = "https://query1.finance.yahoo.com/v1/finance/search"
MORNINGSTAR_ID_SUFFIX = "]2]0]FOEUR$$ALL"

MORNINGSTAR_SYMBOL_MAP = {
    "ES0112611001": "0P00016YQ5.F",
    "ES0146309002": "0P0001DFE8.F",
    "IE00BFZMJT78": "0P0001FAME.F",
    "IE0007471927": "F0GBR04SGO",
    "ES0140794001": "F000016XFK",
    "IE00B79S1F56": "0P0000VHGM.F",
    "DI4C.F": "0P00000B50.F",
}


@dataclass(frozen=True)
class ReturnSeries:
    returns: pd.Series
    source: str
    symbol: str
    name: str
    warning: str | None = None


def _extract_morningstar_name(payload: dict, fallback: str) -> str:
    try:
        security = payload["TimeSeries"]["Security"][0]
    except (KeyError, IndexError, TypeError):
        return fallback

    for key in ("Name", "LegalName", "SecurityName", "SecName"):
        value = security.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _resolve_yahoo_search_name(query: str) -> str | None:
    params = {
        "q": query,
        "quotesCount": 5,
        "newsCount": 0,
    }
    url = f"{YAHOO_SEARCH_ENDPOINT}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except Exception:
        return None

    quotes = payload.get("quotes")
    if not isinstance(quotes, list):
        return None

    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        for key in ("longname", "shortname", "displayName", "symbol"):
            value = quote.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _request_morningstar(
    identifier: str,
    idtype: str,
    start: str,
    end: str | None,
    currency: str,
    fallback_name: str,
) -> tuple[pd.Series, str]:
    params = {
        "currencyId": currency,
        "idtype": idtype,
        "frequency": "daily",
        "outputType": "JSON",
        "startDate": pd.Timestamp(start).strftime("%Y-%m-%d"),
        "id": identifier,
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
        name=identifier,
        dtype=float,
    ).sort_index()
    prices = prices[~prices.index.duplicated(keep="last")].dropna()
    if end is not None:
        prices = prices.loc[: pd.Timestamp(end)]
    if prices.empty:
        raise ValueError("Morningstar devolvio una serie vacia.")
    return prices, _extract_morningstar_name(payload, fallback_name)


def _morningstar_candidates(identifier: str) -> list[tuple[str, str]]:
    clean = identifier.strip().upper()
    candidates: list[tuple[str, str]] = []
    mapped_identifier = MORNINGSTAR_SYMBOL_MAP.get(clean)
    if mapped_identifier:
        candidates.append((f"{mapped_identifier}{MORNINGSTAR_ID_SUFFIX}", "Morningstar"))
    if len(clean) == 12 and clean[:2].isalpha():
        candidates.append((clean, "ISIN"))
    candidates.append((f"{clean}{MORNINGSTAR_ID_SUFFIX}", "Morningstar"))
    candidates.append((clean, "Morningstar"))

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def looks_like_isin(symbol: str) -> bool:
    clean = symbol.strip().upper()
    return len(clean) == 12 and clean[:2].isalpha() and clean[2:].isalnum()


def looks_like_morningstar_id(symbol: str) -> bool:
    clean = symbol.strip().upper()
    return clean.startswith(("0P", "F0", "F000"))


def download_morningstar_returns(identifier: str, start: str, end: str | None, currency: str) -> tuple[pd.Series, str]:
    errors: list[str] = []
    for morningstar_id, idtype in _morningstar_candidates(identifier):
        try:
            prices, name = _request_morningstar(morningstar_id, idtype, start, end, currency, identifier)
            returns = prices.pct_change(fill_method=None).dropna()
            if returns.empty:
                raise ValueError("Serie de retornos vacia.")
            if name == identifier:
                name = _resolve_yahoo_search_name(identifier) or name
            returns.name = name
            return returns, name
        except Exception as error:
            errors.append(f"{idtype}: {error}")
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

    if clean_symbol in MORNINGSTAR_SYMBOL_MAP or looks_like_isin(clean_symbol) or looks_like_morningstar_id(clean_symbol):
        try:
            returns, resolved_name = download_morningstar_returns(clean_symbol, start, end, currency)
            name = resolved_name or clean_label or clean_symbol
            returns.name = name
            return ReturnSeries(returns=returns, source="morningstar", symbol=clean_symbol, name=name)
        except Exception as morningstar_error:
            if looks_like_morningstar_id(clean_symbol):
                raise ValueError(
                    f"No se pudieron descargar datos de {label} desde Morningstar. Introduce un ISIN o ticker Yahoo valido."
                ) from morningstar_error
            warning = f"Morningstar fallo para {label}; se uso Yahoo Finance con {clean_symbol}."
            returns, resolved_name = download_yahoo_returns(clean_symbol, start, end)
            name = resolved_name or clean_label or clean_symbol
            returns = returns.rename(name)
            return ReturnSeries(
                returns=returns,
                source="yahoo",
                symbol=clean_symbol,
                name=name,
                warning=warning,
            )

    returns, resolved_name = download_yahoo_returns(clean_symbol, start, end)
    name = resolved_name or clean_label or clean_symbol
    returns = returns.rename(name)
    return ReturnSeries(returns=returns, source="yahoo", symbol=clean_symbol, name=name)
