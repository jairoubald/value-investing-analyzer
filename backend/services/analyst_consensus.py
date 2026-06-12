"""Analyst price-target consensus — FMP primary, Yahoo Finance fallback."""

from __future__ import annotations

from datetime import date
from typing import Any

HORIZON = "12_month_forward"
HORIZON_LABEL = "12-month forward analyst price targets (not intrinsic value today)"


def _normalize(raw: dict[str, Any], *, source: str) -> dict[str, Any]:
    low = float(raw["low"])
    high = float(raw["high"])
    median = float(raw["median"])
    mean = float(raw["mean"])
    if low <= 0 or high <= 0 or high < low:
        raise ValueError("Invalid analyst target range")
    out: dict[str, Any] = {
        "low": round(low, 2),
        "high": round(high, 2),
        "median": round(median, 2),
        "mean": round(mean, 2),
        "analyst_count": raw.get("analyst_count"),
        "source": source,
        "horizon": HORIZON,
        "horizon_label": HORIZON_LABEL,
        "as_of": raw.get("as_of") or date.today().isoformat(),
        "source_note": raw.get("source_note") or _source_note(source),
        "summary": raw.get("summary") or {},
    }
    if raw.get("ratings"):
        out["ratings"] = raw["ratings"]
    return out


def _source_note(source: str) -> str:
    if source == "fmp":
        return "Financial Modeling Prep · price-target-consensus (aggregated sell-side targets)."
    return "Yahoo Finance · aggregated analyst targets (unofficial feed)."


def _normalize_ratings(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    strong_buy = int(row.get("strongBuy") or 0)
    buy = int(row.get("buy") or 0)
    hold = int(row.get("hold") or 0)
    sell = int(row.get("sell") or 0)
    strong_sell = int(row.get("strongSell") or 0)
    total = strong_buy + buy + hold + sell + strong_sell
    if total <= 0:
        return None
    return {
        "strong_buy": strong_buy,
        "buy": buy,
        "hold": hold,
        "sell": sell,
        "strong_sell": strong_sell,
        "total": total,
        "consensus_label": row.get("consensus"),
    }


def _from_fmp(ticker: str) -> dict[str, Any] | None:
    from services.fmp_provider import (
        FMPError,
        fetch_grades_consensus,
        fetch_price_target_consensus,
        fetch_price_target_summary,
    )

    try:
        row = fetch_price_target_consensus(ticker)
    except FMPError:
        return None
    if not row:
        return None

    low = row.get("targetLow")
    high = row.get("targetHigh")
    median = row.get("targetMedian")
    mean = row.get("targetConsensus")
    if any(v is None for v in (low, high, median, mean)):
        return None

    summary: dict[str, Any] = {}
    analyst_count = None
    try:
        summary_rows = fetch_price_target_summary(ticker)
        if summary_rows:
            summary = summary_rows[0] if isinstance(summary_rows, list) else summary_rows
            analyst_count = summary.get("lastYearCount") or summary.get("allTimeCount")
    except FMPError:
        pass

    ratings = None
    try:
        ratings = _normalize_ratings(fetch_grades_consensus(ticker))
    except FMPError:
        pass

    payload: dict[str, Any] = {
        "low": low,
        "high": high,
        "median": median,
        "mean": mean,
        "analyst_count": analyst_count,
        "as_of": date.today().isoformat(),
        "summary": {
            "last_month_count": summary.get("lastMonthCount"),
            "last_month_avg": summary.get("lastMonthAvgPriceTarget"),
            "last_quarter_count": summary.get("lastQuarterCount"),
            "last_quarter_avg": summary.get("lastQuarterAvgPriceTarget"),
            "last_year_count": summary.get("lastYearCount"),
            "last_year_avg": summary.get("lastYearAvgPriceTarget"),
        },
    }
    if ratings:
        payload["ratings"] = ratings

    return _normalize(payload, source="fmp")


def _from_yahoo(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    sym = ticker.upper()
    try:
        info = yf.Ticker(sym).info or {}
    except Exception:
        return None

    low = info.get("targetLowPrice")
    high = info.get("targetHighPrice")
    median = info.get("targetMedianPrice")
    mean = info.get("targetMeanPrice")
    if any(v is None for v in (low, high, median, mean)):
        try:
            t = yf.Ticker(sym)
            pt = t.get_analyst_price_targets() or {}
            low = low or pt.get("low")
            high = high or pt.get("high")
            median = median or pt.get("median")
            mean = mean or pt.get("mean")
        except Exception:
            pass

    if any(v is None for v in (low, high, median, mean)):
        return None

    return _normalize(
        {
            "low": low,
            "high": high,
            "median": median,
            "mean": mean,
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "as_of": date.today().isoformat(),
        },
        source="yahoo",
    )


def fetch_analyst_consensus(ticker: str) -> dict[str, Any]:
    """Return normalized consensus or {error: ...}."""
    sym = ticker.upper()
    for builder in (_from_fmp, _from_yahoo):
        try:
            data = builder(sym)
            if data:
                return data
        except (ValueError, TypeError):
            continue
    return {
        "error": (
            "Analyst price targets unavailable. "
            "Requires FMP price-target-consensus or Yahoo Finance fallback."
        )
    }
