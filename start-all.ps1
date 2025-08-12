#!/usr/bin/env pwsh
# NewsHub 完整启动脚本
# 自动启动所有服务：MinIO、MongoDB、后端、前端、爬虫服务

Write-Host "=== NewsHub 项目启动脚本 ===" -ForegroundColor Green
Write-Host "正在启动所有服务..." -ForegroundColor Yellow

# 1. 启动 MinIO Docker 容器
Write-Host "\n[1/5] 启动 MinIO Docker 容器..." -ForegroundColor Cyan
try {
    & .\start-minio.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ MinIO 服务启动成功" -ForegroundColor Green
    } else {
        Write-Host "❌ MinIO 服务启动失败" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ MinIO 启动脚本执行失败: $_" -ForegroundColor Red
    exit 1
}

# 2. 启动 MongoDB 数据库
Write-Host "\n[2/5] 启动 MongoDB 数据库..." -ForegroundColor Cyan
try {
    & .\init-database.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ MongoDB 数据库启动成功" -ForegroundColor Green
    } else {
        Write-Host "❌ MongoDB 数据库启动失败" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ MongoDB 启动脚本执行失败: $_" -ForegroundColor Red
    exit 1
}

# 3. 启动后端 Go 服务
Write-Host "\n[3/5] 启动后端 Go 服务..." -ForegroundColor Cyan
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd server; go run main.go" -WindowStyle Normal
Write-Host "✅ 后端服务启动中 (端口: 8081)" -ForegroundColor Green

# 等待后端服务启动
Write-Host "等待后端服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 4. 启动前端 Next.js 服务
Write-Host "\n[4/5] 启动前端 Next.js 服务..." -ForegroundColor Cyan
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "npm run dev" -WindowStyle Normal
Write-Host "✅ 前端服务启动中 (端口: 3000)" -ForegroundColor Green

# 等待前端服务启动
Write-Host "等待前端服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 5. 启动爬虫 Python 服务
Write-Host "\n[5/5] 启动爬虫 Python 服务..." -ForegroundColor Cyan
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd crawler-service; python main.py" -WindowStyle Normal
Write-Host "✅ 爬虫服务启动中 (端口: 8001)" -ForegroundColor Green

# 等待所有服务完全启动
Write-Host "\n等待所有服务完全启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "\n=== 🎉 所有服务启动完成! ===" -ForegroundColor Green
Write-Host "\n📋 服务访问地址:" -ForegroundColor White
Write-Host "  🌐 前端应用:     http://localhost:3000" -ForegroundColor Cyan
Write-Host "  🔧 后端API:      http://localhost:8081" -ForegroundColor Cyan
Write-Host "  🕷️  爬虫服务:     http://localhost:8001" -ForegroundColor Cyan
Write-Host "  📦 MinIO控制台:  http://localhost:9001" -ForegroundColor Cyan
Write-Host "  🗄️  MongoDB:      mongodb://localhost:27015" -ForegroundColor Cyan

Write-Host "\n📝 MinIO 登录信息:" -ForegroundColor White
Write-Host "  用户名: minioadmin" -ForegroundColor Yellow
Write-Host "  密码:   minioadmin123" -ForegroundColor Yellow

Write-Host "\n💡 提示:" -ForegroundColor White
Write-Host "  - 使用 ./stop-all.ps1 停止所有服务" -ForegroundColor Gray
Write-Host "  - 查看各服务的终端窗口了解运行状态" -ForegroundColor Gray
Write-Host "  - 如需重启某个服务，请先停止对应进程" -ForegroundColor Gray

Write-Host "\n按任意键退出..." -ForegroundColor White
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")