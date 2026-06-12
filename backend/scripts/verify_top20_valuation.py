#!/usr/bin/env python3
"""Report multiples + consensus completeness for top-20 tickers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_top20_valuation import TOP_20, audit

if __name__ == "__main__":
    report = audit()
    print(json.dumps(report, indent=2))
    if report["multiples_ok"] < 20 or report["consensus_ok"] < 20:
        sys.exit(1)
