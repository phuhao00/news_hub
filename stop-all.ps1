#!/usr/bin/env pwsh
# NewsHub Complete Stop Script
# Stop all services: Frontend, Backend, Crawler, MCP Servers, MinIO, MongoDB

# Set console encoding to UTF-8 to prevent garbled characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "=== NewsHub Project Stop Script ===" -ForegroundColor Red
Write-Host "Stopping all services..." -ForegroundColor Yellow

# Function to stop process by port
function Stop-ProcessByPort {
    param([int]$Port, [string]$ServiceName)
    try {
        $processes = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
        if ($processes) {
            $processes | Stop-Process -Force
            Write-Host "[SUCCESS] $ServiceName stopped" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[INFO] $ServiceName not running" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "Warning: Error stopping ${ServiceName}: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

# 1. Stop Frontend Next.js Service
Write-Host "\n[1/7] Stopping Frontend Next.js Service..." -ForegroundColor Cyan
Stop-ProcessByPort -Port 3000 -ServiceName "Frontend Service"

# 2. Stop Crawler Service
Write-Host "\n[2/7] Stopping Crawler Python Service..." -ForegroundColor Cyan
Stop-ProcessByPort -Port 8001 -ServiceName "Crawler Service"

# 3. Stop Backend Go Service
Write-Host "\n[3/7] Stopping Backend Go Service..." -ForegroundColor Cyan
Stop-ProcessByPort -Port 8081 -ServiceName "Backend Service"

# 4. Stop Browser MCP Server
Write-Host "\n[4/7] Stopping Browser MCP Server..." -ForegroundColor Cyan
Stop-ProcessByPort -Port 3001 -ServiceName "Browser MCP Server"

# 5. Stop Local MCP Server
Write-Host "\n[5/7] Stopping Local MCP Server..." -ForegroundColor Cyan
Stop-ProcessByPort -Port 8080 -ServiceName "Local MCP Server"

# 6. Stop MinIO Docker Container
Write-Host "\n[6/7] Stopping MinIO Docker Container..." -ForegroundColor Cyan
try {
    & .\stop-minio.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] MinIO service stopped" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] MinIO stop script completed" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARNING] MinIO stop script execution failed: $_" -ForegroundColor Yellow
}

# 7. Stop MongoDB Docker Container
Write-Host "\n[7/7] Stopping MongoDB Docker Container..." -ForegroundColor Cyan
try {
    $mongoContainer = docker ps -q --filter "name=mongodb"
    if ($mongoContainer) {
        docker stop $mongoContainer | Out-Null
        Write-Host "[SUCCESS] MongoDB container stopped" -ForegroundColor Green
    } else {
        Write-Host "[INFO] MongoDB container not running" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARNING] Error stopping MongoDB container: $_" -ForegroundColor Yellow
}

# Clean up remaining processes
Write-Host "\n[CLEANUP] Cleaning up remaining processes..." -ForegroundColor Cyan
try {
    # Force stop possible remaining processes
    Get-Process -Name "go", "node", "python" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "go|node|python" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[SUCCESS] Process cleanup completed" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Error during process cleanup: $_" -ForegroundColor Yellow
}

Write-Host "\n=== [STOPPED] All Services Stopped! ===" -ForegroundColor Red
Write-Host "\n[SUMMARY] Stopped Services:" -ForegroundColor White
Write-Host "• Frontend Service (Next.js) - Port 3000" -ForegroundColor Gray
Write-Host "• Backend Service (Go) - Port 8081" -ForegroundColor Gray
Write-Host "• Crawler Service (Python) - Port 8001" -ForegroundColor Gray
Write-Host "• Local MCP Server - Port 8080" -ForegroundColor Gray
Write-Host "• Browser MCP Server - Port 3001" -ForegroundColor Gray
Write-Host "• MinIO Storage Service" -ForegroundColor Gray
Write-Host "• MongoDB Database Service" -ForegroundColor Gray

Write-Host "\n[TIPS] Tips:" -ForegroundColor White
Write-Host "• Use start-all.ps1 to restart all services" -ForegroundColor Gray
Write-Host "• For individual service startup, check respective startup scripts" -ForegroundColor Gray
Write-Host "• MCP servers are now included in startup/stop process" -ForegroundColor Gray

Write-Host "\nPress any key to exit..." -ForegroundColor White
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")