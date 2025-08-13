#!/usr/bin/env pwsh
# Stop MinIO Docker Service

Write-Host "Stopping MinIO Docker service..." -ForegroundColor Yellow

# Check if Docker is running
try {
    docker version | Out-Null
    Write-Host "Docker service is running" -ForegroundColor Green
} catch {
    Write-Host "Error: Docker service is not running" -ForegroundColor Red
    exit 1
}

# Stop MinIO service
try {
    Write-Host "Stopping MinIO container..." -ForegroundColor Yellow
    docker-compose -f docker-compose.minio.yml down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MinIO service stopped successfully!" -ForegroundColor Green
    } else {
        Write-Host "Error occurred while stopping MinIO service" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error occurred while stopping MinIO service: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Optional: Clean up unused containers and networks
$cleanup = Read-Host "Do you want to clean up unused Docker resources? (y/N)"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Write-Host "Cleaning up unused Docker resources..." -ForegroundColor Yellow
    docker system prune -f
    Write-Host "Cleanup completed!" -ForegroundColor Green
}

Write-Host "MinIO service completely stopped!" -ForegroundColor Green