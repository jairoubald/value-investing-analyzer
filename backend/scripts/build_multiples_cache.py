#!/usr/bin/env python3
"""Build monthly P/E & P/BV sidecars from FMP (requires FMP_API_KEY)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.data_cache import load_cached
from services.fmp_provider import FMPError
from services.multiples_series import fetch_and_build_multiples_series
from services.top_tickers import TOP_US_TICKERS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    p = argparse.ArgumentParser(description="FMP → multiples_series sidecar JSON")
    p.add_argument("tickers", nargs="*", default=list(TOP_US_TICKERS))
    args = p.parse_args()

    for ticker in args.tickers:
        sym = ticker.upper()
        print(f"Building multiples for {sym}…")
        payload = load_cached(sym, "preload") or load_cached(sym, "edgar")
        try:
            series = fetch_and_build_multiples_series(sym, payload=payload)
        except FMPError as exc:
            print(f"  SKIP {sym}: {exc}")
            continue

        pe_n = len(series.get("pe", {}).get("history_values") or [])
        pb_n = len(series.get("pbv", {}).get("history_values") or [])
        val = series.get("pe", {}).get("validation") or {}
        print(f"  P/E points: {pe_n}  P/BV points: {pb_n}  vendor checks: {val.get('vendor_checks')}")

        out = DATA_DIR / f"{sym.lower()}_multiples.json"
        out.write_text(json.dumps({"multiples_series": series}, indent=2), encoding="utf-8")
        print(f"  Saved {out}")


if __name__ == "__main__":
    main()
