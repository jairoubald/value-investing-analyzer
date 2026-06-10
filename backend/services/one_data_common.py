"""Shared helpers for all 1 DATA normalizers (FMP, EDGAR, Excel)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_mln(v: Any) -> float | None:
    x = to_float(v)
    if x is None:
        return None
    return x / 1_000_000.0


def to_shares_mln(v: Any) -> float | None:
    x = to_float(v)
    if x is None:
        return None
    if abs(x) > 1_000_000:
        return x / 1_000_000.0
    return x


def fy_label(calendar_year: Any, date_str: str) -> str:
    if calendar_year is not None:
        return f"FY {calendar_year}"
    return f"FY {date_str[:4]}"


def end_date_fmt(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y")
    except ValueError:
        return date_str


def pct_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return abs(b - a) / abs(a) * 100.0
