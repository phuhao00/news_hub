#!/usr/bin/env pwsh
# 停止MinIO Docker服务

Write-Host "正在停止MinIO Docker服务..." -ForegroundColor Yellow

# 检查Docker是否运行
try {
    docker version | Out-Null
    Write-Host "Docker服务正在运行" -ForegroundColor Green
} catch {
    Write-Host "错误: Docker服务未运行" -ForegroundColor Red
    exit 1
}

# 停止MinIO服务
try {
    Write-Host "停止MinIO容器..." -ForegroundColor Yellow
    docker-compose -f docker-compose.minio.yml down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MinIO服务已成功停止!" -ForegroundColor Green
    } else {
        Write-Host "停止MinIO服务时发生错误" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "停止MinIO服务时发生错误: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 可选：清理未使用的容器和网络
$cleanup = Read-Host "是否要清理未使用的Docker资源? (y/N)"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Write-Host "清理未使用的Docker资源..." -ForegroundColor Yellow
    docker system prune -f
    Write-Host "清理完成!" -ForegroundColor Green
}

Write-Host "MinIO服务已完全停止!" -ForegroundColor Green