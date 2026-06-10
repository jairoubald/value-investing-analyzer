# SEC EDGAR homologation (free path)

Maps [SEC companyfacts XBRL](https://www.sec.gov/edgar/sec-api-documentation) into the same `1 DATA` JSON as FMP and Excel.

## Setup

1. Add to `backend/.env` (SEC requires a descriptive User-Agent with contact email):

   ```
   SEC_USER_AGENT=YourAppName your.email@example.com
   ```

2. No API key required.

## CLI

From `backend/`:

```powershell
.venv\Scripts\python.exe scripts\fetch_edgar_ticker.py AAPL --save
.venv\Scripts\python.exe scripts\compare_sources.py AAPL
```

`compare_sources.py` prints:

- Period **end dates** FMP vs EDGAR (Apple FY ends in September — should match when both use fiscal year labels).
- **% variation** per row (Revenue, NI, Assets, CFO, Capex, …).

## Live API

```
GET /api/thesis/AAPL?source=edgar
```

## Limits vs FMP

| | EDGAR | FMP free |
|---|-------|----------|
| Cost | Free | Free tier |
| History | Many years in XBRL | 5 years |
| Coverage | US SEC filers | Global + US |
| Tags | Raw us-gaap, company-specific gaps | Standardized statements |
| Rate limit | ~10 req/s with throttle | Daily call cap |

## XBRL mapping

See `ROW_TAGS` in `services/normalize_edgar.py`. First matching us-gaap tag wins per fiscal year.

Capex / dividends are negated to match Excel cash-flow sign convention (row 212, etc.).
