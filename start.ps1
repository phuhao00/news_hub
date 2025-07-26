#!/usr/bin/env pwsh
# NewsHub One-Click Startup Script
# Start frontend, backend and crawler services

Write-Host "=== NewsHub One-Click Startup Script ===" -ForegroundColor Green
Write-Host "Starting all NewsHub application services..." -ForegroundColor Yellow

# Check if running in correct directory
if (-not (Test-Path "package.json")) {
    Write-Host "Error: Please run this script in NewsHub project root directory" -ForegroundColor Red
    exit 1
}

# Function: Check if port is occupied
function Test-Port {
    param([int]$Port)
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        return $connection
    }
    catch {
        return $false
    }
}

# Function: Wait for service to start
function Wait-ForService {
    param([int]$Port, [string]$ServiceName, [int]$TimeoutSeconds = 30)
    
    Write-Host "Waiting for $ServiceName to start (port $Port)..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-Port -Port $Port) {
            Write-Host "✓ $ServiceName started" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    
    Write-Host "✗ $ServiceName startup timeout" -ForegroundColor Red
    return $false
}

# Check and install frontend dependencies
Write-Host "`n1. Checking frontend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Frontend dependencies installation failed" -ForegroundColor Red
        exit 1
    }
}

# Check and install crawler service dependencies
Write-Host "`n2. Checking crawler service dependencies..." -ForegroundColor Cyan
Push-Location crawler-service
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    # Activate virtual environment and install dependencies
    & ".venv\Scripts\Activate.ps1"
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Crawler service dependencies installation failed" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}

# Check Go environment and backend dependencies
Write-Host "`n3. Checking backend service..." -ForegroundColor Cyan
Push-Location server
try {
    go mod tidy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Backend dependencies check failed" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}

# Start services
Write-Host "`n4. Starting services..." -ForegroundColor Cyan

# Start backend service (port 8080 - from config.json)
Write-Host "Starting backend service..." -ForegroundColor Yellow
Push-Location server
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    go run main.go
}
Pop-Location

# Wait for backend service to start
if (-not (Wait-ForService -Port 8080 -ServiceName "Backend Service")) {
    Write-Host "Backend service startup failed, stopping all services" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

# Start crawler service (port 8001 - from config.json)
Write-Host "Starting crawler service..." -ForegroundColor Yellow
Push-Location crawler-service
$crawlerJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".venv\Scripts\Activate.ps1"
    python main.py
}
Pop-Location

# Wait for crawler service to start
if (-not (Wait-ForService -Port 8001 -ServiceName "Crawler Service")) {
    Write-Host "Crawler service startup failed, stopping all services" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

# Start frontend service (port 3000 - from config.json)
Write-Host "Starting frontend service..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    npm run dev
}

# Wait for frontend service to start
if (-not (Wait-ForService -Port 3000 -ServiceName "Frontend Service")) {
    Write-Host "Frontend service startup failed, stopping all services" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

Write-Host "`n=== All services started successfully! ===" -ForegroundColor Green
Write-Host "Frontend service: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend service: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Crawler service: http://localhost:8001" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop all services" -ForegroundColor Yellow

# Wait for user interruption
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`nStopping all services..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    Write-Host "All services stopped" -ForegroundColor Green
}