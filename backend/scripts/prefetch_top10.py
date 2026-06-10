#!/usr/bin/env python3
"""Download EDGAR 1 DATA for top US tickers (run locally before deploy)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.edgar_provider import EdgarError, fetch_company_facts
from services.normalize_edgar import normalize_edgar_facts
from services.one_data_schema import HISTORY_YEARS
from services.top_tickers import TOP_US_50

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    p = argparse.ArgumentParser(description="Prefetch EDGAR cache for top US tickers")
    p.add_argument("--force", action="store_true", help="Re-download even if file exists")
    p.add_argument("--limit", type=int, default=0, help="Only first N tickers (0 = all)")
    args = p.parse_args()

    tickers = TOP_US_50[: args.limit] if args.limit else TOP_US_50
    print(f"Prefetch {len(tickers)} tickers · up to {HISTORY_YEARS} FY each")
    ok, fail = [], []
    for ticker in tickers:
        out = DATA_DIR / f"{ticker.lower()}_edgar_1data.json"
        if out.exists() and not args.force:
            print(f"  skip {ticker}")
            ok.append(ticker)
            continue
        print(f"  fetch {ticker}…", flush=True)
        try:
            facts = fetch_company_facts(ticker)
            payload = normalize_edgar_facts(ticker, facts)
            n = len(payload["years"])
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"  OK {ticker} -> {n} years")
            ok.append(ticker)
        except (EdgarError, ValueError) as exc:
            print(f"  FAIL {ticker}: {exc}")
            fail.append(ticker)
    print(f"\nDone: {len(ok)} ok, {len(fail)} failed")
    if fail:
        print("Failed:", ", ".join(fail))
        sys.exit(1)


if __name__ == "__main__":
    main()
