"""Build company profile sidecars for preloaded tickers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.fmp_provider import fetch_company_profile_bundle
from services.top_tickers import PRELOADED_TICKERS

DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static" / "profile"


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch FMP profile → data/*_profile.json")
    p.add_argument("tickers", nargs="*", default=list(PRELOADED_TICKERS))
    args = p.parse_args()

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    for ticker in args.tickers:
        sym = ticker.upper()
        try:
            profile = fetch_company_profile_bundle(sym)
        except Exception as exc:
            profile = {"error": str(exc), "ticker": sym}
        payload = {"ticker": sym, "company_profile": profile}
        path = DATA_DIR / f"{sym.lower()}_profile.json"
        static_path = STATIC_DIR / f"{sym.lower()}_profile.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        static_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if profile.get("error"):
            print(f"  {sym}: ERROR — {profile['error']}")
        else:
            segs = len(profile.get("segments") or [])
            print(f"  {sym}: {profile.get('name')} · {profile.get('sector')} · {segs} segments")


if __name__ == "__main__":
    main()
