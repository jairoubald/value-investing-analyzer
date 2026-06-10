export function formatBillions(value: number | null, currency = "USD"): string {
  if (value === null || Number.isNaN(value)) return "—";

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (abs >= 1_000_000_000_000) {
    return `${sign}${(abs / 1_000_000_000_000).toFixed(2)} T ${currency}`;
  }
  if (abs >= 1_000_000_000) {
    return `${sign}${(abs / 1_000_000_000).toFixed(2)} B ${currency}`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toFixed(2)} M ${currency}`;
  }
  return `${sign}${abs.toLocaleString("es-ES")} ${currency}`;
}

export function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

export function chartBillions(value: number | null): number | null {
  if (value === null || Number.isNaN(value)) return null;
  return Math.round((value / 1_000_000_000) * 100) / 100;
}
