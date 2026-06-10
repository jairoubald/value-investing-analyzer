# FMP homologation sprint (2-hour test)

## Provider choice: **Financial Modeling Prep (FMP)**

| | |
|---|---|
| **Cost** | Free (250 calls/day) for this test; **Starter ~$22/mo** for launch (< $30) |
| **Why** | Standardized income / balance / cash-flow — closest to Bloomberg → 1 DATA paste workflow |
| **Skip** | WACC row 11 history (optional); tax rate computed from latest FY |

## Setup (5 minutes)

1. Register: https://site.financialmodelingprep.com/register  
2. Copy API key  
3. PowerShell:
   ```powershell
   $env:FMP_API_KEY = "your_key_here"
   ```
4. From `backend`:
   ```powershell
   .venv\Scripts\python.exe scripts\fetch_fmp_ticker.py MSFT --save --run-engine
   ```

## What the pipeline does

```text
FMP API  →  normalize_fmp.py  →  1 DATA JSON  →  compute_magic_numbers()  →  tables + 21 charts
```

Row mapping is documented in `services/one_data_schema.py` (Excel row numbers preserved).

## Live in the web app

Restart `start.bat`, then:

```text
http://127.0.0.1:8001/api/thesis/MSFT?source=fmp
```

Same UI works — point frontend at `?source=fmp` when you add a ticker switch (optional next step).

## Validation

The fetch script compares key rows vs `data/msft_1data.json` (Bloomberg/Excel snapshot):

- Revenue, EBIT, Net income, Total assets, Equity, CFO, Capex  
- Target: **< 2%** avg diff (restated filings may differ slightly from Bloomberg)

## API calls per ticker

One full homologation = **5 calls** (profile, income, balance, cashflow, quote).  
Free tier ≈ **50 tickers/day** if you refresh once.
