from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests

SEC_HEADERS = {"User-Agent": "ValueInvestingAnalyzer/1.0 (value-investing@local.app)"}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

TAG_CANDIDATES = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "current_debt": ["DebtCurrent", "ShortTermBorrowings"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
}


@lru_cache(maxsize=1)
def _load_ticker_map() -> dict[str, dict[str, Any]]:
    response = requests.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return {entry["ticker"].upper(): entry for entry in payload.values()}


def _lookup_cik(ticker: str) -> tuple[str, dict[str, Any]]:
    ticker_map = _load_ticker_map()
    entry = ticker_map.get(ticker.upper())
    if not entry:
        raise ValueError(
            f"No se encontró el ticker {ticker}. Solo están disponibles emisores registrados en la SEC (EE.UU.)."
        )
    cik = str(entry["cik_str"]).zfill(10)
    return cik, entry


def _annual_by_fy(gaap: dict[str, Any], tag_candidates: list[str]) -> dict[int, float]:
    merged: dict[int, dict[str, Any]] = {}

    for tag in tag_candidates:
        concept = gaap.get(tag)
        if not concept:
            continue

        for item in concept.get("units", {}).get("USD", []):
            if item.get("form") != "10-K" or item.get("fp") != "FY":
                continue

            fy = item.get("fy")
            if fy is None:
                continue

            current = merged.get(fy)
            if current is None or item.get("filed", "") >= current.get("filed", ""):
                merged[fy] = item

    return {fy: float(item["val"]) for fy, item in merged.items()}


def _value_for_fy(values: dict[int, float], fy: int) -> float | None:
    return values.get(fy)


def _margin(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def analyze_ticker(ticker: str, years: int = 10) -> dict[str, Any]:
    symbol = ticker.strip().upper()
    cik, entry = _lookup_cik(symbol)

    response = requests.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers=SEC_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    facts = response.json()

    gaap = facts.get("facts", {}).get("us-gaap", {})
    if not gaap:
        raise ValueError(f"No se encontraron datos financieros para {symbol}")

    revenue = _annual_by_fy(gaap, TAG_CANDIDATES["revenue"])
    if not revenue:
        raise ValueError(f"No se encontraron datos de ingresos para {symbol}")

    gross_profit = _annual_by_fy(gaap, TAG_CANDIDATES["gross_profit"])
    operating_income = _annual_by_fy(gaap, TAG_CANDIDATES["operating_income"])
    net_income = _annual_by_fy(gaap, TAG_CANDIDATES["net_income"])
    equity = _annual_by_fy(gaap, TAG_CANDIDATES["equity"])
    long_term_debt = _annual_by_fy(gaap, TAG_CANDIDATES["long_term_debt"])
    current_debt = _annual_by_fy(gaap, TAG_CANDIDATES["current_debt"])
    operating_cf = _annual_by_fy(gaap, TAG_CANDIDATES["operating_cash_flow"])
    capex = _annual_by_fy(gaap, TAG_CANDIDATES["capex"])

    fiscal_years = sorted(
        set(revenue)
        | set(gross_profit)
        | set(operating_income)
        | set(net_income)
        | set(equity)
        | set(long_term_debt)
        | set(current_debt)
        | set(operating_cf)
        | set(capex)
    )[-years:]
    annual_data: list[dict[str, Any]] = []

    for fy in fiscal_years:
        rev = _value_for_fy(revenue, fy)
        gp = _value_for_fy(gross_profit, fy)
        op = _value_for_fy(operating_income, fy)
        ni = _value_for_fy(net_income, fy)
        eq = _value_for_fy(equity, fy)
        ltd = _value_for_fy(long_term_debt, fy)
        cd = _value_for_fy(current_debt, fy)
        ocf = _value_for_fy(operating_cf, fy)
        cx = _value_for_fy(capex, fy)

        total_debt = None
        if ltd is not None or cd is not None:
            total_debt = (ltd or 0) + (cd or 0)

        free_cash_flow = None
        if ocf is not None and cx is not None:
            free_cash_flow = ocf - abs(cx)

        annual_data.append(
            {
                "year": str(fy),
                "revenue": rev,
                "gross_margin": _margin(gp, rev),
                "operating_margin": _margin(op, rev),
                "net_margin": _margin(ni, rev),
                "roe": _margin(ni, eq),
                "total_debt": total_debt,
                "operating_cash_flow": ocf,
                "free_cash_flow": free_cash_flow,
            }
        )

    company_name = facts.get("entityName") or entry.get("title") or symbol

    return {
        "ticker": symbol,
        "company_name": company_name,
        "currency": "USD",
        "years": annual_data,
    }
