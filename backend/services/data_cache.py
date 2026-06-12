"""Resolve cached 1 DATA JSON files (production: serve cache before live APIs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.sp500_priority import (
    company_name,
    format_mcap_billions,
    priority_billions,
    sort_tickers_for_display,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATALOG_PATH = DATA_DIR / "ticker_catalog.json"
MANIFEST_PATH = DATA_DIR / "sp500_manifest.json"

_CATALOG_MEM: dict[str, Any] | None = None


def list_cached_tickers() -> list[str]:
    tickers: set[str] = set()
    for path in DATA_DIR.glob("*_1data.json"):
        name = path.stem
        base = name.replace("_edgar_1data", "").replace("_fmp_1data", "").replace("_1data", "")
        if base:
            tickers.add(base.upper())
    return sorted(tickers)


def _glob_ready_tickers() -> list[str]:
    tickers: set[str] = set()
    for path in DATA_DIR.glob("*_1data.json"):
        base = path.stem.replace("_edgar_1data", "").replace("_fmp_1data", "").replace("_1data", "")
        if base:
            tickers.add(base.upper())
    return sort_tickers_for_display(list(tickers), top_n=20)


def build_ticker_catalog_payload() -> dict[str, Any]:
    """Build ordered ready list + browse catalog (lightweight profile reads only)."""
    tickers = list_cached_tickers()
    ordered = sort_tickers_for_display(tickers, top_n=20)
    catalog: list[dict[str, str | float | None]] = []
    for sym in ordered:
        cap_b = priority_billions(sym)
        catalog.append(
            {
                "ticker": sym,
                "company": company_name(sym),
                "market_cap_b": cap_b,
                "market_cap_label": format_mcap_billions(cap_b),
            }
        )
    return {
        "ready": ordered,
        "catalog": catalog,
        "count": len(ordered),
        "sort": "top_20_market_cap_then_alpha",
    }


def rebuild_ticker_catalog() -> dict[str, Any]:
    """Regenerate ticker_catalog.json after cache builds."""
    global _CATALOG_MEM
    payload = build_ticker_catalog_payload()
    CATALOG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _CATALOG_MEM = payload
    return payload


def _catalog_from_manifest() -> dict[str, Any] | None:
    """Fast catalog from sp500_manifest.json (single file read at startup)."""
    if not MANIFEST_PATH.is_file():
        return None
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cached_rows = data.get("cached")
    if not isinstance(cached_rows, list) or not cached_rows:
        return None

    ranked = sorted(
        cached_rows,
        key=lambda row: (-float(row.get("priority_mcap_b") or 0), str(row.get("ticker") or "")),
    )
    top = ranked[:20]
    top_set = {str(row["ticker"]) for row in top}
    rest = sorted(
        [row for row in ranked if str(row.get("ticker")) not in top_set],
        key=lambda row: str(row.get("ticker") or ""),
    )
    ordered_rows = top + rest

    catalog: list[dict[str, str | float | None]] = []
    ready: list[str] = []
    for row in ordered_rows:
        sym = str(row.get("ticker") or "").upper()
        if not sym:
            continue
        cap_raw = row.get("priority_mcap_b")
        cap_b = float(cap_raw) if cap_raw is not None else None
        ready.append(sym)
        catalog.append(
            {
                "ticker": sym,
                "company": str(row.get("name") or sym),
                "market_cap_b": cap_b,
                "market_cap_label": format_mcap_billions(cap_b),
            }
        )
    if not ready:
        return None
    return {
        "ready": ready,
        "catalog": catalog,
        "count": len(ready),
        "sort": "top_20_market_cap_then_alpha",
    }


def warm_ticker_catalog() -> dict[str, Any]:
    """Load catalog into memory at startup (single JSON read)."""
    return _load_catalog_mem()


def _load_catalog_mem() -> dict[str, Any]:
    global _CATALOG_MEM
    if _CATALOG_MEM is not None:
        return _CATALOG_MEM
    if CATALOG_PATH.is_file():
        try:
            _CATALOG_MEM = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            if _CATALOG_MEM.get("ready") and _CATALOG_MEM.get("catalog"):
                return _CATALOG_MEM
        except (json.JSONDecodeError, OSError):
            pass
    manifest_payload = _catalog_from_manifest()
    if manifest_payload:
        _CATALOG_MEM = manifest_payload
        return _CATALOG_MEM
    return rebuild_ticker_catalog()


def list_ready_tickers() -> list[str]:
    """Tickers with cached 1 DATA — top 20 by market cap, then A–Z."""
    payload = _load_catalog_mem()
    ready = payload.get("ready")
    if isinstance(ready, list) and ready:
        return [str(sym).upper() for sym in ready]
    return _glob_ready_tickers()


def list_ticker_catalog() -> list[dict[str, str | float | None]]:
    """Ticker + company + market cap for browse UI (top 20 mcap, rest A–Z)."""
    payload = _load_catalog_mem()
    catalog = payload.get("catalog")
    if isinstance(catalog, list) and catalog:
        return catalog
    return build_ticker_catalog_payload()["catalog"]


def is_ticker_ready(symbol: str) -> bool:
    sym = symbol.upper()
    if sym == "MSFT":
        return bool(load_cached("MSFT", "preload") or load_cached("MSFT", "edgar"))
    return bool(load_cached(sym, "edgar") or load_cached(sym, "preload") or load_cached(sym, "fmp"))


def cache_path(symbol: str, source: str) -> Path | None:
    sym = symbol.lower()
    src = source.lower()
    if src == "edgar":
        candidates = [DATA_DIR / f"{sym}_edgar_1data.json"]
    elif src == "fmp":
        candidates = [DATA_DIR / f"{sym}_fmp_1data.json"]
    elif src == "preload":
        candidates = [DATA_DIR / f"{sym}_1data.json"]
    else:
        candidates = [
            DATA_DIR / f"{sym}_1data.json",
            DATA_DIR / f"{sym}_edgar_1data.json",
            DATA_DIR / f"{sym}_fmp_1data.json",
        ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_cached(symbol: str, source: str = "auto") -> dict | None:
    path = cache_path(symbol, source)
    if not path:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_cached(symbol: str, source: str, payload: dict[str, Any]) -> Path:
    sym = symbol.lower()
    if source == "edgar":
        path = DATA_DIR / f"{sym}_edgar_1data.json"
    elif source == "fmp":
        path = DATA_DIR / f"{sym}_fmp_1data.json"
    else:
        path = DATA_DIR / f"{sym}_1data.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
