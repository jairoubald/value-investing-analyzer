from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "msft_1data.json"


class DataSheet:
    """In-memory 1 DATA grid (row/col aligned with Excel)."""

    def __init__(self, payload: dict[str, Any]):
        self.company = payload.get("company")
        self.currency = payload.get("currency")
        self.units = payload.get("units")
        self.ticker = payload.get("ticker", "")
        self.source = payload.get("source", "preload")
        self.source_provider = payload.get("source_provider")
        self.years = payload["years"]
        self._grid = payload["grid"]
        self.year_cols = [y["col"] for y in self.years]

    def val(self, row: int, col: int) -> float | None:
        row_s = self._grid.get(str(row), {})
        values = row_s.get("values", {})
        v = values.get(str(col))
        if v is None:
            return None
        return float(v)

    def year_labels(self) -> list[str]:
        return [str(y["fy"]) for y in self.years]


def _series(data: DataSheet, row: int) -> list[float | None]:
    return [data.val(row, col) for col in data.year_cols]


def _safe_div(n: float | None, d: float | None) -> float | None:
    if n is None or d is None or d == 0:
        return None
    return n / d


def _growth(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return curr / prev - 1


def _iferror_calc(calc: float | None, fallback: float | None) -> float | None:
    return calc if calc is not None else fallback


def extract_market_bar(data: DataSheet) -> dict[str, Any]:
    """Live-style quote strip from 1 DATA PRICE & MULTIPLE block (col 39 = TODAY)."""
    today_col = 39
    price = data.val(15, today_col)
    prev = data.val(15, today_col - 1)
    pe = data.val(16, today_col)
    pb = data.val(17, today_col)

    direction = ""
    if price is not None and prev is not None:
        if price > prev:
            direction = "↑"
        elif price < prev:
            direction = "↓"

    ask = round(price + 0.01, 2) if price is not None else None
    currency = data.currency or "USD"
    fx_label = "US $" if currency == "USD" else currency

    return {
        "price": price,
        "ask": ask,
        "prev": prev,
        "pe": pe,
        "pb": pb,
        "direction": direction,
        "fx_label": fx_label,
    }


def compute_magic_numbers(data: DataSheet) -> dict[str, Any]:
    n = len(data.year_cols)
    tax_rate = data.val(11, 21) or 0.0

    # --- Block 1: How does the company generate cash? ---
    revenue = _series(data, 14)
    cost_of_rev = [(-v) if v is not None else None for v in _series(data, 16)]
    gross_fallback = _series(data, 18)
    total_expenses = [(-v) if v is not None else None for v in _series(data, 20)]
    ebit_fallback = _series(data, 26)
    interest_other = [(-v) if v is not None else None for v in _series(data, 27)]
    interest_exp = _series(data, 28)
    tax_parts = [
        sum(
            x
            for x in [
                data.val(r, col)
                for r in (42, 51, 53, 54)
                for col in [data.year_cols[i]]
            ]
            if x is not None
        )
        for i in range(n)
    ]
    taxes = [(-t) if t else None for t in tax_parts]
    net_income_fallback = _series(data, 50)

    gross_profit: list[float | None] = []
    ebit: list[float | None] = []
    ebt: list[float | None] = []
    net_income: list[float | None] = []

    for i in range(n):
        gp_calc = (
            (revenue[i] + cost_of_rev[i])
            if revenue[i] is not None and cost_of_rev[i] is not None
            else None
        )
        gross_profit.append(_iferror_calc(gp_calc, gross_fallback[i]))

        eb_calc = (
            (total_expenses[i] + gross_profit[i])
            if total_expenses[i] is not None and gross_profit[i] is not None
            else None
        )
        ebit.append(_iferror_calc(eb_calc, ebit_fallback[i]))

        eb = (
            (ebit[i] + interest_other[i])
            if ebit[i] is not None and interest_other[i] is not None
            else None
        )
        ebt.append(eb)

        ni_calc = (ebt[i] + taxes[i]) if ebt[i] is not None and taxes[i] is not None else None
        net_income.append(_iferror_calc(ni_calc, net_income_fallback[i]))

    cfo = _series(data, 209)
    capex = _series(data, 212)
    interest_tax_shield = [
        (ie * (1 - tax_rate / 100)) if ie is not None else None for ie in interest_exp
    ]
    fcff = [
        sum(x for x in (cfo[i], capex[i], interest_tax_shield[i]) if x is not None) or None
        for i in range(n)
    ]
    # Excel SUM(D18:D20) - capex row is stored positive in data, formula uses +E212
    fcff = [
        (cfo[i] or 0) + (capex[i] or 0) + (interest_tax_shield[i] or 0)
        if any(v is not None for v in (cfo[i], capex[i], interest_tax_shield[i]))
        else None
        for i in range(n)
    ]

    eps = _series(data, 62)

    # --- Block 2: Growth ---
    def grow_series(vals: list[float | None]) -> list[float | None]:
        out: list[float | None] = [None]
        for i in range(1, n):
            out.append(_growth(vals[i], vals[i - 1]))
        return out

    growth_revenue = grow_series(revenue)
    growth_net_income = grow_series(net_income)
    growth_eps = grow_series(eps)
    growth_cfo = grow_series(cfo)
    growth_fcff = grow_series(fcff)

    # --- Block 3: Profitability margins ---
    gross_margin = [_safe_div(gross_profit[i], revenue[i]) for i in range(n)]
    ebit_margin = [_safe_div(ebit[i], revenue[i]) for i in range(n)]
    ebt_margin = [_safe_div(ebt[i], revenue[i]) for i in range(n)]
    net_margin = [_safe_div(net_income[i], revenue[i]) for i in range(n)]

    # --- Block 4: Other key ratios ---
    cfo_ni = [_safe_div(cfo[i], net_income[i]) for i in range(n)]
    fcff_ni = [_safe_div(fcff[i], net_income[i]) for i in range(n)]
    capex_cfo = [_safe_div(-(capex[i] or 0), cfo[i]) if capex[i] is not None and cfo[i] else None for i in range(n)]

    total_equity = _series(data, 172)
    total_assets = _series(data, 128)
    equity_assets = [_safe_div(total_equity[i], total_assets[i]) for i in range(n)]
    roe = [_safe_div(net_income[i], total_equity[i]) for i in range(n)]
    bv_growth: list[float | None] = [None]
    bv_growth_abs: list[float | None] = [None]
    for i in range(1, n):
        bv_growth.append(_growth(total_equity[i], total_equity[i - 1]))
        if total_equity[i] is not None and total_equity[i - 1] is not None:
            bv_growth_abs.append(total_equity[i] - total_equity[i - 1])
        else:
            bv_growth_abs.append(None)

    # --- Block 5: Balance sheet key ratios ---
    st_debt = _series(data, 136)
    lt_debt = _series(data, 147)
    total_debt = [
        (st_debt[i] or 0) + (lt_debt[i] or 0)
        if st_debt[i] is not None or lt_debt[i] is not None
        else None
        for i in range(n)
    ]
    debt_ni = [_safe_div(total_debt[i], net_income[i]) for i in range(n)]
    st_debt_pct = [_safe_div(st_debt[i], total_debt[i]) for i in range(n)]
    lt_debt_pct = [_safe_div(lt_debt[i], total_debt[i]) for i in range(n)]

    acquisitions = _series(data, 222)
    acq_ni = [_safe_div(-(acquisitions[i] or 0), fcff[i]) if acquisitions[i] is not None and fcff[i] else None for i in range(n)]
    dividends = _series(data, 231)
    div_fcff = [_safe_div(-(dividends[i] or 0), fcff[i]) if dividends[i] is not None and fcff[i] else None for i in range(n)]
    debt_repay = _series(data, 232)
    repay_fcff = [_safe_div(-(debt_repay[i] or 0), fcff[i]) if debt_repay[i] is not None and fcff[i] else None for i in range(n)]

    # --- Block 6: Balance sheet (absolute) ---
    shares_cap = _series(data, 164)
    treasury = [(-v) if v is not None else None for v in _series(data, 167)]
    retained = _series(data, 168)
    equity_calc = [
        (
            (total_equity[i] - (shares_cap[i] or 0) - (treasury[i] or 0) - (retained[i] or 0))
            if total_equity[i] is not None
            else None
        )
        for i in range(n)
    ]
    cash = _series(data, 99)
    st_invest = _series(data, 100)
    current_assets = _series(data, 113)
    ppe = _series(data, 114)
    goodwill = _series(data, 121)
    intangibles = [
        (data.val(119, col) - data.val(121, col))
        if data.val(119, col) is not None and data.val(121, col) is not None
        else None
        for col in data.year_cols
    ]
    lt_invest = _series(data, 117)
    non_current_assets = _series(data, 127)
    payables = _series(data, 131)
    other_st_liab = _series(data, 142)
    current_liab = _series(data, 146)
    other_lt_liab = _series(data, 152)
    non_current_liab = _series(data, 161)
    total_liabilities = [
        (current_liab[i] or 0) + (non_current_liab[i] or 0)
        if current_liab[i] is not None or non_current_liab[i] is not None
        else None
        for i in range(n)
    ]

    def pct_of_assets(values: list[float | None]) -> list[float | None]:
        return [_safe_div(values[i], total_assets[i]) for i in range(n)]

    other_current_assets = [
        (
            current_assets[i] - (cash[i] or 0) - (st_invest[i] or 0)
            if current_assets[i] is not None
            else None
        )
        for i in range(n)
    ]
    equity_pct = pct_of_assets(total_equity)
    liabilities_pct = pct_of_assets(total_liabilities)
    current_assets_pct = pct_of_assets(current_assets)
    debt_assets_pct = pct_of_assets(total_debt)

    wacc = _series(data, 11)
    shares_outstanding = _series(data, 177)

    years = data.year_labels()

    def block(
        name: str,
        metrics: dict[str, list[float | None]],
        *,
        as_pct: set[str] | None = None,
        as_ratio: set[str] | None = None,
        display: dict[str, Any] | None = None,
    ):
        as_pct = as_pct or set()
        as_ratio = as_ratio or set()

        def metric_format(key: str) -> str:
            if key in as_pct:
                return "percent"
            if key in as_ratio:
                return "ratio"
            return "number"

        return {
            "name": name,
            "years": years,
            "display": display or {},
            "metrics": [
                {
                    "key": key,
                    "label": key,
                    "format": metric_format(key),
                    "bar_group": (display or {}).get("bar_groups", {}).get(key),
                    "values": {years[i]: metrics[key][i] for i in range(n)},
                }
                for key in metrics
            ],
        }

    equity_labels = {
        "Shares Capital + Additional",
        "Treasury Stocks",
        "Retained Earnings",
        "Other Equity",
        "Total Equity",
    }
    assets_labels = {
        "Cash and",
        "Short Term Investments",
        "Total Current Assets",
        "PPE",
        "Goodwill",
        "other Intangibles",
        "LT Investment",
        "Total Non Current Assets",
        "Total Assets",
    }
    debt_labels = {
        "Payables & Accruals",
        "ST Debt",
        "Other ST Liabilities",
        "Total Current Liabilities",
        "LT Debt",
        "other LT Liabilities",
        "Total Non Current Liabilities",
        "Total Liabilties",
        "Total Debt",
    }
    bs_collapsible_groups = [
        {
            "id": "equity",
            "label": "Total Equity",
            "metrics": list(equity_labels),
        },
        {
            "id": "assets",
            "label": "Total Assets",
            "metrics": list(assets_labels),
        },
        {
            "id": "liabilities",
            "label": "Total Liabilities",
            "metrics": list(debt_labels),
        },
    ]

    pct_equity = {"Total Equity"}
    pct_assets = {
        "Cash and",
        "Short Term Investments",
        "Total Current Assets",
        "PPE",
        "Goodwill",
        "other Intangibles",
        "LT Investment",
        "Total Non Current Assets",
    }
    pct_debt = {"Total Debt/Assets"}

    blocks = [
        block(
            "1 How does the company generate cash?",
            {
                "TOTALREVENUE": revenue,
                "COST OF REVENUES": cost_of_rev,
                "GROSS PROFIT": gross_profit,
                "TOTAL EXPENSES": total_expenses,
                "EBIT": ebit,
                "INTEREST& OTHER": interest_other,
                "EBT": ebt,
                "TAXES": taxes,
                "NET INCOME": net_income,
                "CFO": cfo,
                "-CAPEX": capex,
                "INTEREST (1-T)": interest_tax_shield,
                "FCFF": fcff,
            },
            display={"bar_mode": "column", "show_unit": True, "collapsible": True},
        ),
        block(
            "2 Growth",
            {
                "growth REVENUE": growth_revenue,
                "growth NET INCOME": growth_net_income,
                "growth EPS": growth_eps,
                "growth CFO": growth_cfo,
                "growth FCFF": growth_fcff,
            },
            as_pct={
                "growth REVENUE",
                "growth NET INCOME",
                "growth EPS",
                "growth CFO",
                "growth FCFF",
            },
            display={"bar_mode": "row", "show_unit": False, "collapsible": True},
        ),
        block(
            "3 Profitability",
            {
                "GROSS marg": gross_margin,
                "EBIT marg": ebit_margin,
                "EBT marg": ebt_margin,
                "NET margin": net_margin,
            },
            as_pct={"GROSS marg", "EBIT marg", "EBT marg", "NET margin"},
            display={"bar_mode": "row", "show_unit": False, "collapsible": True},
        ),
        block(
            "4 Other key ratios",
            {
                "NET PROFIT MARGIN": net_margin,
                "CFO/NI": cfo_ni,
                "FCFF/NI": fcff_ni,
                "CAPEX/CFO": capex_cfo,
                "EQUITY/ASSETS": equity_assets,
                "ROE": roe,
                "BOOK VALUE Growth": bv_growth,
                "BV growth $$": bv_growth_abs,
            },
            as_pct={"NET PROFIT MARGIN", "EQUITY/ASSETS", "ROE", "BOOK VALUE Growth"},
            display={"bar_mode": "row", "show_unit": False, "collapsible": True, "unit_rows": {"BV growth $$"}},
        ),
        block(
            "5 Balance sheet key ratios",
            {
                "Total Debt / Net Income": debt_ni,
                "ST Debt / Total Debt": st_debt_pct,
                "LT Debt / Total Debt": lt_debt_pct,
                "Adquisition / Net Income": acq_ni,
                "Dividend Paid / FCFF": div_fcff,
                "Repayment Debt/ FCFF": repay_fcff,
            },
            as_pct={"ST Debt / Total Debt", "LT Debt / Total Debt"},
            as_ratio={
                "Total Debt / Net Income",
                "Adquisition / Net Income",
                "Dividend Paid / FCFF",
                "Repayment Debt/ FCFF",
            },
            display={"bar_mode": "row", "show_unit": False, "collapsible": True},
        ),
        block(
            "6 Balance sheet",
            {
                "Shares Capital + Additional": shares_cap,
                "Treasury Stocks": treasury,
                "Retained Earnings": retained,
                "Other Equity": equity_calc,
                "Total Equity": total_equity,
                "Cash and": cash,
                "Short Term Investments": st_invest,
                "Total Current Assets": current_assets,
                "PPE": ppe,
                "Goodwill": goodwill,
                "other Intangibles": intangibles,
                "LT Investment": lt_invest,
                "Total Non Current Assets": non_current_assets,
                "Total Assets": total_assets,
                "Payables & Accruals": payables,
                "ST Debt": st_debt,
                "Other ST Liabilities": other_st_liab,
                "Total Current Liabilities": current_liab,
                "LT Debt": lt_debt,
                "other LT Liabilities": other_lt_liab,
                "Total Non Current Liabilities": non_current_liab,
                "Total Liabilties": total_liabilities,
                "Total Debt": total_debt,
            },
            display={
                "bar_mode": "column",
                "show_unit": True,
                "collapsible": True,
                "collapsible_groups": bs_collapsible_groups,
            },
        ),
        block(
            "6 Balance sheet (% of assets)",
            {
                "Total Equity": pct_of_assets(total_equity),
                "Cash and": pct_of_assets(cash),
                "Short Term Investments": pct_of_assets(st_invest),
                "Total Current Assets": pct_of_assets(current_assets),
                "PPE": pct_of_assets(ppe),
                "Goodwill": pct_of_assets(goodwill),
                "other Intangibles": pct_of_assets(intangibles),
                "LT Investment": pct_of_assets(lt_invest),
                "Total Non Current Assets": pct_of_assets(non_current_assets),
                "Total Debt/Assets": pct_of_assets(total_debt),
            },
            as_pct={
                "Total Equity",
                "Cash and",
                "Short Term Investments",
                "Total Current Assets",
                "PPE",
                "Goodwill",
                "other Intangibles",
                "LT Investment",
                "Total Non Current Assets",
                "Total Debt/Assets",
            },
            display={
                "bar_mode": "column",
                "show_unit": False,
                "collapsible": True,
                "parent_section": 6,
                "collapsible_groups": [
                    {
                        "id": "equity",
                        "label": "Total Equity",
                        "metrics": list(pct_equity),
                    },
                    {
                        "id": "assets",
                        "label": "Total Assets",
                        "metrics": list(pct_assets),
                    },
                    {
                        "id": "liabilities",
                        "label": "Total Liabilities",
                        "metrics": list(pct_debt),
                    },
                ],
            },
        ),
    ]

    chart_payload = build_charts(
        years=years,
        revenue=revenue,
        ebit=ebit,
        net_income=net_income,
        growth_revenue=growth_revenue,
        growth_net_income=growth_net_income,
        growth_eps=growth_eps,
        growth_cfo=growth_cfo,
        growth_fcff=growth_fcff,
        cfo_ni=cfo_ni,
        fcff_ni=fcff_ni,
        capex_cfo=capex_cfo,
        ebit_margin=ebit_margin,
        ebt_margin=ebt_margin,
        net_margin=net_margin,
        wacc=wacc,
        total_equity=total_equity,
        bv_growth=bv_growth,
        equity_pct=equity_pct,
        liabilities_pct=liabilities_pct,
        current_assets_pct=current_assets_pct,
        debt_assets_pct=debt_assets_pct,
        debt_ni=debt_ni,
        st_debt_pct=st_debt_pct,
        lt_debt_pct=lt_debt_pct,
        acq_ni=acq_ni,
        div_fcff=div_fcff,
        repay_fcff=repay_fcff,
        shares_outstanding=shares_outstanding,
        shares_cap=shares_cap,
        treasury=treasury,
        retained=retained,
        equity_calc=equity_calc,
        cash=cash,
        st_invest=st_invest,
        other_current_assets=other_current_assets,
        ppe=ppe,
        goodwill=goodwill,
        intangibles=intangibles,
        lt_invest=lt_invest,
        payables=payables,
        st_debt=st_debt,
        other_st_liab=other_st_liab,
        lt_debt=lt_debt,
        other_lt_liab=other_lt_liab,
    )

    return {
        "ticker": data.ticker,
        "company": data.company,
        "currency": data.currency,
        "units": data.units,
        "tax_rate": tax_rate,
        "source": data.source,
        "source_provider": data.source_provider,
        "market_bar": extract_market_bar(data),
        "blocks": blocks,
        "chart_sections": chart_payload["sections"],
        "charts_missing_data": chart_payload["missing"],
    }


def _series_has_data(data: list[float | None]) -> bool:
    return any(v is not None for v in data)


def _chart(
    chart_id: str,
    title: str,
    chart_type: str,
    series: list[dict[str, Any]],
    *,
    stacked: bool = False,
    dual_axis: bool = False,
    format: str = "number",
    missing: list[str],
) -> dict[str, Any]:
    if not any(_series_has_data(s["data"]) for s in series):
        missing.append(title)
    return {
        "id": chart_id,
        "title": title,
        "type": chart_type,
        "series": series,
        "stacked": stacked,
        "dual_axis": dual_axis,
        "format": format,
    }


def build_charts(**kwargs: Any) -> dict[str, Any]:
    """21 charts in 5 sections — mirrors Excel sheet 3 GRAPHS."""
    missing: list[str] = []
    years: list[str] = kwargs["years"]

    def s(name: str, data: list[float | None], **extra: Any) -> dict[str, Any]:
        return {"name": name, "data": data, **extra}

    sections = [
        {
            "id": "growth",
            "title": "1 GROWTH & FLOWS OF VALUE",
            "charts": [
                _chart(
                    "g1-growth-rev-ni-eps",
                    "Growth Revenue, Net Income, EPS",
                    "line",
                    [
                        s("growth REVENUE", kwargs["growth_revenue"], format="percent"),
                        s("growth NET INCOME", kwargs["growth_net_income"], format="percent"),
                        s("growth EPS", kwargs["growth_eps"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
                _chart(
                    "g2-net-income",
                    "Net Income",
                    "bar",
                    [s("NET INCOME", kwargs["net_income"])],
                    missing=missing,
                ),
                _chart(
                    "g3-growth-cfo-fcff",
                    "Growth CFO, FCFF",
                    "line",
                    [
                        s("growth REVENUE", kwargs["growth_revenue"], format="percent"),
                        s("growth CFO", kwargs["growth_cfo"], format="percent"),
                        s("growth FCFF", kwargs["growth_fcff"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
                _chart(
                    "g4-flows-of-value",
                    "Flows of Value",
                    "line",
                    [
                        s("CFO/NI", kwargs["cfo_ni"], format="ratio"),
                        s("FCFF/NI", kwargs["fcff_ni"], format="ratio"),
                        s("CAPEX/CFO", kwargs["capex_cfo"], format="ratio"),
                    ],
                    format="ratio",
                    missing=missing,
                ),
            ],
        },
        {
            "id": "performance",
            "title": "2 FINANCIAL PERFORMANCE & PROFITABILITY RATIOS",
            "charts": [
                _chart(
                    "f1-revenues-net-income",
                    "Revenues, Net Income",
                    "bar",
                    [
                        s("EBIT", kwargs["ebit"]),
                        s("NET INCOME", kwargs["net_income"]),
                    ],
                    missing=missing,
                ),
                _chart(
                    "f2-profitability",
                    "Profitability",
                    "line",
                    [
                        s("EBIT marg", kwargs["ebit_margin"], format="percent"),
                        s("EBT marg", kwargs["ebt_margin"], format="percent"),
                        s("NET margin", kwargs["net_margin"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
                _chart(
                    "f3-wacc",
                    "WACC",
                    "line",
                    [s("WACC", kwargs["wacc"], format="percent_points")],
                    format="percent_points",
                    missing=missing,
                ),
                _chart(
                    "f4-equity-growth",
                    "Equity $B & growth",
                    "bar",
                    [
                        s("Total Equity", kwargs["total_equity"]),
                        s(
                            "BOOK VALUE Growth",
                            kwargs["bv_growth"],
                            type="line",
                            format="percent",
                            y_axis="y1",
                        ),
                    ],
                    dual_axis=True,
                    missing=missing,
                ),
            ],
        },
        {
            "id": "equity_debt",
            "title": "3 EQUITY & DEBT RATIOS",
            "charts": [
                _chart(
                    "e1-assets",
                    "Assets",
                    "bar",
                    [
                        s("Total Equity", kwargs["equity_pct"], format="percent"),
                        s("Total Liabilties", kwargs["liabilities_pct"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
                _chart(
                    "e2-pct-of-assets",
                    "% of Assets",
                    "line",
                    [
                        s("Total Current Assets", kwargs["current_assets_pct"], format="percent"),
                        s("Total Debt/Assets", kwargs["debt_assets_pct"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
                _chart(
                    "e3-debt-ni",
                    "Total Debt / Net Income",
                    "line",
                    [s("Total Debt / Net Income", kwargs["debt_ni"], format="ratio")],
                    format="ratio",
                    missing=missing,
                ),
                _chart(
                    "e4-lt-st-debt",
                    "LT & ST Debt",
                    "bar",
                    [
                        s("ST Debt / Total Debt", kwargs["st_debt_pct"], format="percent"),
                        s("LT Debt / Total Debt", kwargs["lt_debt_pct"], format="percent"),
                    ],
                    format="percent",
                    missing=missing,
                ),
            ],
        },
        {
            "id": "cash_usage",
            "title": "4 WHAT DOES IT DO WITH CASH?",
            "charts": [
                _chart(
                    "c1-acquisition",
                    "Adquisition / Net Income",
                    "bar",
                    [s("Adquisition / Net Income", kwargs["acq_ni"], format="ratio")],
                    format="ratio",
                    missing=missing,
                ),
                _chart(
                    "c2-repay-debt",
                    "Repayment Debt/ FCFF",
                    "bar",
                    [s("Repayment Debt/ FCFF", kwargs["repay_fcff"], format="ratio")],
                    format="ratio",
                    missing=missing,
                ),
                _chart(
                    "c3-shares",
                    "Shares Outstanding",
                    "line",
                    [s("Shares Outstanding", kwargs["shares_outstanding"])],
                    missing=missing,
                ),
                _chart(
                    "c4-dividends",
                    "Dividend Paid / FCFF",
                    "bar",
                    [s("Dividend Paid / FCFF", kwargs["div_fcff"], format="ratio")],
                    format="ratio",
                    missing=missing,
                ),
            ],
        },
        {
            "id": "balance_sheet",
            "title": "5 BALANCE SHEET (EQUITY, ASSETS, LIABILITIES)",
            "charts": [
                _chart(
                    "b1-total-equity",
                    "Total Equity",
                    "bar",
                    [
                        s("Shares Capital + Additional", kwargs["shares_cap"]),
                        s("Treasury Stocks", kwargs["treasury"]),
                        s("Retained Earnings", kwargs["retained"]),
                        s("Other Equity", kwargs["equity_calc"]),
                    ],
                    stacked=True,
                    missing=missing,
                ),
                _chart(
                    "b2-current-assets",
                    "Total Current Assets",
                    "bar",
                    [
                        s("Cash and", kwargs["cash"]),
                        s("Short Term Investments", kwargs["st_invest"]),
                        s("Other current assets", kwargs["other_current_assets"]),
                    ],
                    stacked=True,
                    missing=missing,
                ),
                _chart(
                    "b3-non-current-assets",
                    "Total Non Current Assets",
                    "bar",
                    [
                        s("PPE", kwargs["ppe"]),
                        s("Goodwill", kwargs["goodwill"]),
                        s("other Intangibles", kwargs["intangibles"]),
                        s("LT Investment", kwargs["lt_invest"]),
                    ],
                    stacked=True,
                    missing=missing,
                ),
                _chart(
                    "b4-current-liabilities",
                    "Current Liabilities",
                    "bar",
                    [
                        s("Payables & Accruals", kwargs["payables"]),
                        s("ST Debt", kwargs["st_debt"]),
                        s("Other ST Liabilities", kwargs["other_st_liab"]),
                    ],
                    stacked=True,
                    missing=missing,
                ),
                _chart(
                    "b5-non-current-liabilities",
                    "Non Current Liabilities",
                    "bar",
                    [
                        s("LT Debt", kwargs["lt_debt"]),
                        s("other LT Liabilities", kwargs["other_lt_liab"]),
                    ],
                    stacked=True,
                    missing=missing,
                ),
            ],
        },
    ]

    return {"sections": sections, "missing": missing, "years": years}


def load_preloaded(ticker: str = "MSFT") -> dict[str, Any]:
    path = DEFAULT_DATA_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = DataSheet(payload)
    result = compute_magic_numbers(data)
    result["ticker"] = ticker
    return result
