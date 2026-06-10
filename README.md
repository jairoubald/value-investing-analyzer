# Value Investing Analyzer

Aplicación web para analizar acciones desde una perspectiva de **value investing**. Ingresa un ticker (por ejemplo `AAPL`, `META`, `MSFT`) y obtén ventas, márgenes, ROE, deuda y flujo de caja de los últimos 10 años.

## Inicio rápido (Windows)

Doble clic en `start.bat` o ejecuta:

```bat
start.bat
```

Abre **http://127.0.0.1:8000** en el navegador.

## Instalación manual

Requisito: **Python 3.12+**

```bat
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Métricas incluidas

| Métrica | Descripción |
|---------|-------------|
| **Ventas** | Ingresos totales anuales |
| **Márgenes** | Bruto, operativo y neto (% sobre ventas) |
| **ROE** | Return on Equity = beneficio neto / patrimonio |
| **Deuda** | Deuda total reportada |
| **Flujo de caja** | Operativo (FCO) y libre (FCF) |

## Fuente de datos

Los datos provienen de los informes **10-K** de la [SEC (EDGAR)](https://www.sec.gov/edgar), la fuente oficial de emisores en EE.UU. Solo están disponibles tickers de empresas cotizadas en bolsa estadounidense.

## Frontend React (opcional)

Si tienes Node.js instalado, también puedes usar el frontend en React:

```bat
cd frontend
npm install
npm run dev
```

Esto abre `http://localhost:5173` con proxy al backend.

## Nota

Esta herramienta es solo informativa y no constituye asesoramiento financiero.
