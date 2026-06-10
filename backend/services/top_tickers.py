"""Five preloaded tickers — instant demo (no live API on page load)."""

TOP_US_TICKERS: tuple[str, ...] = (
    "MSFT",
    "AAPL",
    "NVDA",
    "GOOGL",
    "AMZN",
)

PRELOADED_TICKERS = frozenset(TOP_US_TICKERS)

# Archived list (top-50 + search build) kept for later — see docs/ARCHIVE_TOP50.md
TOP_US_50: tuple[str, ...] = TOP_US_TICKERS
