"""Precompute one-pager JSON for static fallback."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.data_cache import load_cached
from services.magic_numbers import DataSheet, compute_magic_numbers, enrich_payload_consensus, enrich_payload_multiples
from services.one_pager import enrich_payload_profile
from services.top_tickers import PRELOADED_TICKERS

STATIC_DIR = ROOT / "static" / "one_pager"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tickers", nargs="*", default=list(PRELOADED_TICKERS))
    args = p.parse_args()
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    for ticker in args.tickers:
        sym = ticker.upper()
        payload = load_cached(sym, "edgar") or load_cached("MSFT", "preload")
        if sym == "MSFT" and not payload:
            payload = json.loads((ROOT / "data" / "msft_1data.json").read_text(encoding="utf-8"))
        if not payload:
            print(f"  {sym}: no cache")
            continue
        payload = dict(payload)
        payload["ticker"] = sym
        payload = enrich_payload_profile(enrich_payload_consensus(enrich_payload_multiples(payload)))
        result = compute_magic_numbers(DataSheet(payload))
        op = result.get("one_pager")
        out = {"ticker": sym, "one_pager": op, "market_bar": result.get("market_bar")}
        path = STATIC_DIR / f"{sym.lower()}_one_pager.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        blend = (op or {}).get("valuation_snapshot", {}).get("blend_price")
        print(f"  {sym}: blend=${blend}")


if __name__ == "__main__":
    main()
