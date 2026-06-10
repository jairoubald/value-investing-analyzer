import { useState, type FormEvent } from "react";

interface TickerSearchProps {
  onSearch: (ticker: string) => void;
  loading: boolean;
}

export function TickerSearch({ onSearch, loading }: TickerSearchProps) {
  const [ticker, setTicker] = useState("AAPL");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = ticker.trim();
    if (trimmed) onSearch(trimmed.toUpperCase());
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full max-w-xl flex-col gap-3 sm:flex-row"
    >
      <label className="sr-only" htmlFor="ticker">
        Ticker
      </label>
      <input
        id="ticker"
        value={ticker}
        onChange={(event) => setTicker(event.target.value.toUpperCase())}
        placeholder="Ej: AAPL, META, MSFT"
        className="mono flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-lg tracking-wide outline-none transition focus:border-emerald-400/60 focus:ring-2 focus:ring-emerald-400/20"
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="submit"
        disabled={loading || !ticker.trim()}
        className="rounded-xl bg-emerald-500 px-6 py-3 font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Analizando..." : "Analizar"}
      </button>
    </form>
  );
}
