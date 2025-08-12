#!/usr/bin/env pwsh
# 启动MinIO Docker服务

Write-Host "正在启动MinIO Docker服务..." -ForegroundColor Green

# 检查Docker是否运行
try {
    docker version | Out-Null
    Write-Host "Docker服务正在运行" -ForegroundColor Green
} catch {
    Write-Host "错误: Docker服务未运行，请先启动Docker Desktop" -ForegroundColor Red
    exit 1
}

# 启动MinIO服务
try {
    Write-Host "启动MinIO容器..." -ForegroundColor Yellow
    docker-compose -f docker-compose.minio.yml up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MinIO服务启动成功!" -ForegroundColor Green
        Write-Host "MinIO API地址: http://localhost:9000" -ForegroundColor Cyan
        Write-Host "MinIO控制台地址: http://localhost:9001" -ForegroundColor Cyan
        Write-Host "用户名: minioadmin" -ForegroundColor Cyan
        Write-Host "密码: minioadmin123" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "等待MinIO服务完全启动..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        
        # 检查服务状态
        Write-Host "检查MinIO服务状态..." -ForegroundColor Yellow
        docker-compose -f docker-compose.minio.yml ps
    } else {
        Write-Host "MinIO服务启动失败" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "启动MinIO服务时发生错误: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "MinIO服务已成功启动并运行!" -ForegroundColor Green