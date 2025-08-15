@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Playwright Browser Installation Script
echo ========================================
echo.

echo [INFO] Starting Playwright browser installation...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python first: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Python is available
echo.

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

echo [INFO] pip is available
echo.

REM Install/upgrade playwright
echo [INFO] Installing/upgrading Playwright...
pip install --upgrade playwright
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright
    pause
    exit /b 1
)

echo [INFO] Playwright package installed successfully
echo.

REM Install Playwright browsers
echo [INFO] Installing Playwright browsers (this may take several minutes)...
echo [INFO] Downloading Chromium, Firefox, and WebKit browsers...
playwright install
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright browsers
    echo [INFO] Trying alternative installation method...
    python -m playwright install
    if errorlevel 1 (
        echo [ERROR] Alternative installation also failed
        echo [INFO] Please check your internet connection and try again
        pause
        exit /b 1
    )
)

echo.
echo [SUCCESS] Playwright browsers installed successfully!
echo.

REM Install system dependencies (Windows)
echo [INFO] Installing system dependencies for Windows...
playwright install-deps
if errorlevel 1 (
    echo [WARNING] Some system dependencies might not be installed
    echo [INFO] This is normal on Windows, continuing...
)

echo.
echo [INFO] Verifying installation...
echo.

REM Test Playwright installation
echo [INFO] Testing Playwright installation...
python -c "from playwright.sync_api import sync_playwright; print('Playwright import successful')"
if errorlevel 1 (
    echo [ERROR] Playwright installation verification failed
    pause
    exit /b 1
)

echo [SUCCESS] Playwright installation verified!
echo.
echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo You can now run your crawler service.
echo If you still encounter browser issues, please check:
echo 1. Antivirus software is not blocking browser executables
echo 2. Windows Defender exclusions for Playwright cache folder
echo 3. Sufficient disk space (browsers require ~500MB)
echo.
echo Playwright cache location: %USERPROFILE%\AppData\Local\ms-playwright
echo.
pause