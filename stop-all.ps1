#!/usr/bin/env pwsh
# NewsHub 完整停止脚本
# 停止所有服务：前端、后端、爬虫服务、MinIO、MongoDB

Write-Host "=== NewsHub 项目停止脚本 ===" -ForegroundColor Red
Write-Host "正在停止所有服务..." -ForegroundColor Yellow

# 1. 停止 Node.js 进程 (前端)
Write-Host "\n[1/5] 停止前端 Next.js 服务..." -ForegroundColor Cyan
try {
    $nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
    if ($nodeProcesses) {
        $nodeProcesses | Stop-Process -Force
        Write-Host "✅ 前端服务已停止" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  前端服务未运行" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  停止前端服务时出错: $_" -ForegroundColor Yellow
}

# 2. 停止 Go 进程 (后端)
Write-Host "\n[2/5] 停止后端 Go 服务..." -ForegroundColor Cyan
try {
    # 查找监听8081端口的进程
    $goProcesses = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
    if ($goProcesses) {
        $goProcesses | Stop-Process -Force
        Write-Host "✅ 后端服务已停止" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  后端服务未运行" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  停止后端服务时出错: $_" -ForegroundColor Yellow
}

# 3. 停止 Python 进程 (爬虫服务)
Write-Host "\n[3/5] 停止爬虫 Python 服务..." -ForegroundColor Cyan
try {
    # 查找监听8001端口的进程
    $pythonProcesses = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
    if ($pythonProcesses) {
        $pythonProcesses | Stop-Process -Force
        Write-Host "✅ 爬虫服务已停止" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  爬虫服务未运行" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  停止爬虫服务时出错: $_" -ForegroundColor Yellow
}

# 4. 停止 MinIO Docker 容器
Write-Host "\n[4/5] 停止 MinIO Docker 容器..." -ForegroundColor Cyan
try {
    & .\stop-minio.ps1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ MinIO 服务已停止" -ForegroundColor Green
    } else {
        Write-Host "⚠️  MinIO 停止脚本执行完成" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  MinIO 停止脚本执行失败: $_" -ForegroundColor Yellow
}

# 5. 停止 MongoDB Docker 容器
Write-Host "\n[5/5] 停止 MongoDB Docker 容器..." -ForegroundColor Cyan
try {
    $mongoContainer = docker ps -q --filter "name=mongodb"
    if ($mongoContainer) {
        docker stop $mongoContainer | Out-Null
        Write-Host "✅ MongoDB 容器已停止" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  MongoDB 容器未运行" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  停止 MongoDB 容器时出错: $_" -ForegroundColor Yellow
}

# 清理可能残留的进程
Write-Host "\n🧹 清理残留进程..." -ForegroundColor Cyan
try {
    # 强制停止可能的残留进程
    Get-Process -Name "go", "node", "python" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match "go|node|python" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "✅ 进程清理完成" -ForegroundColor Green
} catch {
    Write-Host "⚠️  进程清理时出错: $_" -ForegroundColor Yellow
}

Write-Host "\n=== 🛑 所有服务已停止! ===" -ForegroundColor Red
Write-Host "\n💡 提示:" -ForegroundColor White
Write-Host "  - 使用 ./start-all.ps1 重新启动所有服务" -ForegroundColor Gray
Write-Host "  - 如需单独启动某个服务，请查看相应的启动脚本" -ForegroundColor Gray

Write-Host "\n按任意键退出..." -ForegroundColor White
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")