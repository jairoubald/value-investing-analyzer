@echo off
cd /d "%~dp0backend"
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R ":8001.*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo Starting Thesis Tool on http://127.0.0.1:8001
echo Apple: http://127.0.0.1:8001/?ticker=AAPL
uvicorn main:app --reload --host 127.0.0.1 --port 8001
