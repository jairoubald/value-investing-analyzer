import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AnalysisResult } from "../types";
import { chartBillions, formatBillions, formatPercent } from "../utils/format";

interface MetricsDashboardProps {
  data: AnalysisResult;
}

const tooltipStyle = {
  backgroundColor: "#111827",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "12px",
};

export function MetricsDashboard({ data }: MetricsDashboardProps) {
  const chartData = data.years.map((year) => ({
    year: year.year,
    revenue: chartBillions(year.revenue),
    gross_margin: year.gross_margin,
    operating_margin: year.operating_margin,
    net_margin: year.net_margin,
    roe: year.roe,
    total_debt: chartBillions(year.total_debt),
    operating_cash_flow: chartBillions(year.operating_cash_flow),
    free_cash_flow: chartBillions(year.free_cash_flow),
  }));

  return (
    <div className="space-y-8">
      <header className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <p className="text-sm uppercase tracking-[0.2em] text-emerald-300/80">
          Análisis fundamental
        </p>
        <h2 className="mt-2 text-3xl font-bold">{data.company_name}</h2>
        <p className="mono mt-1 text-white/60">
          {data.ticker} · {data.currency} · últimos {data.years.length} años
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Ventas (Revenue)" subtitle="Miles de millones">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="revenue" name="Ventas" fill="#34d399" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Márgenes" subtitle="Porcentaje sobre ventas">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" unit="%" />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Line
                type="monotone"
                dataKey="gross_margin"
                name="Bruto"
                stroke="#34d399"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="operating_margin"
                name="Operativo"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="net_margin"
                name="Neto"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="ROE" subtitle="Return on Equity (%)">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" unit="%" />
              <Tooltip contentStyle={tooltipStyle} />
              <Line
                type="monotone"
                dataKey="roe"
                name="ROE"
                stroke="#a78bfa"
                strokeWidth={3}
                dot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Deuda total" subtitle="Miles de millones">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="total_debt" name="Deuda" fill="#f87171" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Flujo de caja"
          subtitle="Operativo y libre (miles de millones)"
          className="lg:col-span-2"
        >
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Bar dataKey="operating_cash_flow" name="Operativo" fill="#38bdf8" radius={[6, 6, 0, 0]} />
              <Bar dataKey="free_cash_flow" name="Libre (FCF)" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </section>

      <section className="overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.03]">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-white/[0.02] text-white/60">
            <tr>
              <th className="px-4 py-3 font-medium">Año</th>
              <th className="px-4 py-3 font-medium">Ventas</th>
              <th className="px-4 py-3 font-medium">Margen bruto</th>
              <th className="px-4 py-3 font-medium">Margen operativo</th>
              <th className="px-4 py-3 font-medium">Margen neto</th>
              <th className="px-4 py-3 font-medium">ROE</th>
              <th className="px-4 py-3 font-medium">Deuda</th>
              <th className="px-4 py-3 font-medium">FCO</th>
              <th className="px-4 py-3 font-medium">FCF</th>
            </tr>
          </thead>
          <tbody>
            {data.years.map((year) => (
              <tr key={year.year} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="mono px-4 py-3 font-medium">{year.year}</td>
                <td className="mono px-4 py-3">{formatBillions(year.revenue, data.currency)}</td>
                <td className="mono px-4 py-3">{formatPercent(year.gross_margin)}</td>
                <td className="mono px-4 py-3">{formatPercent(year.operating_margin)}</td>
                <td className="mono px-4 py-3">{formatPercent(year.net_margin)}</td>
                <td className="mono px-4 py-3">{formatPercent(year.roe)}</td>
                <td className="mono px-4 py-3">{formatBillions(year.total_debt, data.currency)}</td>
                <td className="mono px-4 py-3">
                  {formatBillions(year.operating_cash_flow, data.currency)}
                </td>
                <td className="mono px-4 py-3">
                  {formatBillions(year.free_cash_flow, data.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article
      className={`rounded-2xl border border-white/10 bg-white/[0.03] p-5 ${className}`}
    >
      <div className="mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-white/50">{subtitle}</p>
      </div>
      {children}
    </article>
  );
}
