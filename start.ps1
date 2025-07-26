#!/usr/bin/env pwsh
# NewsHub 项目启动脚本 (PowerShell)
Write-Host "🚀 正在启动 NewsHub 项目..." -ForegroundColor Green

# 检查必要的工具
Write-Host "📋 检查系统环境..." -ForegroundColor Yellow

# 检查 Node.js
if (!(Get-Command "node" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 未找到 Node.js，请先安装 Node.js" -ForegroundColor Red
    exit 1
}

# 检查 Go
if (!(Get-Command "go" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 未找到 Go，请先安装 Go" -ForegroundColor Red
    exit 1
}

# 检查 Python
if (!(Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 未找到 Python，请先安装 Python" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 系统环境检查完成" -ForegroundColor Green

# 启动 MongoDB (如果没有运行)
Write-Host "🗄️ 启动 MongoDB..." -ForegroundColor Yellow
$mongoProcess = Get-Process -Name "mongod" -ErrorAction SilentlyContinue
if (-not $mongoProcess) {
    try {
        Start-Process "mongod" -ArgumentList "--dbpath", ".\mongodb_data" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "✅ MongoDB 已启动" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ MongoDB 启动失败，请手动启动 MongoDB" -ForegroundColor Yellow
    }
} else {
    Write-Host "✅ MongoDB 已在运行" -ForegroundColor Green
}

# 安装前端依赖
Write-Host "📦 安装前端依赖..." -ForegroundColor Yellow
if (Test-Path "package.json") {
    npm install
    Write-Host "✅ 前端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到 package.json" -ForegroundColor Red
}

# 安装后端依赖
Write-Host "📦 安装后端依赖..." -ForegroundColor Yellow
Set-Location "server"
if (Test-Path "go.mod") {
    go mod tidy
    Write-Host "✅ 后端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到 go.mod" -ForegroundColor Red
}
Set-Location ".."

# 安装爬虫服务依赖
Write-Host "📦 安装爬虫服务依赖..." -ForegroundColor Yellow
Set-Location "crawler-service"
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    Write-Host "✅ 爬虫服务依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到 requirements.txt" -ForegroundColor Red
}
Set-Location ".."

# 初始化数据库
Write-Host "🗄️ 数据库初始化..." -ForegroundColor Yellow
if (Test-Path "init-mongo.js") {
    Write-Host "💡 数据库初始化脚本存在，如需初始化请手动运行" -ForegroundColor Yellow
}

Write-Host "🎉 准备工作完成，正在启动服务..." -ForegroundColor Green
Write-Host ""

# 启动后端服务
Write-Host "🚀 启动后端服务 (端口: 8082)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd server; go run main.go" -WindowStyle Normal

Start-Sleep -Seconds 2

# 启动爬虫服务
Write-Host "🕷️ 启动爬虫服务 (端口: 8001)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd crawler-service; python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload" -WindowStyle Normal

Start-Sleep -Seconds 3

# 启动前端服务
Write-Host "🌐 启动前端服务 (端口: 3001)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev" -WindowStyle Normal

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "🎉 NewsHub 项目启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "📊 服务地址:" -ForegroundColor Yellow
Write-Host "  前端应用: http://localhost:3001" -ForegroundColor White
Write-Host "  后端API: http://localhost:8082" -ForegroundColor White
Write-Host "  爬虫服务: http://localhost:8001" -ForegroundColor White
Write-Host "  API文档: http://localhost:8001/docs" -ForegroundColor White
Write-Host ""
Write-Host "🔧 系统监控:" -ForegroundColor Yellow
Write-Host "  健康检查: http://localhost:8082/health" -ForegroundColor White
Write-Host "  系统指标: http://localhost:8082/metrics" -ForegroundColor White
Write-Host ""
Write-Host "⭐ 开始使用 NewsHub 智能内容管理平台吧！" -ForegroundColor Green
Write-Host ""

# 等待一下然后打开浏览器
Start-Sleep -Seconds 3
try {
    Start-Process "http://localhost:3001"
    Write-Host "🌐 已在浏览器中打开 NewsHub 应用" -ForegroundColor Green
} catch {
    Write-Host "💡 请手动在浏览器中访问: http://localhost:3001" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')