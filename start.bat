@echo off
chcp 65001 >nul
echo ========================================
echo           NewsHub One-Click Startup
echo ========================================

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found, please install Node.js first
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found, please install Python first
    pause
    exit /b 1
)

REM Check Go
go version >nul 2>&1
if errorlevel 1 (
    echo Error: Go not found, please install Go first
    pause
    exit /b 1
)

echo Starting all NewsHub application services...

REM Check if in correct directory
if not exist "package.json" (
    echo Error: Please run this script in the NewsHub project root directory
    pause
    exit /b 1
)

REM Check and install frontend dependencies
echo.
echo 1. Checking frontend dependencies...
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo Frontend dependencies installation failed
        pause
        exit /b 1
    )
)

REM Check and install crawler service dependencies
echo.
echo 2. Checking crawler service dependencies...
cd crawler-service
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment and install dependencies
echo Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo Crawler service dependencies installation failed
    pause
    exit /b 1
)
cd ..

REM Check Go environment and backend dependencies
echo.
echo 3. Checking backend service...
cd server
go mod tidy
if errorlevel 1 (
    echo Backend dependencies check failed
    pause
    exit /b 1
)
cd ..

REM Start services
echo.
echo 4. Starting services...

REM Start backend service
echo Starting backend service...
start "NewsHub Backend" cmd /k "cd server && go run main.go"

REM Wait 2 seconds
timeout /t 2 /nobreak >nul

REM Start crawler service
echo Starting crawler service...
start "NewsHub Crawler" cmd /k "cd crawler-service && .venv\Scripts\activate.bat && python main.py"

REM Wait 2 seconds
timeout /t 2 /nobreak >nul

REM Start frontend service
echo Starting frontend service...
start "NewsHub Frontend" cmd /k "npm run dev"

echo.
echo === All services are starting ===
echo Frontend service: http://localhost:3000
echo Backend service: http://localhost:8080
echo Crawler service: http://localhost:8001
echo.
echo Please wait a few seconds for services to fully start...
echo Press any key to exit startup script (services will continue running in background)
pause >nul