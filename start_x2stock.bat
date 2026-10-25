@echo off
setlocal

rem Start both services from the project root.
cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python virtual environment not found:
    echo         %PYTHON%
    echo Create it with: python -m venv .venv
    pause
    exit /b 1
)

if not exist "%BACKEND_DIR%\app\main.py" (
    echo [ERROR] Backend entrypoint not found: %BACKEND_DIR%\app\main.py
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend package file not found: %FRONTEND_DIR%\package.json
    pause
    exit /b 1
)

echo Starting X2Stock backend at http://localhost:8000 ...
start "X2Stock Backend" /D "%BACKEND_DIR%" cmd /k ""%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Starting X2Stock frontend at http://localhost:5173 ...
where pnpm >nul 2>nul
if not errorlevel 1 (
    start "X2Stock Frontend" /D "%FRONTEND_DIR%" cmd /k "pnpm run dev -- --host 0.0.0.0"
) else (
    where npm >nul 2>nul
    if not errorlevel 1 (
        start "X2Stock Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev -- --host 0.0.0.0"
    ) else (
        echo [ERROR] Neither pnpm nor npm was found in PATH.
        echo Install Node.js, then run this file again.
        pause
        exit /b 1
    )
)

echo.
echo X2Stock services are starting.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API docs: http://localhost:8000/docs
timeout /t 3 /nobreak >nul
exit /b 0
