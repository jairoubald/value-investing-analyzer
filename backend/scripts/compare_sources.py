#!/usr/bin/env python3
"""Compare FMP vs EDGAR 1 DATA homologation for the same ticker (e.g. AAPL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.edgar_provider import EdgarError, fetch_company_facts
from services.fmp_provider import FMPError, fetch_bundle
from services.normalize_edgar import normalize_edgar_facts
from services.normalize_fmp import normalize_fmp_bundle
from services.one_data_common import pct_diff
from services.one_data_schema import ENGINE_ROWS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Core rows for headline % variation report
HEADLINE_ROWS = (14, 16, 26, 50, 128, 172, 209, 212)


def _load_fmp(ticker: str, path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    bundle = fetch_bundle(ticker)
    return normalize_fmp_bundle(ticker, bundle)


def _load_edgar(ticker: str, path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    facts = fetch_company_facts(ticker)
    return normalize_edgar_facts(ticker, facts)


def _fy_map(payload: dict) -> dict[str, dict]:
    return {y["fy"]: y for y in payload["years"]}


def compare(fmp: dict, edgar: dict, rows: tuple[int, ...]) -> None:
    fmp_fys = _fy_map(fmp)
    edgar_fys = _fy_map(edgar)
    common = sorted(set(fmp_fys) & set(edgar_fys))

    print(f"\n{'=' * 72}")
    print(f"  {fmp['ticker']} — FMP vs EDGAR (% variation on matched fiscal years)")
    print(f"{'=' * 72}")
    print(f"  FMP years : {fmp['years'][0]['fy']} -> {fmp['years'][-1]['fy']}")
    print(f"  EDGAR years: {edgar['years'][0]['fy']} -> {edgar['years'][-1]['fy']}")
    print(f"  Overlap: {len(common)} years\n")

    print("  Period end dates (FMP vs EDGAR):")
    for fy in common:
        fd = fmp_fys[fy]["end_date"]
        ed = edgar_fys[fy]["end_date"]
        match = "same" if fd == ed else "DIFF"
        print(f"    {fy}:  FMP {fd}  |  EDGAR {ed}  [{match}]")

    print(f"\n  {'Row':>4}  {'Label':<32}  {'Avg %':>7}  {'Max %':>7}  Status")
    print(f"  {'-' * 4}  {'-' * 32}  {'-' * 7}  {'-' * 7}  {'-' * 6}")

    for row in rows:
        fmp_col_by_fy = {y["fy"]: str(y["col"]) for y in fmp["years"]}
        edgar_col_by_fy = {y["fy"]: str(y["col"]) for y in edgar["years"]}
        label = (
            fmp.get("grid", {}).get(str(row), {}).get("label")
            or edgar.get("grid", {}).get(str(row), {}).get("label")
            or f"row {row}"
        )
        pcts: list[float] = []
        for fy in common:
            fc = fmp_col_by_fy[fy]
            ec = edgar_col_by_fy[fy]
            fv = fmp.get("grid", {}).get(str(row), {}).get("values", {}).get(fc)
            ev = edgar.get("grid", {}).get(str(row), {}).get("values", {}).get(ec)
            p = pct_diff(fv, ev)
            if p is not None:
                pcts.append(p)
        if not pcts:
            print(f"  {row:>4}  {label[:32]:<32}  {'n/a':>7}  {'n/a':>7}  SKIP")
            continue
        avg = sum(pcts) / len(pcts)
        mx = max(pcts)
        status = "OK" if avg < 1 else ("WARN" if avg < 5 else "FAIL")
        print(f"  {row:>4}  {label[:32]:<32}  {avg:>6.2f}%  {mx:>6.2f}%  {status}")

    print(f"\n  Detail (headline rows, last 3 overlapping years):")
    for fy in common[-3:]:
        print(f"\n    --- {fy} ---")
        fc = str(fmp_fys[fy]["col"])
        ec = str(edgar_fys[fy]["col"])
        for row in HEADLINE_ROWS:
            label = fmp.get("grid", {}).get(str(row), {}).get("label", f"row {row}")
            fv = fmp.get("grid", {}).get(str(row), {}).get("values", {}).get(fc)
            ev = edgar.get("grid", {}).get(str(row), {}).get("values", {}).get(ec)
            if fv is None and ev is None:
                continue
            p = pct_diff(fv, ev)
            ps = f"{p:.3f}%" if p is not None else "n/a"
            print(f"      row {row:>3} {label[:28]:<28}  FMP={fv}  EDGAR={ev}  diff={ps}")


def main() -> None:
    p = argparse.ArgumentParser(description="FMP vs EDGAR homologation diff")
    p.add_argument("ticker", nargs="?", default="AAPL")
    p.add_argument("--fmp-file", type=Path, help="Use saved FMP JSON instead of live fetch")
    p.add_argument("--edgar-file", type=Path, help="Use saved EDGAR JSON instead of live fetch")
    p.add_argument("--save-edgar", action="store_true")
    p.add_argument("--all-rows", action="store_true", help="Compare all engine rows")
    args = p.parse_args()
    ticker = args.ticker.upper()

    fmp_path = args.fmp_file or DATA_DIR / f"{ticker.lower()}_fmp_1data.json"
    edgar_path = args.edgar_file or DATA_DIR / f"{ticker.lower()}_edgar_1data.json"

    print(f"Loading FMP for {ticker}…")
    try:
        fmp = _load_fmp(ticker, fmp_path if fmp_path.exists() else None)
    except FMPError as exc:
        print(f"FMP error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading EDGAR for {ticker}…")
    try:
        edgar = _load_edgar(ticker, edgar_path if edgar_path.exists() and not args.save_edgar else None)
    except EdgarError as exc:
        print(f"EDGAR error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.save_edgar:
        out = DATA_DIR / f"{ticker.lower()}_edgar_1data.json"
        out.write_text(json.dumps(edgar, indent=2), encoding="utf-8")
        print(f"Saved {out}")

    rows = tuple(ENGINE_ROWS) if args.all_rows else HEADLINE_ROWS
    compare(fmp, edgar, rows)


if __name__ == "__main__":
    main()
