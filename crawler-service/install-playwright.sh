#!/bin/bash

set -e  # Exit on any error

echo "========================================"
echo "Playwright Browser Installation Script"
echo "========================================"
echo

echo "[INFO] Starting Playwright browser installation..."
echo

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[ERROR] Python is not installed or not in PATH"
    echo "Please install Python first:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip"
    echo "  CentOS/RHEL: sudo yum install python3 python3-pip"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    echo "  Arch: sudo pacman -S python python-pip"
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
fi

echo "[INFO] Python is available: $($PYTHON_CMD --version)"
echo

# Check if pip is available
if ! command -v $PIP_CMD &> /dev/null; then
    echo "[ERROR] pip is not available"
    echo "Please install pip:"
    echo "  Ubuntu/Debian: sudo apt install python3-pip"
    echo "  CentOS/RHEL: sudo yum install python3-pip"
    exit 1
fi

echo "[INFO] pip is available: $($PIP_CMD --version)"
echo

# Install/upgrade playwright
echo "[INFO] Installing/upgrading Playwright..."
$PIP_CMD install --upgrade playwright
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Playwright"
    echo "[INFO] Trying with --user flag..."
    $PIP_CMD install --user --upgrade playwright
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install Playwright with --user flag"
        exit 1
    fi
fi

echo "[INFO] Playwright package installed successfully"
echo

# Install Playwright browsers
echo "[INFO] Installing Playwright browsers (this may take several minutes)..."
echo "[INFO] Downloading Chromium, Firefox, and WebKit browsers..."
playwright install
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Playwright browsers"
    echo "[INFO] Trying alternative installation method..."
    $PYTHON_CMD -m playwright install
    if [ $? -ne 0 ]; then
        echo "[ERROR] Alternative installation also failed"
        echo "[INFO] Please check your internet connection and try again"
        exit 1
    fi
fi

echo
echo "[SUCCESS] Playwright browsers installed successfully!"
echo

# Install system dependencies
echo "[INFO] Installing system dependencies..."
playwright install-deps
if [ $? -ne 0 ]; then
    echo "[WARNING] Some system dependencies might not be installed"
    echo "[INFO] You might need to run this script with sudo for system dependencies"
    echo "[INFO] Or install dependencies manually:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2"
fi

echo
echo "[INFO] Verifying installation..."
echo

# Test Playwright installation
echo "[INFO] Testing Playwright installation..."
$PYTHON_CMD -c "from playwright.sync_api import sync_playwright; print('Playwright import successful')"
if [ $? -ne 0 ]; then
    echo "[ERROR] Playwright installation verification failed"
    exit 1
fi

echo "[SUCCESS] Playwright installation verified!"
echo
echo "========================================"
echo "Installation completed successfully!"
echo "========================================"
echo
echo "You can now run your crawler service."
echo "If you still encounter browser issues, please check:"
echo "1. System dependencies are installed (run: playwright install-deps)"
echo "2. Sufficient disk space (browsers require ~500MB)"
echo "3. No conflicting browser processes running"
echo
echo "Playwright cache location: ~/.cache/ms-playwright"
echo
echo "To make this script executable, run: chmod +x install-playwright.sh"
echo