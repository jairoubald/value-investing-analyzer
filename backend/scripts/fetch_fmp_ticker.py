#!/usr/bin/env python3
"""Fetch ticker from FMP, build 1 DATA JSON, optionally validate vs Excel preload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.fmp_provider import FMPError, fetch_bundle
from services.normalize_fmp import normalize_fmp_bundle
from services.magic_numbers import DataSheet, compute_magic_numbers

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Rows to score homologation quality vs Excel/Bloomberg 1 DATA
CHECK_ROWS = (14, 26, 50, 128, 172, 209, 212)


def compare_to_reference(fmp_payload: dict, ref_path: Path) -> list[str]:
    ref = json.loads(ref_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    ref_years = {y["fy"]: y["col"] for y in ref["years"]}
    fmp_years = {y["fy"]: y["col"] for y in fmp_payload["years"]}
    common_fys = sorted(set(ref_years) & set(fmp_years))

    if not common_fys:
        lines.append("WARNING: no overlapping fiscal years between FMP and reference")
        return lines

    for row in CHECK_ROWS:
        diffs = []
        for fy in common_fys[-5:]:
            rc, fc = str(ref_years[fy]), str(fmp_years[fy])
            rv = ref.get("grid", {}).get(str(row), {}).get("values", {}).get(rc)
            fv = fmp_payload.get("grid", {}).get(str(row), {}).get("values", {}).get(fc)
            if rv is None or fv is None:
                continue
            if rv == 0:
                pct = 0 if fv == 0 else 999
            else:
                pct = abs(fv - rv) / abs(rv) * 100
            diffs.append(pct)
        if diffs:
            avg = sum(diffs) / len(diffs)
            label = fmp_payload["grid"].get(str(row), {}).get("label", f"row {row}")
            flag = "OK" if avg < 2 else ("WARN" if avg < 8 else "FAIL")
            lines.append(f"  [{flag}] {label} (row {row}): avg diff {avg:.1f}% over {len(diffs)} years")

    return lines


def main() -> None:
    p = argparse.ArgumentParser(description="FMP → 1 DATA homologation test")
    p.add_argument("ticker", nargs="?", default="MSFT")
    p.add_argument("--save", action="store_true", help="Write backend/data/{ticker}_fmp_1data.json")
    p.add_argument(
        "--ref",
        type=Path,
        default=DATA_DIR / "msft_1data.json",
        help="Excel/Bloomberg reference JSON for validation",
    )
    p.add_argument("--run-engine", action="store_true", help="Print sample Magic Numbers output")
    args = p.parse_args()
    ticker = args.ticker.upper()

    print(f"Provider: Financial Modeling Prep (FMP) — budget tier Starter ~$22/mo")
    print(f"Fetching {ticker}…")

    try:
        bundle = fetch_bundle(ticker)
    except FMPError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("\nSetup (2 min):")
        print("  1. Register free key: https://site.financialmodelingprep.com/register")
        print("  2. set FMP_API_KEY=your_key   (PowerShell)")
        print("  3. Re-run this script")
        sys.exit(1)

    payload = normalize_fmp_bundle(ticker, bundle)
    print(f"Built 1 DATA: {len(payload['years'])} years, {len(payload['grid'])} rows populated")
    print(f"  FY range: {payload['years'][0]['fy']} -> {payload['years'][-1]['fy']}")

    if args.ref.exists() and ticker == args.ref.stem.split("_")[0].upper():
        print(f"\nValidation vs {args.ref.name}:")
        for line in compare_to_reference(payload, args.ref):
            print(line)

    if args.save:
        out = DATA_DIR / f"{ticker.lower()}_fmp_1data.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved {out}")

    if args.run_engine:
        result = compute_magic_numbers(DataSheet(payload))
        b1 = result["blocks"][0]
        rev = next(m for m in b1["metrics"] if m["key"] == "TOTALREVENUE")
        ni = next(m for m in b1["metrics"] if m["key"] == "NET INCOME")
        last_fy = payload["years"][-1]["fy"]
        print(f"\nEngine check ({last_fy}):")
        print(f"  Revenue: {rev['values'].get(last_fy)}")
        print(f"  Net income: {ni['values'].get(last_fy)}")
        print(f"  Chart sections: {len(result['chart_sections'])}")

    print("\nLive API: GET /api/thesis/MSFT?source=fmp  (requires FMP_API_KEY on server)")


if __name__ == "__main__":
    main()
