#!/usr/bin/env python3
"""Build multiples + consensus sidecars for top-20 market-cap tickers."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from services.analyst_consensus import fetch_analyst_consensus
from services.data_cache import load_cached, warm_ticker_catalog
from services.fmp_provider import FMPError
from services.multiples_series import fetch_and_build_multiples_series

DATA_DIR = ROOT / "data"
STATIC_CONSENSUS = ROOT / "static" / "consensus"

TOP_20 = [
    "NVDA",
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "AVGO",
    "META",
    "TSLA",
    "LLY",
    "BRK-B",
    "WMT",
    "AMD",
    "JPM",
    "V",
    "ORCL",
    "NFLX",
    "MA",
    "XOM",
    "UNH",
    "AMAT",
]


def save_consensus(ticker: str) -> bool:
    sym = ticker.upper()
    data = fetch_analyst_consensus(sym)
    payload = {"ticker": sym, "analyst_consensus": data}
    for base in (DATA_DIR, STATIC_CONSENSUS):
        base.mkdir(parents=True, exist_ok=True)
        (base / f"{sym.lower()}_consensus.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return not data.get("error")


def save_multiples(ticker: str) -> bool:
    sym = ticker.upper()
    payload = load_cached(sym, "edgar") or load_cached(sym, "preload")
    if not payload:
        print(f"  multiples SKIP {sym}: no 1data cache")
        return False
    try:
        series = fetch_and_build_multiples_series(sym, payload=payload)
    except FMPError as exc:
        print(f"  multiples SKIP {sym}: {exc}")
        return False
    out = {"multiples_series": series}
    (DATA_DIR / f"{sym.lower()}_multiples.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    pe_n = len(series.get("pe", {}).get("points") or series.get("pe", {}).get("history_values") or [])
    pb_n = len(series.get("pbv", {}).get("points") or series.get("pbv", {}).get("history_values") or [])
    print(f"  multiples OK {sym}: P/E {pe_n} pts, P/BV {pb_n} pts")
    return pe_n > 0 or pb_n > 0


def audit() -> dict:
    rows = []
    for sym in TOP_20:
        mpath = DATA_DIR / f"{sym.lower()}_multiples.json"
        cpath = DATA_DIR / f"{sym.lower()}_consensus.json"
        multiples_ok = False
        consensus_ok = False
        if mpath.is_file():
            mdata = json.loads(mpath.read_text(encoding="utf-8"))
            ms = mdata.get("multiples_series") or mdata
            pe = ms.get("pe", {})
            pb = ms.get("pbv", {})
            multiples_ok = bool(pe.get("points") or pe.get("history_values") or pb.get("points") or pb.get("history_values"))
        if cpath.is_file():
            cdata = json.loads(cpath.read_text(encoding="utf-8"))
            ac = cdata.get("analyst_consensus") or {}
            consensus_ok = ac.get("median") is not None and not ac.get("error")
        rows.append({"ticker": sym, "multiples": multiples_ok, "consensus": consensus_ok})
    return {"rows": rows, "multiples_ok": sum(r["multiples"] for r in rows), "consensus_ok": sum(r["consensus"] for r in rows)}


def main() -> None:
    warm_ticker_catalog()
    has_fmp = bool(os.environ.get("FMP_API_KEY", "").strip())
    print(f"Top-20 valuation build · FMP={'yes' if has_fmp else 'NO (Yahoo prices + EDGAR)'}")
    before = audit()
    for sym in TOP_20:
        row = next(r for r in before["rows"] if r["ticker"] == sym)
        need_m = not row["multiples"]
        need_c = not row["consensus"]
        if not need_m and not need_c:
            continue
        print(f"{sym}:")
        if need_m:
            save_multiples(sym)
        if need_c:
            save_consensus(sym)
        time.sleep(2.5)
    report = audit()
    print(f"\nDone · multiples {report['multiples_ok']}/20 · consensus {report['consensus_ok']}/20")
    for row in report["rows"]:
        if not row["multiples"] or not row["consensus"]:
            print(f"  GAP {row['ticker']}: multiples={'OK' if row['multiples'] else 'MISSING'} consensus={'OK' if row['consensus'] else 'MISSING'}")
    if report["multiples_ok"] < 20 or report["consensus_ok"] < 20:
        sys.exit(1)


if __name__ == "__main__":
    main()
