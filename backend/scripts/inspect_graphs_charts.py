"""Extract clean chart titles and series refs from 3 GRAPHS."""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

PATH = Path(
    r"c:\Users\HOME\Desktop\4 - FUND JAIRO\2. ASSETS\2.1 THESIS\0. THESIS TOOL\FINANCIAL TOOL.xlsx"
)


def chart_title(ch) -> str:
    try:
        t = ch.title
        if t and t.tx and t.tx.rich and t.tx.rich.p:
            parts = []
            for p in t.tx.rich.p:
                for r in p.r or []:
                    if hasattr(r, "t") and r.t:
                        parts.append(str(r.t))
            return "".join(parts).strip()
    except Exception:
        pass
    return "?"


def series_info(ch) -> list[str]:
    out = []
    for s in ch.series:
        name = "?"
        try:
            if s.title and s.title.strRef and s.title.strRef.strCache:
                pts = s.title.strRef.strCache.pt
                if pts:
                    name = str(pts[0].v)
            elif s.title and s.title.v:
                name = str(s.title.v)
        except Exception:
            pass
        ref = ""
        try:
            if s.val and s.val.numRef and s.val.numRef.f:
                ref = s.val.numRef.f
        except Exception:
            pass
        out.append(f"{name} <- {ref}")
    return out


def main() -> None:
    wb = load_workbook(PATH, data_only=False)
    ws = wb["3 GRAPHS"]
    charts = list(ws._charts)
    print(f"Total charts: {len(charts)}\n")

    sections = [
        (4, "1 GROWTH & FLOWS OF VALUE"),
        (26, "2 FINANCIAL PERFORMANCE & PROFITABILITY RATIOS"),
        (47, "3 EQUITY & DEBT RATIOS"),
        (68, "4 WHAT DOES IT DO WITH CASH?"),
        (91, "5 BALANCE SHEET (EQUITY, ASSETS, LIABILITIES)"),
        (9999, "END"),
    ]

    def section_for_row(row: int) -> str:
        for start, name in sections:
            if row < start:
                return prev
            prev = name
        return sections[-2][1]

    prev = sections[0][1]
    for i, ch in enumerate(charts, 1):
        row = ch.anchor._from.row + 1 if ch.anchor and hasattr(ch.anchor, "_from") else 0
        sec = section_for_row(row)
        title = chart_title(ch)
        ctype = type(ch).__name__
        print(f"--- Chart {i} | Section: {sec} | Row anchor ~{row} | Type: {ctype} ---")
        print(f"Title: {title}")
        for si in series_info(ch):
            print(f"  Series: {si}")
        print()


if __name__ == "__main__":
    main()
