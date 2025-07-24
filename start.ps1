#!/usr/bin/env pwsh
# NewsHub 一键启动脚本
# 启动前端、后端和爬虫服务

Write-Host "=== NewsHub 一键启动脚本 ===" -ForegroundColor Green
Write-Host "正在启动 NewsHub 应用的所有服务..." -ForegroundColor Yellow

# 检查是否在正确的目录
if (-not (Test-Path "package.json")) {
    Write-Host "错误: 请在 NewsHub 项目根目录下运行此脚本" -ForegroundColor Red
    exit 1
}

# 函数：检查端口是否被占用
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

# 函数：等待服务启动
function Wait-ForService {
    param([int]$Port, [string]$ServiceName, [int]$TimeoutSeconds = 30)
    
    Write-Host "等待 $ServiceName 启动 (端口 $Port)..." -ForegroundColor Yellow
    $elapsed = 0
    
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-Port -Port $Port) {
            Write-Host "✓ $ServiceName 已启动" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    
    Write-Host "✗ $ServiceName 启动超时" -ForegroundColor Red
    return $false
}

# 检查并安装前端依赖
Write-Host "`n1. 检查前端依赖..." -ForegroundColor Cyan
if (-not (Test-Path "node_modules")) {
    Write-Host "安装前端依赖..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "前端依赖安装失败" -ForegroundColor Red
        exit 1
    }
}

# 检查并安装爬虫服务依赖
Write-Host "`n2. 检查爬虫服务依赖..." -ForegroundColor Cyan
Push-Location crawler-service
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "创建Python虚拟环境..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    # 激活虚拟环境并安装依赖
    & ".venv\Scripts\Activate.ps1"
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "爬虫服务依赖安装失败" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}

# 检查Go环境和后端依赖
Write-Host "`n3. 检查后端服务..." -ForegroundColor Cyan
Push-Location server
try {
    go mod tidy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "后端依赖检查失败" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}

# 启动服务
Write-Host "`n4. 启动服务..." -ForegroundColor Cyan

# 启动后端服务 (端口 8082)
Write-Host "启动后端服务..." -ForegroundColor Yellow
Push-Location server
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    go run main.go
}
Pop-Location

# 等待后端服务启动
if (-not (Wait-ForService -Port 8082 -ServiceName "后端服务")) {
    Write-Host "后端服务启动失败，停止所有服务" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

# 启动爬虫服务 (端口 8001)
Write-Host "启动爬虫服务..." -ForegroundColor Yellow
Push-Location crawler-service
$crawlerJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".venv\Scripts\Activate.ps1"
    python main.py
}
Pop-Location

# 等待爬虫服务启动
if (-not (Wait-ForService -Port 8001 -ServiceName "爬虫服务")) {
    Write-Host "爬虫服务启动失败，停止所有服务" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

# 启动前端服务 (端口 3001)
Write-Host "启动前端服务..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    npm run dev
}

# 等待前端服务启动
if (-not (Wait-ForService -Port 3001 -ServiceName "前端服务")) {
    Write-Host "前端服务启动失败，停止所有服务" -ForegroundColor Red
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    exit 1
}

Write-Host "`n=== 所有服务启动成功! ===" -ForegroundColor Green
Write-Host "前端服务: http://localhost:3001" -ForegroundColor Cyan
Write-Host "后端服务: http://localhost:8082" -ForegroundColor Cyan
Write-Host "爬虫服务: http://localhost:8001" -ForegroundColor Cyan
Write-Host "`n按 Ctrl+C 停止所有服务" -ForegroundColor Yellow

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`n正在停止所有服务..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    Write-Host "所有服务已停止" -ForegroundColor Green
}