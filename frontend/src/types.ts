export interface YearMetrics {
  year: string;
  revenue: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  total_debt: number | null;
  operating_cash_flow: number | null;
  free_cash_flow: number | null;
}

export interface AnalysisResult {
  ticker: string;
  company_name: string;
  currency: string;
  years: YearMetrics[];
}
