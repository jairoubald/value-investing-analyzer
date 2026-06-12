"""Method Valuation — DCF (Excel sheet 4 METHOD VALUATION, Method 1)."""

from __future__ import annotations

from typing import Any

from services.magic_numbers import DataSheet, _growth, _safe_div, _series

DEFAULT_WACC = 0.09
DEFAULT_TERMINAL_G = 0.035
FORECAST_YEARS = 7
PE_EPS_HISTORY_YEARS = 10
PE_EPS_FORECAST_YEARS = 5
FLOW_HISTORY_YEARS = 4
DEFAULT_PERCENTILE = 50
MULT_HIST_COL_START = 27
MULT_HIST_COL_END = 38
TODAY_COL = 39


def _percentile_interp_sorted(xs: list[float], p: float) -> float:
    frac = p / 100.0
    k = (len(xs) - 1) * frac
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def percentile_value(values: list[float | None], p: float) -> float | None:
    """Map percentile to value; p may exceed 0–100 (linear extrapolation from P75–P100 / P0–P25)."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]

    if 0 <= p <= 100:
        return _percentile_interp_sorted(xs, p)

    v0 = _percentile_interp_sorted(xs, 0)
    v25 = _percentile_interp_sorted(xs, 25)
    v75 = _percentile_interp_sorted(xs, 75)
    v100 = _percentile_interp_sorted(xs, 100)

    if p > 100:
        slope = (v100 - v75) / 25
        if abs(slope) < 1e-12:
            return v100
        return v100 + slope * (p - 100)

    slope_low = (v25 - v0) / 25
    if abs(slope_low) < 1e-12:
        return v0
    return v0 + slope_low * p


def _dcf_from_fcff(
    forecast_fcff: list[float],
    *,
    wacc: float,
    terminal_g: float,
    cash_mln: float,
    debt_mln: float,
    shares_mln: float,
) -> dict[str, Any] | None:
    if wacc <= terminal_g or shares_mln <= 0 or not forecast_fcff:
        return None

    n = len(forecast_fcff)
    discount_rows: list[dict[str, Any]] = []
    pv_fcff_sum = 0.0

    for i, fcff in enumerate(forecast_fcff):
        year_n = i + 1
        factor = (1 + wacc) ** year_n
        pv = fcff / factor
        pv_fcff_sum += pv
        discount_rows.append(
            {
                "year_n": year_n,
                "fcff_mln": fcff,
                "discount_factor": factor,
                "pv_fcff_mln": pv,
            }
        )

    last_fcff = forecast_fcff[-1]
    terminal_value = last_fcff * (1 + terminal_g) / (wacc - terminal_g)
    pv_terminal = terminal_value / ((1 + wacc) ** n)
    enterprise_value = pv_fcff_sum + pv_terminal
    equity_value = enterprise_value + cash_mln + debt_mln
    price_per_share = equity_value / shares_mln

    return {
        "wacc": wacc,
        "terminal_g": terminal_g,
        "discount_rows": discount_rows,
        "terminal_value_mln": terminal_value,
        "pv_terminal_mln": pv_terminal,
        "pv_fcff_sum_mln": pv_fcff_sum,
        "enterprise_value_mln": enterprise_value,
        "equity_value_mln": equity_value,
        "price_per_share": price_per_share,
    }


def _project_flows(
    *,
    first_forecast_rev: float,
    revenue_growth: float,
    net_margin: float,
    cfo_to_ni: float,
    capex_to_cfo: float,
    base_year: int,
    years: int = FORECAST_YEARS,
) -> dict[str, Any]:
    forecast_years = [f"FY {base_year + i}" for i in range(1, years + 1)]
    forecast_rev: list[float] = []
    forecast_ni: list[float] = []
    forecast_fcff: list[float] = []

    rev = first_forecast_rev
    for _ in range(years):
        ni = rev * net_margin
        cfo_v = ni * cfo_to_ni
        cap = -cfo_v * capex_to_cfo
        fcff_v = cfo_v + cap
        forecast_rev.append(rev)
        forecast_ni.append(ni)
        forecast_fcff.append(fcff_v)
        rev = rev * (1 + revenue_growth)

    return {
        "years": forecast_years,
        "revenue_mln": forecast_rev,
        "net_income_mln": forecast_ni,
        "fcff_mln": forecast_fcff,
    }


def _fundamentals(data: DataSheet) -> dict[str, Any] | None:
    n = len(data.year_cols)
    if n < 2:
        return None

    tax_rate = data.val(11, 21) or 0.0
    revenue = _series(data, 14)
    cfo = _series(data, 209)
    capex = _series(data, 212)
    interest_exp = _series(data, 28)
    net_income_fb = _series(data, 50)

    cost_of_rev = [(-v) if v is not None else None for v in _series(data, 16)]
    total_expenses = [(-v) if v is not None else None for v in _series(data, 20)]
    gross_fb = _series(data, 18)
    ebit_fb = _series(data, 26)

    net_income: list[float | None] = []
    for i in range(n):
        gp = (
            (revenue[i] + cost_of_rev[i])
            if revenue[i] is not None and cost_of_rev[i] is not None
            else None
        )
        gp = gp if gp is not None else gross_fb[i]
        ebit = (
            (total_expenses[i] + gp)
            if total_expenses[i] is not None and gp is not None
            else None
        )
        ebit = ebit if ebit is not None else ebit_fb[i]
        net_income.append(net_income_fb[i])

    interest_tax_shield = [
        (ie * (1 - tax_rate / 100)) if ie is not None else None for ie in interest_exp
    ]
    fcff_hist = [
        sum(x for x in (cfo[i], capex[i], interest_tax_shield[i]) if x is not None) or None
        for i in range(n)
    ]

    growth_revenue: list[float | None] = [None]
    for i in range(1, n):
        growth_revenue.append(_growth(revenue[i], revenue[i - 1]))

    net_margin = [_safe_div(net_income[i], revenue[i]) for i in range(n)]
    cfo_ni = [_safe_div(cfo[i], net_income[i]) for i in range(n)]
    capex_cfo = [
        _safe_div(-(capex[i] or 0), cfo[i]) if capex[i] is not None and cfo[i] else None
        for i in range(n)
    ]

    hist_slice = slice(1, n)
    equity = _series(data, 172)
    bv_growth: list[float | None] = [None]
    for i in range(1, n):
        bv_growth.append(_growth(equity[i], equity[i - 1]))

    percentile_history = {
        "revenue_growth": [v for v in growth_revenue[hist_slice] if v is not None],
        "net_margin": [v for v in net_margin[hist_slice] if v is not None],
        "cfo_to_ni": [v for v in cfo_ni[hist_slice] if v is not None],
        "capex_to_cfo": [v for v in capex_cfo[hist_slice] if v is not None],
        "bv_growth": [v for v in bv_growth[hist_slice] if v is not None],
    }

    last_col = data.year_cols[-1]
    try:
        base_year = int(str(data.year_labels()[-1]).replace("FY ", "").strip())
    except ValueError:
        base_year = 2023

    hist_count = min(FLOW_HISTORY_YEARS, n)
    hist_start = n - hist_count
    actual_years = [data.year_labels()[i] for i in range(hist_start, n)]

    cash = data.val(99, last_col) or 0.0
    st_inv = data.val(100, last_col) or 0.0
    st_debt = data.val(136, last_col) or 0.0
    lt_debt = data.val(147, last_col) or 0.0
    shares_177 = data.val(177, last_col)
    shares_11 = data.val(11, 20)
    shares_mln = max(shares_177 or 0, shares_11 or 0) or shares_177 or 0.0

    return {
        "n": n,
        "revenue": revenue,
        "net_income": net_income,
        "fcff_hist": fcff_hist,
        "percentile_history": percentile_history,
        "base_year": base_year,
        "actual_years": actual_years,
        "actual_revenue_mln": [revenue[i] for i in range(hist_start, n)],
        "actual_net_income_mln": [net_income[i] for i in range(hist_start, n)],
        "actual_fcff_mln": [fcff_hist[i] for i in range(hist_start, n)],
        "first_forecast_rev_mln": data.val(11, 19),
        "last_revenue_mln": revenue[-1],
        "cash_mln": cash + st_inv,
        "debt_mln": -(st_debt + lt_debt),
        "shares_mln": shares_mln,
        "net_income_series": net_income,
        "equity_series": equity,
        "year_labels": data.year_labels(),
    }


def assumptions_from_percentiles(
    fund: dict[str, Any],
    *,
    revenue_growth_p: float = DEFAULT_PERCENTILE,
    net_margin_p: float = DEFAULT_PERCENTILE,
    cfo_to_ni_p: float = DEFAULT_PERCENTILE,
    capex_to_cfo_p: float = DEFAULT_PERCENTILE,
    wacc: float = DEFAULT_WACC,
    terminal_g: float = DEFAULT_TERMINAL_G,
) -> dict[str, Any]:
    hist = fund["percentile_history"]
    return {
        "revenue_growth": percentile_value(hist["revenue_growth"], revenue_growth_p),
        "net_margin": percentile_value(hist["net_margin"], net_margin_p),
        "cfo_to_ni": percentile_value(hist["cfo_to_ni"], cfo_to_ni_p),
        "capex_to_cfo": percentile_value(hist["capex_to_cfo"], capex_to_cfo_p),
        "revenue_growth_p": revenue_growth_p,
        "net_margin_p": net_margin_p,
        "cfo_to_ni_p": cfo_to_ni_p,
        "capex_to_cfo_p": capex_to_cfo_p,
        "wacc": wacc,
        "terminal_g": terminal_g,
    }


def run_dcf_model(
    fund: dict[str, Any],
    assumptions: dict[str, Any],
) -> dict[str, Any] | None:
    rev_g = assumptions.get("revenue_growth")
    margin = assumptions.get("net_margin")
    cfo_ni_r = assumptions.get("cfo_to_ni")
    capex_cfo_r = assumptions.get("capex_to_cfo")
    wacc = assumptions.get("wacc", DEFAULT_WACC)
    terminal_g = assumptions.get("terminal_g", DEFAULT_TERMINAL_G)

    if any(v is None for v in (rev_g, margin, cfo_ni_r, capex_cfo_r)):
        return None

    first_rev = fund.get("first_forecast_rev_mln")
    if first_rev is None and fund.get("last_revenue_mln") is not None:
        first_rev = fund["last_revenue_mln"] * (1 + rev_g)  # type: ignore[operator]

    if first_rev is None:
        return None

    forecast = _project_flows(
        first_forecast_rev=first_rev,
        revenue_growth=rev_g,  # type: ignore[arg-type]
        net_margin=margin,  # type: ignore[arg-type]
        cfo_to_ni=cfo_ni_r,  # type: ignore[arg-type]
        capex_to_cfo=capex_cfo_r,  # type: ignore[arg-type]
        base_year=fund["base_year"],
    )

    result = _dcf_from_fcff(
        forecast["fcff_mln"],
        wacc=wacc,
        terminal_g=terminal_g,
        cash_mln=fund["cash_mln"],
        debt_mln=fund["debt_mln"],
        shares_mln=fund["shares_mln"],
    )
    if result is None:
        return None

    return {
        "assumptions": assumptions,
        "forecast": forecast,
        "result": result,
        "actual": {
            "years": fund["actual_years"],
            "revenue_mln": fund["actual_revenue_mln"],
            "net_income_mln": fund["actual_net_income_mln"],
            "fcff_mln": fund["actual_fcff_mln"],
            "count": len(fund["actual_years"]),
        },
    }


def compute_dcf_valuation(
    data: DataSheet,
    *,
    wacc: float = DEFAULT_WACC,
    terminal_g: float = DEFAULT_TERMINAL_G,
) -> dict[str, Any]:
    fund = _fundamentals(data)
    if fund is None:
        return {"method": "dcf", "error": "Need at least two fiscal years of history."}

    assumptions = assumptions_from_percentiles(fund, wacc=wacc, terminal_g=terminal_g)
    model = run_dcf_model(fund, assumptions)
    if model is None:
        return {
            "method": "dcf",
            "error": "Cannot run DCF with available history.",
            "assumptions": assumptions,
        }

    controls = [
        {
            "id": "revenue_growth",
            "label": "Revenue growth",
            "format": "percent",
            "default_percentile": DEFAULT_PERCENTILE,
            "history": fund["percentile_history"]["revenue_growth"],
        },
        {
            "id": "net_margin",
            "label": "Net margin",
            "format": "percent",
            "default_percentile": DEFAULT_PERCENTILE,
            "history": fund["percentile_history"]["net_margin"],
        },
        {
            "id": "cfo_to_ni",
            "label": "CFO / Net income",
            "format": "ratio",
            "default_percentile": DEFAULT_PERCENTILE,
            "history": fund["percentile_history"]["cfo_to_ni"],
        },
        {
            "id": "capex_to_cfo",
            "label": "CapEx / CFO",
            "format": "percent",
            "default_percentile": DEFAULT_PERCENTILE,
            "history": fund["percentile_history"]["capex_to_cfo"],
        },
        {
            "id": "wacc",
            "label": "WACC",
            "format": "percent_points",
            "default_value": DEFAULT_WACC,
            "min": 0.05,
            "max": 0.18,
        },
    ]

    return {
        "method": "dcf",
        "scenario": "interactive",
        "controls": controls,
        "engine": {
            "terminal_g": terminal_g,
            "forecast_years": FORECAST_YEARS,
            "first_forecast_rev_mln": fund["first_forecast_rev_mln"],
            "last_revenue_mln": fund["last_revenue_mln"],
            "percentile_history": fund["percentile_history"],
            "cash_mln": fund["cash_mln"],
            "debt_mln": fund["debt_mln"],
            "shares_mln": fund["shares_mln"],
            "base_year": fund["base_year"],
            "actual_years": fund["actual_years"],
            "actual_revenue_mln": fund["actual_revenue_mln"],
            "actual_net_income_mln": fund["actual_net_income_mln"],
            "actual_fcff_mln": fund["actual_fcff_mln"],
        },
        "assumptions": model["assumptions"],
        "actual": model["actual"],
        "forecast": model["forecast"],
        "bridge": {
            "cash_mln": fund["cash_mln"],
            "debt_mln": fund["debt_mln"],
            "shares_mln": fund["shares_mln"],
        },
        "result": model["result"],
    }


def _multiples_history(data: DataSheet, row: int) -> list[float | None]:
    return [data.val(row, col) for col in range(MULT_HIST_COL_START, MULT_HIST_COL_END + 1)]


def _pe_history_values(data: DataSheet) -> list[float]:
    ms = data.multiples_series or {}
    pe_block = ms.get("pe") or {}
    computed = pe_block.get("history_values") or []
    if computed:
        return [float(v) for v in computed if v is not None]
    return [v for v in _multiples_history(data, 16) if v is not None]


def _pbv_history_values(data: DataSheet) -> list[float]:
    ms = data.multiples_series or {}
    pb_block = ms.get("pbv") or {}
    computed = pb_block.get("history_values") or []
    if computed:
        return [float(v) for v in computed if v is not None]
    return [v for v in _multiples_history(data, 17) if v is not None]


def _default_forecast(fund: dict[str, Any]) -> dict[str, Any] | None:
    assumptions = assumptions_from_percentiles(fund)
    rev_g = assumptions.get("revenue_growth")
    margin = assumptions.get("net_margin")
    cfo_ni_r = assumptions.get("cfo_to_ni")
    capex_cfo_r = assumptions.get("capex_to_cfo")
    if any(v is None for v in (rev_g, margin, cfo_ni_r, capex_cfo_r)):
        return None

    first_rev = fund.get("first_forecast_rev_mln")
    if first_rev is None and fund.get("last_revenue_mln") is not None:
        first_rev = fund["last_revenue_mln"] * (1 + rev_g)  # type: ignore[operator]
    if first_rev is None:
        return None

    forecast = _project_flows(
        first_forecast_rev=first_rev,
        revenue_growth=rev_g,  # type: ignore[arg-type]
        net_margin=margin,  # type: ignore[arg-type]
        cfo_to_ni=cfo_ni_r,  # type: ignore[arg-type]
        capex_to_cfo=capex_cfo_r,  # type: ignore[arg-type]
        base_year=fund["base_year"],
    )
    return {"assumptions": assumptions, "forecast": forecast}


def _project_book_value(last_bv: float, growth: float, years: int = FORECAST_YEARS) -> list[float]:
    values: list[float] = []
    bv = last_bv
    for _ in range(years):
        bv *= 1 + growth
        values.append(bv)
    return values


def compute_pe_valuation(
    data: DataSheet,
    *,
    pe_percentile: float = DEFAULT_PERCENTILE,
    fund: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fund = fund or _fundamentals(data)
    if fund is None:
        return {"method": "pe", "error": "Need at least two fiscal years of history."}

    pe_hist = _pe_history_values(data)
    if not pe_hist:
        err = data.multiples_series_error or "No historical P/E series (need FMP multiples build)."
        return {"method": "pe", "error": err}

    bundle = _default_forecast(fund)
    if bundle is None:
        return {"method": "pe", "error": "Cannot build earnings forecast for P/E valuation."}

    forecast = bundle["forecast"]
    assumptions = bundle["assumptions"]
    selected_pe = percentile_value(pe_hist, pe_percentile)
    if selected_pe is None:
        return {"method": "pe", "error": "Cannot resolve P/E at selected percentile."}

    shares = fund["shares_mln"]
    if not shares:
        return {"method": "pe", "error": "Shares outstanding missing."}

    ms_pe = (data.multiples_series or {}).get("pe") or {}
    pe_points = ms_pe.get("points") or []

    eps_ttm: float | None = None
    if pe_points:
        eps_ttm = pe_points[-1].get("eps_ttm")
    if eps_ttm is None:
        last_ni = next((v for v in reversed(fund["net_income_series"]) if v is not None), None)
        if last_ni is not None and shares:
            eps_ttm = last_ni / shares

    if eps_ttm is None or eps_ttm <= 0:
        return {"method": "pe", "error": "Trailing EPS unavailable for P/E valuation."}

    price_per_share = selected_pe * eps_ttm
    forecast_prices = [price_per_share for _ in forecast["net_income_mln"]]

    pe_bands = {
        "p20": percentile_value(pe_hist, 20),
        "p50": percentile_value(pe_hist, 50),
        "p80": percentile_value(pe_hist, 80),
    }

    year_labels = fund["year_labels"]
    if pe_points:
        hist_pe_pairs = [(p["month"], p["pe"]) for p in pe_points[-12:]]
    else:
        pe_hist_all = _multiples_history(data, 16)
        hist_pe_pairs = [
            (year_labels[i], pe_hist_all[i])
            for i in range(min(len(year_labels), len(pe_hist_all)))
            if pe_hist_all[i] is not None
        ]

    ni_series = fund["net_income_series"]
    annual_eps = [
        (ni / shares) if ni is not None and shares else None for ni in ni_series
    ]
    eps_history = annual_eps[-PE_EPS_HISTORY_YEARS:]
    eps_history_years = year_labels[-PE_EPS_HISTORY_YEARS:]
    fc_ni = forecast["net_income_mln"][:PE_EPS_FORECAST_YEARS]
    fc_years = forecast["years"][:PE_EPS_FORECAST_YEARS]
    eps_forecast = [(ni / shares) if ni is not None and shares else None for ni in fc_ni]

    return {
        "method": "pe",
        "scenario": "interactive",
        "controls": [
            {
                "id": "pe_multiple",
                "label": "P/E multiple",
                "format": "ratio",
                "default_percentile": DEFAULT_PERCENTILE,
                "history": pe_hist,
            },
        ],
        "engine": {
            "forecast_years": FORECAST_YEARS,
            "shares_mln": shares,
            "base_year": fund["base_year"],
            "history_years": [p[0] for p in hist_pe_pairs],
            "history_pe": [p[1] for p in hist_pe_pairs],
            "monthly_pe_points": pe_points,
            "eps_ttm": eps_ttm,
            "pe_bands": pe_bands,
            "multiples_meta": {
                "source": ms_pe.get("method"),
                "frequency": ms_pe.get("frequency"),
                "validation": ms_pe.get("validation"),
                "source_note": ms_pe.get("source_note"),
            },
            "earnings_history_years": year_labels,
            "earnings_history_mln": fund["net_income_series"],
            "forecast_years_labels": forecast["years"],
            "forecast_earnings_mln": forecast["net_income_mln"],
            "forecast_assumptions": assumptions,
            "eps_history_years": eps_history_years,
            "eps_history": eps_history,
            "eps_forecast_years": fc_years,
            "eps_forecast": eps_forecast,
        },
        "assumptions": {
            "pe_multiple": selected_pe,
            "pe_multiple_p": pe_percentile,
        },
        "result": {
            "price_per_share": price_per_share,
            "selected_pe": selected_pe,
            "eps_ttm": eps_ttm,
            "forecast_prices": forecast_prices,
        },
    }


def compute_pbv_valuation(
    data: DataSheet,
    *,
    pb_percentile: float = DEFAULT_PERCENTILE,
    bv_growth_percentile: float = DEFAULT_PERCENTILE,
    fund: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fund = fund or _fundamentals(data)
    if fund is None:
        return {"method": "pbv", "error": "Need at least two fiscal years of history."}

    pb_hist = _pbv_history_values(data)
    if not pb_hist:
        err = data.multiples_series_error or "No historical P/BV series (need FMP multiples build)."
        return {"method": "pbv", "error": err}

    equity = fund["equity_series"]
    last_bv = next((v for v in reversed(equity) if v is not None), None)
    if last_bv is None:
        return {"method": "pbv", "error": "Book value history missing."}

    bv_growth = percentile_value(fund["percentile_history"]["bv_growth"], bv_growth_percentile)
    if bv_growth is None:
        return {"method": "pbv", "error": "Cannot resolve book-value growth percentile."}

    selected_pb = percentile_value(pb_hist, pb_percentile)
    if selected_pb is None:
        return {"method": "pbv", "error": "Cannot resolve P/BV at selected percentile."}

    shares = fund["shares_mln"]
    if not shares:
        return {"method": "pbv", "error": "Shares outstanding missing."}

    ms_pbv = (data.multiples_series or {}).get("pbv") or {}
    pbv_points = ms_pbv.get("points") or []
    year_labels = fund["year_labels"]
    base_year = fund["base_year"]

    forecast_bv = _project_book_value(last_bv, bv_growth)
    forecast_years = [f"FY {base_year + i}" for i in range(1, FORECAST_YEARS + 1)]

    pbv_bands = {
        "p20": percentile_value(pb_hist, 20),
        "p50": percentile_value(pb_hist, 50),
        "p80": percentile_value(pb_hist, 80),
    }

    bvps_ttm: float | None = None
    if pbv_points:
        bvps_ttm = pbv_points[-1].get("book_value_per_share")
    if bvps_ttm is None and last_bv is not None and shares:
        bvps_ttm = last_bv / shares

    if bvps_ttm is None or bvps_ttm <= 0:
        return {"method": "pbv", "error": "Book value per share unavailable for P/BV valuation."}

    price_per_share = selected_pb * bvps_ttm
    fc_bv = forecast_bv[:PE_EPS_FORECAST_YEARS]
    fc_years = forecast_years[:PE_EPS_FORECAST_YEARS]
    forecast_prices = [selected_pb * (bv / shares) for bv in fc_bv]

    annual_bvps = [
        (eq / shares) if eq is not None and shares else None for eq in equity
    ]
    bvps_history = annual_bvps[-PE_EPS_HISTORY_YEARS:]
    bvps_history_years = year_labels[-PE_EPS_HISTORY_YEARS:]
    bvps_forecast = [(bv / shares) if shares else None for bv in fc_bv]

    if pbv_points:
        hist_pb_pairs = [(p["month"], p["pbv"]) for p in pbv_points[-12:]]
    else:
        pb_hist_all = _multiples_history(data, 17)
        hist_pb_pairs = [
            (year_labels[i], pb_hist_all[i])
            for i in range(min(len(year_labels), len(pb_hist_all)))
            if pb_hist_all[i] is not None
        ]

    return {
        "method": "pbv",
        "scenario": "interactive",
        "controls": [
            {
                "id": "pbv_multiple",
                "label": "P/BV multiple",
                "format": "ratio",
                "default_percentile": DEFAULT_PERCENTILE,
                "history": pb_hist,
            },
        ],
        "engine": {
            "forecast_years": FORECAST_YEARS,
            "shares_mln": shares,
            "base_year": base_year,
            "history_years": [p[0] for p in hist_pb_pairs],
            "history_pbv": [p[1] for p in hist_pb_pairs],
            "monthly_pbv_points": pbv_points,
            "pbv_bands": pbv_bands,
            "bvps_ttm": bvps_ttm,
            "bvps_history_years": bvps_history_years,
            "bvps_history": bvps_history,
            "bvps_forecast_years": fc_years,
            "bvps_forecast": bvps_forecast,
            "multiples_meta": {
                "source": ms_pbv.get("method"),
                "frequency": ms_pbv.get("frequency"),
                "source_note": ms_pbv.get("source_note"),
            },
            "bv_history_years": year_labels,
            "bv_history_mln": equity,
            "forecast_years_labels": forecast_years,
            "forecast_bv_mln": forecast_bv,
            "bv_growth": bv_growth,
            "bv_growth_p": bv_growth_percentile,
        },
        "assumptions": {
            "pbv_multiple": selected_pb,
            "pbv_multiple_p": pb_percentile,
        },
        "result": {
            "price_per_share": price_per_share,
            "selected_pbv": selected_pb,
            "bvps_ttm": bvps_ttm,
            "forecast_prices": forecast_prices,
        },
    }


def _consensus_price_at_percentile(consensus: dict[str, Any], percentile: float) -> float:
    """Linear position between analyst low and high (0 = low, 100 = high)."""
    low = float(consensus["low"])
    high = float(consensus["high"])
    p = max(0.0, min(100.0, percentile))
    return low + (high - low) * (p / 100.0)


def _consensus_anchor_labels(consensus: dict[str, Any]) -> dict[str, float]:
    return {
        "low": float(consensus["low"]),
        "median": float(consensus["median"]),
        "mean": float(consensus["mean"]),
        "high": float(consensus["high"]),
    }


def compute_consensus_valuation(
    data: DataSheet,
    *,
    consensus_percentile: float = DEFAULT_PERCENTILE,
) -> dict[str, Any]:
    raw = data.analyst_consensus or {}
    if raw.get("error"):
        err = raw["error"]
        if data.analyst_consensus_error:
            err = f"{err} ({data.analyst_consensus_error})"
        return {"method": "consensus", "error": err}

    if not raw.get("low") or not raw.get("high"):
        err = data.analyst_consensus_error or "Analyst consensus unavailable."
        return {"method": "consensus", "error": err}

    anchors = _consensus_anchor_labels(raw)
    selected = float(anchors["median"])

    return {
        "method": "consensus",
        "scenario": "interactive",
        "controls": [],
        "engine": {
            **raw,
            "anchors": anchors,
            "disclaimer": (
                "Analyst price targets reflect where covering sell-side analysts expect the "
                "share price to trade over approximately the next 12 months. They are not an "
                "intrinsic or fair-value estimate for today."
            ),
        },
        "assumptions": {},
        "result": {
            "price_per_share": round(selected, 2),
            "reference_price": round(selected, 2),
            "anchors": anchors,
        },
    }


def compute_valuation_bundle(data: DataSheet) -> dict[str, Any]:
    fund = _fundamentals(data)
    return {
        "dcf": compute_dcf_valuation(data),
        "pe": compute_pe_valuation(data, fund=fund),
        "pbv": compute_pbv_valuation(data, fund=fund),
        "consensus": compute_consensus_valuation(data),
    }
