#!/usr/bin/env python3
"""Quick check: valuation.pe / valuation.pbv for preloaded tickers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.data_cache import load_cached
from services.magic_numbers import DataSheet, compute_magic_numbers, enrich_payload_multiples
from services.top_tickers import TOP_US_TICKERS


def main() -> None:
    for ticker in TOP_US_TICKERS:
        payload = load_cached(ticker, "preload") or load_cached(ticker, "edgar")
        if not payload:
            print(f"{ticker}: no cache")
            continue
        payload = enrich_payload_multiples(payload)
        result = compute_magic_numbers(DataSheet(payload))
        pe = result.get("valuation", {}).get("pe", {})
        pbv = result.get("valuation", {}).get("pbv", {})
        pe_hist = len((pe.get("controls") or [{}])[0].get("history") or [])
        pb_hist = len((pbv.get("controls") or [{}])[0].get("history") or [])
        print(
            f"{ticker}: PE ${pe.get('result', {}).get('price_per_share', 'err:' + str(pe.get('error')))} "
            f"({pe_hist} pts) | PBV ${pbv.get('result', {}).get('price_per_share', 'err:' + str(pbv.get('error')))} "
            f"({pb_hist} pts)"
        )


if __name__ == "__main__":
    main()
