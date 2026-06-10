"""Financial Modeling Prep (FMP) stable API — Starter plan ~$22/mo fits <$30 budget."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# New accounts (2025+) use /stable/ — legacy /api/v3/ returns 403 for new keys.
FMP_BASE = "https://financialmodelingprep.com/stable"
# Free FMP tier: limit max 5. Starter+ allows 20+. Set FMP_STATEMENT_LIMIT or HISTORY_YEARS.
DEFAULT_LIMIT = int(os.environ.get("FMP_STATEMENT_LIMIT", os.environ.get("HISTORY_YEARS", "20")))


class FMPError(RuntimeError):
    pass


def get_api_key() -> str:
    key = os.environ.get("FMP_API_KEY", "").strip()
    if not key:
        raise FMPError(
            "FMP_API_KEY not set. Put your key in backend/.env (see .env.example). "
            "Free key: https://site.financialmodelingprep.com/register"
        )
    return key


def _get(endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
    params = dict(params or {})
    params["apikey"] = get_api_key()
    url = f"{FMP_BASE}/{endpoint.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=45)
    if resp.status_code != 200:
        raise FMPError(f"FMP HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if isinstance(data, dict) and data.get("Error Message"):
        raise FMPError(str(data["Error Message"]))
    return data


def _symbol_params(symbol: str, **extra: Any) -> dict[str, Any]:
    return {"symbol": symbol.upper(), **extra}


def fetch_profile(symbol: str) -> dict[str, Any]:
    rows = _get("profile", params=_symbol_params(symbol))
    if not rows:
        raise FMPError(f"No profile for {symbol}")
    return rows[0]


def fetch_income(symbol: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    return _get(
        "income-statement",
        params=_symbol_params(symbol, period="annual", limit=limit),
    )


def fetch_balance(symbol: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    return _get(
        "balance-sheet-statement",
        params=_symbol_params(symbol, period="annual", limit=limit),
    )


def fetch_cashflow(symbol: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    return _get(
        "cash-flow-statement",
        params=_symbol_params(symbol, period="annual", limit=limit),
    )


def fetch_key_metrics(symbol: str, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    return _get(
        "key-metrics",
        params=_symbol_params(symbol, period="annual", limit=limit),
    )


def fetch_quote(symbol: str) -> dict[str, Any]:
    rows = _get("quote", params=_symbol_params(symbol))
    if not rows:
        raise FMPError(f"No quote for {symbol}")
    return rows[0]


def fetch_bundle(symbol: str) -> dict[str, Any]:
    """All statements needed for 1 DATA homologation."""
    return {
        "profile": fetch_profile(symbol),
        "income": fetch_income(symbol),
        "balance": fetch_balance(symbol),
        "cashflow": fetch_cashflow(symbol),
        "key_metrics": fetch_key_metrics(symbol),
        "quote": fetch_quote(symbol),
    }
