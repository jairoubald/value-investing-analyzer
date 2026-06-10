import { useCallback, useEffect, useState } from "react";
import { MetricsDashboard } from "./components/MetricsDashboard";
import { TickerSearch } from "./components/TickerSearch";
import type { AnalysisResult } from "./types";

export default function App() {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (ticker: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/analyze/${encodeURIComponent(ticker)}?years=10`);
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || "No se pudo analizar el ticker");
      }

      setData(payload);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    analyze("AAPL");
  }, [analyze]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="mb-10 space-y-4">
        <p className="text-sm uppercase tracking-[0.25em] text-emerald-300/70">
          Value Investing
        </p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight sm:text-5xl">
          Analiza acciones con datos fundamentales de 10 años
        </h1>
        <p className="max-w-2xl text-lg text-white/60">
          Ingresa un ticker para ver ventas, márgenes, ROE, deuda y flujo de caja. Ideal para
          evaluar la calidad del negocio antes de invertir.
        </p>
      </div>

      <TickerSearch onSearch={analyze} loading={loading} />

      {error && (
        <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-200">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="mt-10 animate-pulse rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/50">
          Cargando datos financieros...
        </div>
      )}

      {data && !loading && (
        <div className="mt-10">
          <MetricsDashboard data={data} />
        </div>
      )}
    </div>
  );
}
