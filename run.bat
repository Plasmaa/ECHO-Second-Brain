@echo off
title ECHO - Second Brain Memory Agent
color 0B

echo =======================================================
echo    🧠 ECHO - Second Brain & Personal Memory Agent
echo =======================================================
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating .venv...
    python -m venv .venv
    echo [*] Installing dependencies...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [*] Starting ECHO Web Application & Telegram Bot...
echo [*] Web UI will be available at: http://localhost:8000/
echo [*] Interactive API Docs: http://localhost:8000/docs
echo [*] Telegram Bot is listening...
echo.

:: Open default browser after 2 seconds in background
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000/"

:: Start FastAPI + Telegram Bot via uvicorn
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

pause
