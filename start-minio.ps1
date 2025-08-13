#!/usr/bin/env pwsh
# Start MinIO Docker Service

Write-Host "Starting MinIO Docker service..." -ForegroundColor Green

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "Docker service is running" -ForegroundColor Green
} catch {
    Write-Host "Error: Docker service is not running, please start Docker Desktop first" -ForegroundColor Red
    exit 1
}

# Start MinIO service
try {
    Write-Host "Starting MinIO container..." -ForegroundColor Yellow
    docker-compose -f docker-compose.minio.yml up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MinIO service started successfully!" -ForegroundColor Green
        Write-Host "MinIO API address: http://localhost:9000" -ForegroundColor Cyan
        Write-Host "MinIO console address: http://localhost:9001" -ForegroundColor Cyan
        Write-Host "Username: minioadmin" -ForegroundColor Cyan
        Write-Host "Password: minioadmin123" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Waiting for MinIO service to fully start..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        
        # Check service status
        Write-Host "Checking MinIO service status..." -ForegroundColor Yellow
        docker-compose -f docker-compose.minio.yml ps
    } else {
        Write-Host "MinIO service startup failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error occurred while starting MinIO service: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "MinIO service has been successfully started and is running!" -ForegroundColor Green