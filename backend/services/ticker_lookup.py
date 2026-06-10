"""Ticker validation (SEC) and live fetch with cache persistence."""

from __future__ import annotations

import json
import re
import threading
from typing import Any

from services.data_cache import cache_path, load_cached, save_cached
from services.edgar_provider import EdgarError, fetch_company_facts, resolve_cik
from services.normalize_edgar import normalize_edgar_facts

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")


def normalize_symbol(raw: str) -> str:
    """BRK.B → BRK-B for SEC; strip whitespace."""
    s = raw.strip().upper()
    return s.replace(".", "-")


def validate_symbol(raw: str) -> dict[str, Any]:
    """Fast check: format + SEC CIK registry (no companyfacts download)."""
    sym = normalize_symbol(raw)
    if not sym or not _SYMBOL_RE.match(sym):
        return {
            "symbol": sym or raw.strip().upper(),
            "exists": False,
            "cached": False,
            "reason": "invalid_format",
            "message": "Invalid ticker format.",
        }

    cached = load_cached(sym, "edgar") is not None or cache_path(sym, "preload") is not None
    try:
        cik = resolve_cik(sym)
    except EdgarError:
        return {
            "symbol": sym,
            "exists": False,
            "cached": cached,
            "reason": "not_in_sec",
            "message": f"{sym} is not a US SEC filer (not found in EDGAR).",
        }

    return {
        "symbol": sym,
        "exists": True,
        "cached": cached,
        "cik": cik,
        "reason": "ok",
        "message": "Cached — loads instantly." if cached else "Valid ticker — live fetch from SEC EDGAR (~1–2 min).",
    }


def fetch_edgar_and_cache(symbol: str) -> dict[str, Any]:
    """Best-effort live path: EDGAR companyfacts → 1 DATA JSON → disk cache."""
    sym = normalize_symbol(symbol)
    validation = validate_symbol(sym)
    if not validation["exists"]:
        raise ValueError(validation["message"])

    facts = fetch_company_facts(sym)
    payload = normalize_edgar_facts(sym, facts)
    save_cached(sym, "edgar", payload)
    return payload


def _fetch_fmp_fallback(symbol: str) -> dict[str, Any]:
    from services.fmp_provider import FMPError, fetch_bundle
    from services.normalize_fmp import normalize_fmp_bundle

    sym = normalize_symbol(symbol)
    bundle = fetch_bundle(sym)
    payload = normalize_fmp_bundle(sym, bundle)
    save_cached(sym, "fmp", payload)
    return payload


def fetch_live_with_fallback(symbol: str) -> dict[str, Any]:
    """EDGAR first (free, ~20y); FMP fallback if key set and EDGAR fails."""
    sym = normalize_symbol(symbol)
    try:
        return fetch_edgar_and_cache(sym)
    except Exception as edgar_exc:
        import os

        if not os.environ.get("FMP_API_KEY", "").strip():
            raise edgar_exc
        try:
            return _fetch_fmp_fallback(sym)
        except Exception as fmp_exc:
            raise RuntimeError(f"EDGAR: {edgar_exc}; FMP fallback: {fmp_exc}") from fmp_exc


def _set_job(sym: str, **fields: Any) -> dict[str, Any]:
    with _lock:
        job = _jobs.setdefault(sym, {})
        job.update(fields)
        return dict(job)


def get_job(sym: str) -> dict[str, Any] | None:
    with _lock:
        j = _jobs.get(sym.upper())
        return dict(j) if j else None


def start_live_fetch(symbol: str) -> dict[str, Any]:
    """Background thread — avoids HTTP timeout on Render during EDGAR download."""
    sym = normalize_symbol(symbol)
    existing = get_job(sym)
    if existing and existing.get("status") == "running":
        return existing

    validation = validate_symbol(sym)
    if not validation["exists"]:
        return _set_job(sym, status="failed", error=validation["message"], validation=validation)

    if validation["cached"]:
        return _set_job(sym, status="done", error=None, validation=validation)

    _set_job(sym, status="running", error=None, validation=validation)

    def _run() -> None:
        try:
            fetch_live_with_fallback(sym)
            _set_job(sym, status="done", error=None)
        except Exception as exc:
            _set_job(sym, status="failed", error=str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return get_job(sym) or {"status": "running"}
