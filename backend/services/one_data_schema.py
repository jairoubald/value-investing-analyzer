"""Canonical 1 DATA row contract (Excel-aligned).

Each row is what ``magic_numbers.DataSheet`` reads. Values are stored in MLN
(millions) for dollar amounts unless noted. Fiscal years map to Excel columns
5–16 (12 years, oldest → newest).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

YEAR_COL_START = 5
YEAR_COL_COUNT = 12  # Excel layout; actual periods may be fewer on FMP free tier (5)
UNITS = "MLN"

# Row numbers referenced by magic_numbers.py (and WACC row 11 cols 5–16 optional).
ENGINE_ROWS = (
    11, 14, 16, 18, 20, 26, 27, 28, 42, 50, 51, 53, 54, 62,
    99, 100, 113, 114, 117, 119, 121, 127, 128, 131, 136, 142, 146, 147, 152, 161,
    164, 167, 168, 172, 177, 209, 212, 222, 231, 232,
)

RowKind = Literal["money_mln", "ratio", "eps", "shares_mln", "percent_points", "meta"]


@dataclass(frozen=True)
class RowSpec:
    row: int
    label: str
    kind: RowKind
    fmp_source: str  # dotted path hint for docs / mapper


# Primary homologation targets — FMP field → Excel row
ROW_SPECS: tuple[RowSpec, ...] = (
    RowSpec(14, "Revenue", "money_mln", "income.revenue"),
    RowSpec(16, "Cost of Revenue", "money_mln", "income.costOfRevenue"),
    RowSpec(18, "Gross Profit", "money_mln", "income.grossProfit"),
    RowSpec(20, "Operating Expenses", "money_mln", "income.operatingExpenses"),
    RowSpec(26, "Operating Income (Loss)", "money_mln", "income.operatingIncome"),
    RowSpec(27, "Non-Operating (Income) Loss", "money_mln", "income.totalOtherIncomeExpensesNet"),
    RowSpec(28, "Interest Expense", "money_mln", "income.interestExpense"),
    RowSpec(50, "Income (Loss) Incl. MI", "money_mln", "income.netIncome"),
    RowSpec(62, "Basic EPS, GAAP", "eps", "income.eps"),
    RowSpec(99, "Cash & Cash Equivalents", "money_mln", "balance.cashAndCashEquivalents"),
    RowSpec(100, "ST Investments", "money_mln", "balance.shortTermInvestments"),
    RowSpec(113, "Total Current Assets", "money_mln", "balance.totalCurrentAssets"),
    RowSpec(114, "Property, Plant & Equip, Net", "money_mln", "balance.propertyPlantEquipmentNet"),
    RowSpec(117, "LT Investments & Receivables", "money_mln", "balance.longTermInvestments"),
    RowSpec(119, "Other LT Assets", "money_mln", "balance.otherNonCurrentAssets"),
    RowSpec(121, "Goodwill", "money_mln", "balance.goodwill"),
    RowSpec(127, "Total Noncurrent Assets", "money_mln", "balance.totalNonCurrentAssets"),
    RowSpec(128, "Total Assets", "money_mln", "balance.totalAssets"),
    RowSpec(131, "Payables & Accruals", "money_mln", "balance.accountPayables"),  # + accrued when present
    RowSpec(136, "ST Debt", "money_mln", "balance.shortTermDebt"),
    RowSpec(142, "Other ST Liabilities", "money_mln", "derived.otherStLiabilities"),
    RowSpec(146, "Total Current Liabilities", "money_mln", "balance.totalCurrentLiabilities"),
    RowSpec(147, "LT Debt", "money_mln", "balance.longTermDebt"),
    RowSpec(152, "Other LT Liabilities", "money_mln", "balance.otherNonCurrentLiabilities"),
    RowSpec(161, "Total Noncurrent Liabilities", "money_mln", "balance.totalNonCurrentLiabilities"),
    RowSpec(164, "Share Capital & APIC", "money_mln", "derived.shareCapitalApic"),
    RowSpec(167, "Treasury Stock", "money_mln", "balance.treasuryStock"),
    RowSpec(168, "Retained Earnings", "money_mln", "balance.retainedEarnings"),
    RowSpec(172, "Total Equity", "money_mln", "balance.totalStockholdersEquity"),
    RowSpec(177, "Shares Outstanding", "shares_mln", "income.weightedAverageShsOut"),
    RowSpec(209, "Cash from Operating Activities", "money_mln", "cashflow.operatingCashFlow"),
    RowSpec(212, "Change in Fixed & Intang", "money_mln", "cashflow.capitalExpenditure"),
    RowSpec(222, "Net Cash From Acq & Div", "money_mln", "cashflow.acquisitionsNet"),
    RowSpec(231, "Dividends Paid", "money_mln", "cashflow.dividendsPaid"),
    RowSpec(232, "Cash From (Repayment) Debt", "money_mln", "cashflow.debtRepayment"),
)

ROW_BY_NUMBER = {s.row: s for s in ROW_SPECS}
