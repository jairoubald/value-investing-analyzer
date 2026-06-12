@echo off
cd /d "%~dp0backend"
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

set PORT=8002
echo Stopping prior servers on ports 8001 and %PORT%...
for %%P in (8001 %PORT%) do (
  for /L %%i in (1,1,5) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R ":%%P.*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
  )
)

echo Starting Thesis Tool on http://127.0.0.1:%PORT%
echo Apple: http://127.0.0.1:%PORT%/?ticker=AAPL
echo Multiples: http://127.0.0.1:%PORT%/?ticker=AAPL#valuation-multiples
uvicorn main:app --reload --host 127.0.0.1 --port %PORT%
