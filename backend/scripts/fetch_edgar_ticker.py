#!/usr/bin/env python3
"""Fetch ticker from SEC EDGAR, build 1 DATA JSON (free path)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.edgar_provider import EdgarError, fetch_company_facts
from services.normalize_edgar import normalize_edgar_facts
from services.magic_numbers import DataSheet, compute_magic_numbers

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    p = argparse.ArgumentParser(description="SEC EDGAR → 1 DATA homologation")
    p.add_argument("ticker", nargs="?", default="AAPL")
    p.add_argument("--save", action="store_true", help="Write backend/data/{ticker}_edgar_1data.json")
    p.add_argument("--run-engine", action="store_true")
    args = p.parse_args()
    ticker = args.ticker.upper()

    print("Provider: SEC EDGAR (free, US listed)")
    print(f"Fetching {ticker}…")

    try:
        facts = fetch_company_facts(ticker)
    except EdgarError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("\nSetup:")
        print("  Set SEC_USER_AGENT in backend/.env (real email — SEC requirement)")
        sys.exit(1)

    payload = normalize_edgar_facts(ticker, facts)
    print(f"Built 1 DATA: {len(payload['years'])} years, {len(payload['grid'])} rows populated")
    for y in payload["years"]:
        print(f"  {y['fy']}  end {y['end_date']}")

    if args.save:
        out = DATA_DIR / f"{ticker.lower()}_edgar_1data.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved {out}")

    if args.run_engine:
        result = compute_magic_numbers(DataSheet(payload))
        b1 = result["blocks"][0]
        rev = next(m for m in b1["metrics"] if m["key"] == "TOTALREVENUE")
        last_fy = payload["years"][-1]["fy"]
        print(f"\nEngine check ({last_fy}): Revenue = {rev['values'].get(last_fy)}")

    print("\nLive API: GET /api/thesis/AAPL?source=edgar")


if __name__ == "__main__":
    main()
