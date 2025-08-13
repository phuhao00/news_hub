#!/usr/bin/env pwsh
# NewsHub Complete Startup Script
# Auto start all services: MinIO, MongoDB, Backend, Frontend, Crawler Service, MCP Servers

# Set console encoding to UTF-8 to prevent garbled characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "=== NewsHub Project Startup Script ===" -ForegroundColor Green
Write-Host "Starting all services..." -ForegroundColor Yellow

# Function to check if port is available
function Test-Port {
    param([int]$Port)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $true
    } catch {
        return $false
    }
}

# Function to wait for service to be ready
function Wait-ForService {
    param([int]$Port, [string]$ServiceName, [int]$MaxWaitSeconds = 30)
    Write-Host "Waiting for $ServiceName to be ready on port $Port..." -ForegroundColor Yellow
    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        if (Test-Port -Port $Port) {
            Write-Host "[SUCCESS] $ServiceName is ready!" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
        $waited += 2
    }
    Write-Host "[WARNING] $ServiceName not ready after $MaxWaitSeconds seconds" -ForegroundColor Yellow
    return $false
}

# 1. Start MinIO Docker Container
Write-Host "\n[1/5] Starting MinIO Docker Container..." -ForegroundColor Cyan
try {
    & .\start-minio.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] MinIO service started successfully" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] MinIO service failed to start" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] MinIO startup script execution failed: $_" -ForegroundColor Red
    exit 1
}

# 2. Start MongoDB Database
Write-Host "\n[2/5] Starting MongoDB Database..." -ForegroundColor Cyan
try {
    & .\init-database.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] MongoDB database started successfully" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] MongoDB database failed to start" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] MongoDB startup script execution failed: $_" -ForegroundColor Red
    exit 1
}

# 3. Start Local MCP Server
Write-Host "\n[3/7] Starting Local MCP Server..." -ForegroundColor Cyan
if (Test-Port -Port 8080) {
    Write-Host "[WARNING] Port 8080 is already in use, skipping Local MCP Server" -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd crawler-service; python local_mcp_server.py" -WindowStyle Normal
    Write-Host "[SUCCESS] Local MCP Server starting (Port: 8080)" -ForegroundColor Green
    Wait-ForService -Port 8080 -ServiceName "Local MCP Server" -MaxWaitSeconds 15
}

# 4. Start Browser MCP Server
Write-Host "\n[4/7] Starting Browser MCP Server..." -ForegroundColor Cyan
if (Test-Port -Port 3001) {
    Write-Host "[WARNING] Port 3001 is already in use, skipping Browser MCP Server" -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd crawler-service; python browser_mcp_server.py" -WindowStyle Normal
    Write-Host "[SUCCESS] Browser MCP Server starting (Port: 3001)" -ForegroundColor Green
    Wait-ForService -Port 3001 -ServiceName "Browser MCP Server" -MaxWaitSeconds 20
}

# 5. Start Backend Go Service
Write-Host "\n[5/7] Starting Backend Go Service..." -ForegroundColor Cyan
if (Test-Port -Port 8081) {
    Write-Host "[WARNING] Port 8081 is already in use, skipping Backend Service" -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd server; go run main.go" -WindowStyle Normal
    Write-Host "[SUCCESS] Backend service starting (Port: 8081)" -ForegroundColor Green
    Wait-ForService -Port 8081 -ServiceName "Backend Service" -MaxWaitSeconds 20
}

# 6. Start Frontend Next.js Service
Write-Host "\n[6/7] Starting Frontend Next.js Service..." -ForegroundColor Cyan
if (Test-Port -Port 3000) {
    Write-Host "[WARNING] Port 3000 is already in use, skipping Frontend Service" -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev" -WindowStyle Normal
    Write-Host "[SUCCESS] Frontend service starting (Port: 3000)" -ForegroundColor Green
    Wait-ForService -Port 3000 -ServiceName "Frontend Service" -MaxWaitSeconds 30
}

# 7. Start Crawler Python Service
Write-Host "\n[7/7] Starting Crawler Python Service..." -ForegroundColor Cyan
if (Test-Port -Port 8001) {
    Write-Host "[WARNING] Port 8001 is already in use, skipping Crawler Service" -ForegroundColor Yellow
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd crawler-service; python main.py" -WindowStyle Normal
    Write-Host "[SUCCESS] Crawler service starting (Port: 8001)" -ForegroundColor Green
    Wait-ForService -Port 8001 -ServiceName "Crawler Service" -MaxWaitSeconds 15
}

# Final service status check
Write-Host "\n=== Final Service Status Check ===" -ForegroundColor Green

$services = @(
    @{Name="MinIO"; Port=9000; URL="http://localhost:9001"},
    @{Name="MongoDB"; Port=27017; URL="mongodb://localhost:27017"},
    @{Name="Local MCP Server"; Port=8080; URL="http://localhost:8080"},
    @{Name="Browser MCP Server"; Port=3001; URL="http://localhost:3001"},
    @{Name="Backend API"; Port=8081; URL="http://localhost:8081"},
    @{Name="Frontend"; Port=3000; URL="http://localhost:3000"},
    @{Name="Crawler Service"; Port=8001; URL="http://localhost:8001"}
)

foreach ($service in $services) {
    if (Test-Port -Port $service.Port) {
        Write-Host "[SUCCESS] $($service.Name) - Running" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] $($service.Name) - Not Running" -ForegroundColor Red
    }
}

Write-Host "\n=== All Services Startup Complete! ===" -ForegroundColor Green
Write-Host "\n[INFO] Service Access Information:" -ForegroundColor White
Write-Host "- Frontend (Next.js):     http://localhost:3000" -ForegroundColor Cyan
Write-Host "- Backend API (Go):       http://localhost:8081" -ForegroundColor Cyan
Write-Host "- Crawler Service:        http://localhost:8001" -ForegroundColor Cyan
Write-Host "- Local MCP Server:       http://localhost:8080" -ForegroundColor Cyan
Write-Host "- Browser MCP Server:     http://localhost:3001" -ForegroundColor Cyan
Write-Host "- MinIO Console:          http://localhost:9001" -ForegroundColor Cyan
Write-Host "- MongoDB:                mongodb://localhost:27017" -ForegroundColor Cyan

Write-Host "\n[CREDENTIALS] Default Credentials:" -ForegroundColor White
Write-Host "- MinIO: minioadmin / minioadmin123" -ForegroundColor Yellow
Write-Host "- MongoDB: No authentication required" -ForegroundColor Yellow

Write-Host "\n[READY] NewsHub is ready to use!" -ForegroundColor Green
Write-Host "\n[TIPS] Tips:" -ForegroundColor White
Write-Host "- Use stop-all.ps1 to stop all services" -ForegroundColor Gray
Write-Host "- Check logs in respective terminal windows for troubleshooting" -ForegroundColor Gray
Write-Host "- MCP servers are now included for enhanced crawler functionality" -ForegroundColor Gray

Write-Host "\nPress any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")