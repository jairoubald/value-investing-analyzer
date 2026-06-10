"""Map FMP standardized statements → Excel 1 DATA JSON (engine input)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.one_data_schema import HISTORY_YEARS, ROW_BY_NUMBER, UNITS, YEAR_COL_COUNT, YEAR_COL_START


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_mln(v: Any) -> float | None:
    x = _f(v)
    if x is None:
        return None
    return x / 1_000_000.0


def _to_shares_mln(v: Any) -> float | None:
    x = _f(v)
    if x is None:
        return None
    # FMP reports raw share count; Excel 1 DATA stores millions of shares.
    if abs(x) > 1_000_000:
        return x / 1_000_000.0
    return x


def _sort_annual(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [r for r in rows if str(r.get("period", "FY")).upper() in ("FY", "ANNUAL", "YEAR")]
    if len(out) < len(rows) // 2:
        out = list(rows)
    out.sort(key=lambda r: r.get("date") or r.get("calendarYear") or "")
    return out[-min(YEAR_COL_COUNT, HISTORY_YEARS):]


def _index_by_date(
    income: list[dict],
    balance: list[dict],
    cashflow: list[dict],
    metrics: list[dict],
) -> list[dict[str, dict[str, Any]]]:
    inc = _sort_annual(income)
    bal = {r["date"]: r for r in _sort_annual(balance)}
    cf = {r["date"]: r for r in _sort_annual(cashflow)}
    km = {r["date"]: r for r in _sort_annual(metrics)}
    periods: list[dict[str, dict[str, Any]]] = []
    for row in inc:
        d = row["date"]
        periods.append(
            {
                "date": d,
                "calendarYear": row.get("calendarYear"),
                "income": row,
                "balance": bal.get(d, {}),
                "cashflow": cf.get(d, {}),
                "metrics": km.get(d, {}),
            }
        )
    return periods


def _fy_label(calendar_year: Any, date_str: str) -> str:
    if calendar_year is not None:
        return f"FY {calendar_year}"
    return f"FY {date_str[:4]}"


def _end_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y")
    except ValueError:
        return date_str


def _derived_rows(p: dict[str, dict[str, Any]]) -> dict[int, float | None]:
    inc = p["income"]
    bal = p["balance"]

    payables = _f(bal.get("accountPayables"))
    accrued = _f(bal.get("accruedExpenses")) or 0.0
    if payables is not None and accrued:
        payables = payables + accrued

    total_cl = _f(bal.get("totalCurrentLiabilities"))
    st_debt = _f(bal.get("shortTermDebt")) or 0.0
    other_st = None
    if total_cl is not None and payables is not None:
        other_st = total_cl - payables - st_debt

    common = _f(bal.get("commonStock")) or 0.0
    apic = _f(bal.get("additionalPaidInCapital")) or 0.0
    share_cap = common + apic if (common or apic) else None

    other_lt_assets = _f(bal.get("otherNonCurrentAssets"))
    if other_lt_assets is None:
        tnca = _f(bal.get("totalNonCurrentAssets"))
        parts = [
            _f(bal.get("propertyPlantEquipmentNet")),
            _f(bal.get("goodwill")),
            _f(bal.get("intangibleAssets")),
            _f(bal.get("longTermInvestments")),
        ]
        if tnca is not None and any(x is not None for x in parts):
            other_lt_assets = tnca - sum(x or 0 for x in parts)

    return {
        131: _to_mln(payables),
        142: _to_mln(other_st),
        119: _to_mln(other_lt_assets),
        164: _to_mln(share_cap),
    }


def _row_values(p: dict[str, dict[str, Any]]) -> dict[int, float | None]:
    inc = p["income"]
    bal = p["balance"]
    cf = p["cashflow"]

    derived = _derived_rows(p)

    return {
        14: _to_mln(inc.get("revenue")),
        16: _to_mln(inc.get("costOfRevenue")),
        18: _to_mln(inc.get("grossProfit")),
        20: _to_mln(inc.get("operatingExpenses")),
        26: _to_mln(inc.get("operatingIncome")),
        27: _to_mln(inc.get("totalOtherIncomeExpensesNet")),
        28: _to_mln(inc.get("interestExpense")),
        50: _to_mln(inc.get("netIncome")),
        62: _f(inc.get("eps")),
        99: _to_mln(bal.get("cashAndCashEquivalents")),
        100: _to_mln(bal.get("shortTermInvestments")),
        113: _to_mln(bal.get("totalCurrentAssets")),
        114: _to_mln(bal.get("propertyPlantEquipmentNet")),
        117: _to_mln(bal.get("longTermInvestments")),
        121: _to_mln(bal.get("goodwill")),
        127: _to_mln(bal.get("totalNonCurrentAssets")),
        128: _to_mln(bal.get("totalAssets")),
        136: _to_mln(bal.get("shortTermDebt")),
        146: _to_mln(bal.get("totalCurrentLiabilities")),
        147: _to_mln(bal.get("longTermDebt")),
        152: _to_mln(bal.get("otherNonCurrentLiabilities")),
        161: _to_mln(bal.get("totalNonCurrentLiabilities")),
        167: _to_mln(bal.get("treasuryStock")),
        168: _to_mln(bal.get("retainedEarnings")),
        172: _to_mln(bal.get("totalStockholdersEquity")),
        177: _to_shares_mln(inc.get("weightedAverageShsOut") or inc.get("weightedAverageShsOutDil")),
        209: _to_mln(cf.get("operatingCashFlow")),
        212: _to_mln(cf.get("capitalExpenditure") or cf.get("investmentsInPropertyPlantAndEquipment")),
        222: _to_mln(cf.get("acquisitionsNet")),
        231: _to_mln(cf.get("dividendsPaid")),
        232: _to_mln(cf.get("debtRepayment") or cf.get("netDebtIssuance")),
        **derived,
    }


def normalize_fmp_bundle(symbol: str, bundle: dict[str, Any]) -> dict[str, Any]:
    profile = bundle["profile"]
    periods = _index_by_date(
        bundle["income"],
        bundle["balance"],
        bundle["cashflow"],
        bundle.get("key_metrics") or [],
    )
    if not periods:
        raise ValueError(f"No annual periods from FMP for {symbol}")

    years: list[dict[str, Any]] = []
    grid: dict[str, dict[str, Any]] = {}

    for i, p in enumerate(periods):
        col = YEAR_COL_START + i
        years.append(
            {
                "col": col,
                "fy": _fy_label(p.get("calendarYear"), p["date"]),
                "end_date": _end_date(p["date"]),
            }
        )
        row_vals = _row_values(p)
        for row_num, val in row_vals.items():
            if val is None:
                continue
            spec = ROW_BY_NUMBER.get(row_num)
            label = spec.label if spec else f"row_{row_num}"
            entry = grid.setdefault(str(row_num), {"label": label, "values": {}})
            entry["values"][str(col)] = val

    # Tax rate for engine (Excel row 11 col 21) — effective tax on latest FY.
    latest = periods[-1]["income"]
    ibt = _f(latest.get("incomeBeforeTax"))
    tax = _f(latest.get("incomeTaxExpense"))
    if ibt and tax is not None and ibt != 0:
        grid.setdefault("11", {"label": "Effective tax rate", "values": {}})
        grid["11"]["values"]["21"] = abs(tax / ibt) * 100.0

    # Optional market strip (cols 39+) — quote only, not WACC history.
    quote = bundle.get("quote") or {}
    if quote.get("price") is not None:
        grid.setdefault("15", {"label": "PX_LAST", "values": {}})
        grid["15"]["values"]["39"] = _f(quote.get("price"))
        if quote.get("previousClose") is not None:
            grid["15"]["values"]["38"] = _f(quote.get("previousClose"))

    ticker = symbol.upper()
    return {
        "ticker": ticker,
        "company": profile.get("companyName") or f"{ticker} US Equity",
        "currency": profile.get("currency") or "USD",
        "units": UNITS,
        "years": years,
        "grid": grid,
        "source": "fmp",
        "source_provider": "Financial Modeling Prep",
        "source_fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
