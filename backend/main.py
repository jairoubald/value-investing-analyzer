from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from services.data_cache import list_cached_tickers, load_cached
from services.magic_numbers import DataSheet, compute_magic_numbers, load_preloaded
from services.stock_analyzer import analyze_ticker
from services.ticker_lookup import (
    get_job,
    normalize_symbol,
    start_live_fetch,
    validate_symbol,
)
from services.top_tickers import TOP_US_50, TOP_US_TICKERS

STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(__file__).parent / "data"

load_dotenv(Path(__file__).parent / ".env")

app = FastAPI(title="Financial Thesis Tool")


@app.on_event("startup")
def _warm_sec_ticker_map() -> None:
    """Pre-load SEC ticker list so LOOKUP is not slow on first custom search."""
    import threading

    def _run() -> None:
        try:
            from services.edgar_provider import _ticker_cik_map

            _ticker_cik_map()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _live_fetch_enabled() -> bool:
    return os.environ.get("ALLOW_LIVE_FETCH", "false").strip().lower() in ("1", "true", "yes")


@app.get("/api/health")
def health():
    cached = list_cached_tickers()
    return {
        "status": "ok",
        "cached_tickers": cached,
        "top50_count": len(TOP_US_50),
        "live_fetch": _live_fetch_enabled(),
        "live_search": True,
        "fmp_key_loaded": bool(os.environ.get("FMP_API_KEY", "").strip()),
        "engine": "magic_numbers_v4_top50_search",
        "sources": ["preload", "fmp", "edgar"],
    }


@app.get("/api/tickers")
def tickers():
    cached = set(list_cached_tickers())
    return {
        "top_us": list(TOP_US_50),
        "top10": list(TOP_US_TICKERS),
        "cached": sorted(cached),
        "ready": [t for t in TOP_US_50 if t in cached],
    }


@app.get("/api/ticker/{ticker}")
def ticker_lookup(ticker: str):
    """Step 1: validate ticker exists (SEC) and whether data is cached."""
    sym = normalize_symbol(ticker)
    info = validate_symbol(sym)
    info["in_top50"] = sym in TOP_US_50
    return info


@app.post("/api/ticker/{ticker}/refresh")
def ticker_refresh(ticker: str):
    """Step 2: fetch live from SEC EDGAR (background), save cache, poll /refresh/status."""
    sym = normalize_symbol(ticker)
    job = start_live_fetch(sym)
    if job.get("status") == "failed":
        raise HTTPException(status_code=400, detail=job.get("error", "Fetch failed"))
    return {"symbol": sym, **job}


@app.get("/api/ticker/{ticker}/refresh/status")
def ticker_refresh_status(ticker: str):
    sym = normalize_symbol(ticker)
    job = get_job(sym)
    if job:
        return {"symbol": sym, **job}
    cached = load_cached(sym, "edgar") is not None or load_cached(sym, "fmp") is not None
    return {"symbol": sym, "status": "done" if cached else "idle", "cached": cached}


def _thesis_from_payload(payload: dict) -> dict:
    return compute_magic_numbers(DataSheet(payload))


def _resolve_cached(symbol: str, src: str) -> dict | None:
    if src == "preload":
        return load_cached(symbol, "preload")
    if src == "fmp":
        return load_cached(symbol, "fmp") or load_cached(symbol, "auto")
    if src == "edgar":
        return load_cached(symbol, "edgar") or load_cached(symbol, "auto")
    return load_cached(symbol, "auto")


def _live_fmp(symbol: str) -> dict:
    from services.fmp_provider import fetch_bundle
    from services.normalize_fmp import normalize_fmp_bundle

    bundle = fetch_bundle(symbol)
    return normalize_fmp_bundle(symbol, bundle)


def _live_edgar(symbol: str) -> dict:
    from services.edgar_provider import fetch_company_facts
    from services.normalize_edgar import normalize_edgar_facts

    facts = fetch_company_facts(symbol)
    return normalize_edgar_facts(symbol, facts)


@app.get("/api/thesis/{ticker}")
def thesis(ticker: str, source: str = "preload"):
    symbol = normalize_symbol(ticker)
    src = source.lower()

    cached = _resolve_cached(symbol, src)
    if cached:
        return _thesis_from_payload(cached)

    if not _live_fetch_enabled():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No cached data for {symbol}. "
                "Use the search box — valid tickers can be fetched live from SEC EDGAR."
            ),
        )

    if src == "fmp":
        try:
            return _thesis_from_payload(_live_fmp(symbol))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"FMP homologation failed: {exc}") from exc

    if src in ("edgar", "preload"):
        try:
            return _thesis_from_payload(_live_edgar(symbol))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"EDGAR homologation failed: {exc}") from exc

    raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found.")


@app.get("/api/thesis")
def thesis_default():
    return load_preloaded("MSFT")


@app.get("/api/analyze/{ticker}")
def analyze(ticker: str, years: int = 10):
    if years < 1 or years > 15:
        raise HTTPException(status_code=400, detail="years debe estar entre 1 y 15")

    try:
        return analyze_ticker(ticker, years=years)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al obtener datos del ticker: {exc}",
        ) from exc


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
