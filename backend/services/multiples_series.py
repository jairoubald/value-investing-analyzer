"""Monthly trailing P/E and P/BV from FMP prices + quarterly fundamentals."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any

from services.fmp_provider import (
    FMPError,
    FMP_QUARTERLY_LIMIT,
    fetch_historical_prices_eod,
    fetch_income,
    fetch_income_quarterly,
    fetch_key_metrics_quarterly,
)

MONTHS_HISTORY = 10 * 12  # ~10 years of monthly points
PE_VALIDATION_TOLERANCE = 0.05  # 5% vs FMP quarterly peRatio


def _parse_date(value: str) -> date:
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return datetime.strptime(raw[:10], "%Y-%m-%d").date()


def _month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _month_end_asof(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _subtract_months(d: date, months: int) -> date:
    m = d.month - 1 - months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def month_end_prices(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Last trading close per calendar month."""
    by_month: dict[str, float] = {}
    for row in sorted(rows, key=lambda r: str(r.get("date", ""))):
        raw = row.get("close") or row.get("adjClose") or row.get("price")
        if raw is None:
            continue
        d = _parse_date(str(row["date"]))
        by_month[_month_key(d)] = float(raw)
    return by_month


def _row_eps(row: dict[str, Any]) -> float | None:
    for key in ("epsDiluted", "epsdiluted", "eps"):
        val = row.get(key)
        if val is not None:
            return float(val)
    return None


def _quarterly_eps_diluted(rows: list[dict[str, Any]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    for row in sorted(rows, key=lambda r: str(r.get("date", ""))):
        eps = _row_eps(row)
        if eps is None:
            continue
        out.append((_parse_date(str(row["date"])), eps))
    return out


def _quarterly_bvps(rows: list[dict[str, Any]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    for row in sorted(rows, key=lambda r: str(r.get("date", ""))):
        bvps = row.get("bookValuePerShare")
        if bvps is None:
            continue
        out.append((_parse_date(str(row["date"])), float(bvps)))
    return out


def _grid_value(grid: dict[str, Any], row: int, col: int) -> float | None:
    values = (grid.get(str(row)) or {}).get("values") or {}
    val = values.get(str(col))
    if val is None:
        return None
    return float(val)


def _likely_split_ratio(ratio: float) -> float | None:
    if ratio < 1.5:
        return None
    for factor in (2, 3, 4, 5, 6, 7, 8, 10, 20):
        if abs(ratio - factor) / factor <= 0.12:
            return float(factor)
    return None


def _sanitize_shares(shares: list[float | None]) -> list[float | None]:
    """Split-adjust older share counts so NI/shares aligns with split-adjusted prices."""
    scaled: list[float | None] = [None if s is None or s <= 0 else float(s) for s in shares]
    for i in range(1, len(scaled)):
        prev, curr = scaled[i - 1], scaled[i]
        if prev is None or curr is None or prev <= 0:
            continue
        ratio = curr / prev
        factor = _likely_split_ratio(ratio)
        if factor is not None:
            for j in range(i):
                if scaled[j] is not None:
                    scaled[j] *= factor
            continue
        if ratio > 2.5 or ratio < 0.4:
            scaled[i] = None
    return scaled


def _annual_eps_overrides(income_annual: list[dict[str, Any]]) -> dict[date, float]:
    out: dict[date, float] = {}
    for row in income_annual:
        eps = _row_eps(row)
        if eps is None or eps <= 0:
            continue
        out[_parse_date(str(row["date"]))] = eps
    return out


def _quarters_from_payload(
    payload: dict[str, Any],
    *,
    income_annual: list[dict[str, Any]] | None = None,
) -> tuple[list[tuple[date, float]], list[tuple[date, float]]]:
    """Approximate quarterly EPS/BVPS from annual EDGAR grid (NI & equity in MLN, shares in MLN)."""
    grid = payload.get("grid") or {}
    years = payload.get("years") or []
    fmp_eps = _annual_eps_overrides(income_annual or [])

    raw_shares: list[float | None] = []
    year_meta: list[tuple[int, date, float | None, float | None]] = []
    for year in years:
        col = int(year["col"])
        end_raw = year.get("end_date")
        if not end_raw:
            raw_shares.append(None)
            continue
        fy_end = _parse_date(str(end_raw))
        ni = _grid_value(grid, 50, col)
        sh = _grid_value(grid, 177, col)
        eq = _grid_value(grid, 172, col)
        raw_shares.append(sh)
        year_meta.append((col, fy_end, ni, eq))

    clean_shares = _sanitize_shares(raw_shares)
    quarters_eps: list[tuple[date, float]] = []
    quarters_bvps: list[tuple[date, float]] = []

    for i, (col, fy_end, ni, eq) in enumerate(year_meta):
        shares = clean_shares[i]
        if shares is None or shares <= 0:
            continue
        annual_eps = fmp_eps.get(fy_end)
        if annual_eps is None:
            if ni is None or ni <= 0:
                continue
            annual_eps = ni / shares
        if annual_eps <= 0:
            continue
        quarter_eps = annual_eps / 4.0
        for months_back in (0, 3, 6, 9):
            q_end = _subtract_months(fy_end, months_back)
            quarters_eps.append((q_end, quarter_eps))
        if eq is not None and eq > 0:
            bvps = eq / shares
            if bvps > 0:
                quarters_bvps.append((fy_end, bvps))

    quarters_eps.sort(key=lambda x: x[0])
    quarters_bvps.sort(key=lambda x: x[0])
    return quarters_eps, quarters_bvps


def _merge_quarter_series(
    primary: list[tuple[date, float]],
    fallback: list[tuple[date, float]],
) -> list[tuple[date, float]]:
    """Prefer FMP quarterly points; fill gaps from annualized grid estimates."""
    if not primary:
        return fallback
    if not fallback:
        return primary
    merged = {d: v for d, v in fallback}
    for d, v in primary:
        merged[d] = v
    return sorted(merged.items(), key=lambda x: x[0])


def _vendor_ratio_by_date(rows: list[dict[str, Any]], field: str) -> dict[date, float]:
    out: dict[date, float] = {}
    for row in rows:
        val = row.get(field)
        if val is None:
            continue
        out[_parse_date(str(row["date"]))] = float(val)
    return out


def _ttm_eps_asof(quarters: list[tuple[date, float]], asof: date) -> float | None:
    available = [(d, e) for d, e in quarters if d <= asof]
    if len(available) < 4:
        return None
    ttm = sum(e for _, e in available[-4:])
    return ttm if ttm > 0 else None


def _latest_point_asof(points: list[tuple[date, float]], asof: date) -> float | None:
    available = [v for d, v in points if d <= asof]
    return available[-1] if available else None


def _validation_stats(
    points: list[dict[str, Any]],
    vendor: dict[date, float],
) -> dict[str, Any]:
    checked = 0
    within = 0
    max_delta = 0.0
    for pt in points:
        asof = _parse_date(pt["asof"])
        vendor_pe = vendor.get(asof)
        if vendor_pe is None or vendor_pe <= 0:
            continue
        checked += 1
        delta = abs(pt["pe"] - vendor_pe) / vendor_pe
        max_delta = max(max_delta, delta)
        if delta <= PE_VALIDATION_TOLERANCE:
            within += 1
    return {
        "vendor_checks": checked,
        "vendor_within_tolerance": within,
        "vendor_max_delta_pct": round(max_delta * 100, 2) if checked else None,
        "tolerance_pct": PE_VALIDATION_TOLERANCE * 100,
    }


def build_monthly_pe_series(
    *,
    prices_by_month: dict[str, float],
    quarters_eps: list[tuple[date, float]],
    key_metrics_quarterly: list[dict[str, Any]] | None = None,
    months: int = MONTHS_HISTORY,
    source_note: str | None = None,
) -> dict[str, Any]:
    vendor_pe = _vendor_ratio_by_date(key_metrics_quarterly or [], "peRatio")

    month_keys = sorted(prices_by_month.keys())[-months:]
    points: list[dict[str, Any]] = []

    for mk in month_keys:
        y, m = (int(p) for p in mk.split("-"))
        asof = _month_end_asof(y, m)
        price = prices_by_month[mk]
        ttm = _ttm_eps_asof(quarters_eps, asof)
        if ttm is None:
            continue
        pe = price / ttm
        vendor = vendor_pe.get(asof)
        pt: dict[str, Any] = {
            "month": mk,
            "asof": asof.isoformat(),
            "price": round(price, 4),
            "eps_ttm": round(ttm, 4),
            "pe": round(pe, 4),
        }
        if vendor is not None and vendor > 0:
            pt["vendor_pe"] = round(vendor, 4)
            pt["vendor_delta_pct"] = round(abs(pe - vendor) / vendor * 100, 2)
        points.append(pt)

    history_values = [p["pe"] for p in points]
    validation = _validation_stats(points, vendor_pe)
    note = source_note or (
        "Month-end close ÷ sum of last 4 quarterly diluted EPS; "
        "validated vs FMP quarterly peRatio where available."
    )

    return {
        "method": "month_end_price_over_diluted_eps_ttm",
        "eps_basis": "diluted",
        "frequency": "monthly",
        "points": points,
        "history_values": history_values,
        "history_labels": [p["month"] for p in points],
        "validation": validation,
        "source_note": note,
    }


def build_monthly_pbv_series(
    *,
    prices_by_month: dict[str, float],
    quarters_bvps: list[tuple[date, float]],
    key_metrics_quarterly: list[dict[str, Any]] | None = None,
    months: int = MONTHS_HISTORY,
    source_note: str | None = None,
) -> dict[str, Any]:
    vendor_pb = _vendor_ratio_by_date(key_metrics_quarterly or [], "pbRatio")

    month_keys = sorted(prices_by_month.keys())[-months:]
    points: list[dict[str, Any]] = []

    for mk in month_keys:
        y, m = (int(p) for p in mk.split("-"))
        asof = _month_end_asof(y, m)
        price = prices_by_month[mk]
        bvps = _latest_point_asof(quarters_bvps, asof)
        if bvps is None or bvps <= 0:
            continue
        pbv = price / bvps
        vendor = vendor_pb.get(asof)
        pt: dict[str, Any] = {
            "month": mk,
            "asof": asof.isoformat(),
            "price": round(price, 4),
            "book_value_per_share": round(bvps, 4),
            "pbv": round(pbv, 4),
        }
        if vendor is not None and vendor > 0:
            pt["vendor_pbv"] = round(vendor, 4)
            pt["vendor_delta_pct"] = round(abs(pbv - vendor) / vendor * 100, 2)
        points.append(pt)

    history_values = [p["pbv"] for p in points]
    note = source_note or (
        "Month-end close ÷ book value per share from latest reported quarter (FMP key metrics)."
    )

    return {
        "method": "month_end_price_over_book_value_per_share",
        "frequency": "monthly",
        "points": points,
        "history_values": history_values,
        "history_labels": [p["month"] for p in points],
        "source_note": note,
    }


def build_multiples_series(
    *,
    symbol: str,
    price_rows: list[dict[str, Any]],
    income_quarterly: list[dict[str, Any]] | None = None,
    key_metrics_quarterly: list[dict[str, Any]] | None = None,
    income_annual: list[dict[str, Any]] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prices = month_end_prices(price_rows)
    fmp_eps = _quarterly_eps_diluted(income_quarterly or [])
    fmp_bvps = _quarterly_bvps(key_metrics_quarterly or [])

    grid_eps: list[tuple[date, float]] = []
    grid_bvps: list[tuple[date, float]] = []
    if payload:
        grid_eps, grid_bvps = _quarters_from_payload(payload, income_annual=income_annual)

    quarters_eps = _merge_quarter_series(fmp_eps, grid_eps)
    quarters_bvps = _merge_quarter_series(fmp_bvps, grid_bvps)

    used_grid_eps = bool(grid_eps) and len(quarters_eps) > len(fmp_eps)
    used_grid_bv = bool(grid_bvps) and (not fmp_bvps or len(quarters_bvps) > len(fmp_bvps))

    pe_note = (
        "Month-end close ÷ trailing diluted EPS (TTM); FMP quarterly EPS where available, "
        "annual EDGAR NI ÷ shares split into fiscal quarters for longer history."
        if used_grid_eps
        else "Month-end close ÷ sum of last 4 quarterly diluted EPS; "
        "validated vs FMP quarterly peRatio where available."
    )
    pbv_note = (
        "Month-end close ÷ book value per share; FMP quarterly where available, "
        "annual EDGAR equity ÷ shares at fiscal year-end for longer history."
        if used_grid_bv
        else "Month-end close ÷ book value per share from latest reported quarter (FMP key metrics)."
    )

    pe = build_monthly_pe_series(
        prices_by_month=prices,
        quarters_eps=quarters_eps,
        key_metrics_quarterly=key_metrics_quarterly,
        source_note=pe_note,
    )
    pbv = build_monthly_pbv_series(
        prices_by_month=prices,
        quarters_bvps=quarters_bvps,
        key_metrics_quarterly=key_metrics_quarterly,
        source_note=pbv_note,
    )
    return {
        "ticker": symbol.upper(),
        "built_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "pe": pe,
        "pbv": pbv,
    }


def build_multiples_series_from_fmp_rows(
    *,
    symbol: str,
    price_rows: list[dict[str, Any]],
    income_quarterly: list[dict[str, Any]],
    key_metrics_quarterly: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_multiples_series(
        symbol=symbol,
        price_rows=price_rows,
        income_quarterly=income_quarterly,
        key_metrics_quarterly=key_metrics_quarterly,
        payload=payload,
    )


def fetch_and_build_multiples_series(
    symbol: str,
    *,
    years: int = 10,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Live FMP fetch — requires FMP_API_KEY for prices; fundamentals may come from EDGAR grid."""
    sym = symbol.upper()
    price_rows = fetch_historical_prices_eod(sym, years=years)

    income_q: list[dict[str, Any]] = []
    metrics_q: list[dict[str, Any]] = []
    income_a: list[dict[str, Any]] = []
    try:
        income_q = fetch_income_quarterly(sym)
    except FMPError:
        pass
    try:
        metrics_q = fetch_key_metrics_quarterly(sym)
    except FMPError:
        pass
    if payload:
        try:
            income_a = fetch_income(sym, limit=5)
        except FMPError:
            pass

    series = build_multiples_series(
        symbol=sym,
        price_rows=price_rows,
        income_quarterly=income_q,
        key_metrics_quarterly=metrics_q,
        income_annual=income_a,
        payload=payload,
    )
    if not series["pe"]["history_values"] and not payload:
        raise FMPError(
            "Could not build P/E history — need EDGAR cache payload or FMP quarterly income."
        )
    return series


def attach_multiples_to_payload(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Return payload with multiples_series attached (mutates copy)."""
    out = dict(payload)
    try:
        out["multiples_series"] = fetch_and_build_multiples_series(symbol, payload=out)
    except FMPError as exc:
        out["multiples_series_error"] = str(exc)
    except Exception as exc:  # pragma: no cover
        out["multiples_series_error"] = str(exc)
    return out
