"""Resolve cached 1 DATA JSON files (production: serve cache before live APIs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def list_cached_tickers() -> list[str]:
    tickers: set[str] = set()
    for path in DATA_DIR.glob("*_1data.json"):
        name = path.stem  # e.g. msft_1data, aapl_edgar_1data, aapl_fmp_1data
        base = name.replace("_edgar_1data", "").replace("_fmp_1data", "").replace("_1data", "")
        if base:
            tickers.add(base.upper())
    return sorted(tickers)


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
