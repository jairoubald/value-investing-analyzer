# Phase 1 — MSFT preload

## Now
- `backend/data/msft_1data.json` — snapshot of Excel sheet `1 DATA`
- `GET /api/thesis/MSFT` — Magic Numbers + charts (validated vs Excel)

## Future (multi-company)
- Upload `.xlsx` with one sheet per company; **sheet name = ticker** (e.g. `MSFT`, `AAPL`)
- Same column layout as `1 DATA`; parser writes `backend/data/{ticker}_1data.json`
- UI: company picker populated from available tickers

No code for upload yet — data model and API path already ticker-scoped.
