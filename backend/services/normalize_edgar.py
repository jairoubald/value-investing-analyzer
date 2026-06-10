"""Map SEC EDGAR XBRL companyfacts → Excel 1 DATA JSON."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.one_data_common import end_date_fmt, fy_label, to_float, to_mln, to_shares_mln
from services.one_data_schema import ROW_BY_NUMBER, UNITS, YEAR_COL_START

# us-gaap tag fallbacks per 1 DATA row (first match wins).
ROW_TAGS: dict[int, tuple[str, ...]] = {
    14: ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    16: ("CostOfGoodsAndServicesSold", "CostOfRevenue"),
    18: ("GrossProfit",),
    20: ("OperatingExpenses", "CostsAndExpenses"),
    26: ("OperatingIncomeLoss",),
    27: ("NonoperatingIncomeExpense", "OtherNonoperatingIncomeExpense"),
    28: ("InterestExpense", "InterestExpenseDebt"),
    50: ("NetIncomeLoss",),
    62: ("EarningsPerShareBasic",),
    99: ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"),
    100: ("ShortTermInvestments",),
    113: ("AssetsCurrent",),
    114: ("PropertyPlantAndEquipmentNet",),
    117: ("LongTermInvestments",),
    121: ("Goodwill",),
    127: ("AssetsNoncurrent",),
    128: ("Assets",),
    131: ("AccountsPayableCurrent",),
    136: ("ShortTermBorrowings", "LongTermDebtCurrent"),
    146: ("LiabilitiesCurrent",),
    147: ("LongTermDebtNoncurrent", "LongTermDebt"),
    152: ("OtherLiabilitiesNoncurrent",),
    161: ("LiabilitiesNoncurrent",),
    164: ("CommonStocksIncludingAdditionalPaidInCapital", "CommonStockValue"),
    167: ("TreasuryStockValue",),
    168: ("RetainedEarningsAccumulatedDeficit",),
    172: ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    177: ("WeightedAverageNumberOfSharesOutstandingBasic",),
    209: ("NetCashProvidedByUsedInOperatingActivities",),
    212: ("PaymentsToAcquirePropertyPlantAndEquipment",),
    222: ("PaymentsToAcquireBusinessesNetOfCashAcquired",),
    231: ("PaymentsOfDividends",),
    232: ("ProceedsFromRepaymentsOfDebt", "RepaymentsOfDebt"),
}

DEFAULT_YEARS = 5

# Excel 1 DATA stores capex / dividends as negative cash outflows.
NEGATE_FOR_EXCEL = frozenset({212, 222, 231})


def _annual_facts(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    if tag not in gaap:
        return []
    units = gaap[tag].get("units", {})
    rows: list[dict[str, Any]] = []
    for unit_rows in units.values():
        for row in unit_rows:
            if row.get("fp") != "FY":
                continue
            form = row.get("form") or ""
            if form and not form.startswith(("10-K", "20-F", "40-F")):
                continue
            rows.append(row)
    return rows


def _pick_best_by_end(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One fact per period-end date; prefer the latest filing."""
    by_end: dict[str, dict[str, Any]] = {}
    for row in rows:
        end = row.get("end")
        if not end:
            continue
        prev = by_end.get(end)
        if prev is None or (row.get("filed", "") > prev.get("filed", "")):
            by_end[end] = row
    return by_end


def _series_for_tag(facts: dict[str, Any], tag: str) -> dict[str, dict[str, Any]]:
    return _pick_best_by_end(_annual_facts(facts, tag))


def _value_for_end(tag_series: dict[str, dict[str, Any]], end: str) -> float | None:
    row = tag_series.get(end)
    return to_float(row["val"]) if row else None


def _build_period_ends(facts: dict[str, Any], limit: int = DEFAULT_YEARS) -> list[str]:
    """Period keys = fiscal year-end dates (not SEC fy integer — can misalign vs FMP)."""
    rev: dict[str, dict[str, Any]] = {}
    for tag in ROW_TAGS[14]:
        rev = _series_for_tag(facts, tag)
        if rev:
            break
    if not rev:
        raise ValueError("No annual revenue facts in EDGAR payload")
    return sorted(rev.keys())[-limit:]


def _row_value(facts: dict[str, Any], row: int, end: str) -> float | None:
    for tag in ROW_TAGS.get(row, ()):
        val = _value_for_end(_series_for_tag(facts, tag), end)
        if val is not None:
            return val
    return None


def normalize_edgar_facts(symbol: str, facts_payload: dict[str, Any]) -> dict[str, Any]:
    entity = facts_payload.get("entityName") or symbol.upper()
    period_ends = _build_period_ends(facts_payload)

    years: list[dict[str, Any]] = []
    grid: dict[str, dict[str, Any]] = {}

    for i, end in enumerate(period_ends):
        col = YEAR_COL_START + i
        fy_num = int(end[:4])

        years.append(
            {
                "col": col,
                "fy": fy_label(fy_num, end),
                "end_date": end_date_fmt(end),
            }
        )

        for row_num in ROW_TAGS:
            raw = _row_value(facts_payload, row_num, end)
            if raw is None:
                continue
            spec = ROW_BY_NUMBER.get(row_num)
            label = spec.label if spec else f"row_{row_num}"
            if row_num in (62,):
                val = raw
            elif row_num == 177:
                val = to_shares_mln(raw)
            else:
                val = to_mln(raw)
            if val is not None and row_num in NEGATE_FOR_EXCEL:
                val = -abs(val)
            entry = grid.setdefault(str(row_num), {"label": label, "values": {}})
            entry["values"][str(col)] = val

    latest_end = period_ends[-1]
    ibt = _row_value(facts_payload, 50, latest_end)
    for tag in (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeBeforeEquityMethodInvestments",
    ):
        v = _value_for_end(_series_for_tag(facts_payload, tag), latest_end)
        if v is not None:
            ibt = v
            break
    tax = _value_for_end(_series_for_tag(facts_payload, "IncomeTaxExpenseBenefit"), latest_end)
    if ibt and tax is not None and ibt != 0:
        grid.setdefault("11", {"label": "Effective tax rate", "values": {}})
        grid["11"]["values"]["21"] = abs(tax / ibt) * 100.0

    return {
        "ticker": symbol.upper(),
        "company": entity,
        "currency": "USD",
        "units": UNITS,
        "years": years,
        "grid": grid,
        "source": "edgar",
        "source_provider": "SEC EDGAR XBRL",
        "source_fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
