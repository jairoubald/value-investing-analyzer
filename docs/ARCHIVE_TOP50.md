# Archived: top-50 + live search build

The full top-50 list, SEC lookup, and live EDGAR fetch UI were removed in the
**preload-5 instant demo** mode (engine `magic_numbers_v5_preload5`).

To restore later: check git history before the "preload5" commit, or re-enable:

- `services/ticker_lookup.py`
- `/api/ticker/{sym}/refresh` endpoints in `main.py`
- SEARCH / LOOKUP UI in `index.html`
- `backend/data/*_edgar_1data.json` for all 50 tickers

Current demo tickers (instant, cache-only):

- MSFT (Excel reference `msft_1data.json`)
- AAPL, NVDA, GOOGL, AMZN (`*_edgar_1data.json`)
