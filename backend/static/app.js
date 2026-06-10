const charts = {};

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      labels: { color: "#94a3b8" },
    },
  },
  scales: {
    x: {
      ticks: { color: "#94a3b8" },
      grid: { color: "rgba(255,255,255,0.06)" },
    },
    y: {
      ticks: { color: "#94a3b8" },
      grid: { color: "rgba(255,255,255,0.06)" },
    },
  },
};

function formatBillions(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)} T ${currency}`;
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)} B ${currency}`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)} M ${currency}`;
  return `${sign}${abs.toLocaleString("es-ES")} ${currency}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function toBillions(value) {
  if (value === null || value === undefined) return null;
  return Math.round((value / 1e9) * 100) / 100;
}

function destroyCharts() {
  Object.values(charts).forEach((chart) => chart.destroy());
  Object.keys(charts).forEach((key) => delete charts[key]);
}

function renderCharts(data) {
  destroyCharts();

  const labels = data.years.map((y) => y.year);

  charts.revenue = new Chart(document.getElementById("chart-revenue"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Ventas",
          data: data.years.map((y) => toBillions(y.revenue)),
          backgroundColor: "#34d399",
          borderRadius: 6,
        },
      ],
    },
    options: chartDefaults,
  });

  charts.margins = new Chart(document.getElementById("chart-margins"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Bruto",
          data: data.years.map((y) => y.gross_margin),
          borderColor: "#34d399",
          tension: 0.3,
        },
        {
          label: "Operativo",
          data: data.years.map((y) => y.operating_margin),
          borderColor: "#60a5fa",
          tension: 0.3,
        },
        {
          label: "Neto",
          data: data.years.map((y) => y.net_margin),
          borderColor: "#fbbf24",
          tension: 0.3,
        },
      ],
    },
    options: {
      ...chartDefaults,
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, ticks: { color: "#94a3b8", callback: (v) => `${v}%` } },
      },
    },
  });

  charts.roe = new Chart(document.getElementById("chart-roe"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "ROE",
          data: data.years.map((y) => y.roe),
          borderColor: "#a78bfa",
          backgroundColor: "rgba(167, 139, 250, 0.15)",
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      ...chartDefaults,
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, ticks: { color: "#94a3b8", callback: (v) => `${v}%` } },
      },
    },
  });

  charts.debt = new Chart(document.getElementById("chart-debt"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Deuda",
          data: data.years.map((y) => toBillions(y.total_debt)),
          backgroundColor: "#f87171",
          borderRadius: 6,
        },
      ],
    },
    options: chartDefaults,
  });

  charts.cashflow = new Chart(document.getElementById("chart-cashflow"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Operativo",
          data: data.years.map((y) => toBillions(y.operating_cash_flow)),
          backgroundColor: "#38bdf8",
          borderRadius: 6,
        },
        {
          label: "Libre (FCF)",
          data: data.years.map((y) => toBillions(y.free_cash_flow)),
          backgroundColor: "#22c55e",
          borderRadius: 6,
        },
      ],
    },
    options: chartDefaults,
  });
}

function renderTable(data) {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = data.years
    .map(
      (year) => `
      <tr>
        <td>${year.year}</td>
        <td>${formatBillions(year.revenue, data.currency)}</td>
        <td>${formatPercent(year.gross_margin)}</td>
        <td>${formatPercent(year.operating_margin)}</td>
        <td>${formatPercent(year.net_margin)}</td>
        <td>${formatPercent(year.roe)}</td>
        <td>${formatBillions(year.total_debt, data.currency)}</td>
        <td>${formatBillions(year.operating_cash_flow, data.currency)}</td>
        <td>${formatBillions(year.free_cash_flow, data.currency)}</td>
      </tr>
    `,
    )
    .join("");
}

function renderDashboard(data) {
  document.getElementById("company-name").textContent = data.company_name;
  document.getElementById("company-meta").textContent =
    `${data.ticker} · ${data.currency} · últimos ${data.years.length} años`;

  renderCharts(data);
  renderTable(data);

  document.getElementById("dashboard").classList.remove("hidden");
}

async function analyzeTicker(ticker) {
  const errorEl = document.getElementById("error");
  const loadingEl = document.getElementById("loading");
  const dashboardEl = document.getElementById("dashboard");
  const btn = document.getElementById("search-btn");

  errorEl.classList.add("hidden");
  dashboardEl.classList.add("hidden");
  loadingEl.classList.remove("hidden");
  btn.disabled = true;

  try {
    const response = await fetch(`/api/analyze/${encodeURIComponent(ticker)}?years=10`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "No se pudo analizar el ticker");
    }

    renderDashboard(payload);
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.remove("hidden");
  } finally {
    loadingEl.classList.add("hidden");
    btn.disabled = false;
  }
}

document.getElementById("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const ticker = document.getElementById("ticker-input").value.trim().toUpperCase();
  if (ticker) analyzeTicker(ticker);
});

analyzeTicker("AAPL");
