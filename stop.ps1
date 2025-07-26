# NewsHub 项目停止脚本 (PowerShell)

Write-Host "🛑 正在停止 NewsHub 项目..." -ForegroundColor Yellow

# 停止Go后端进程
Write-Host "🚀 停止后端服务..." -ForegroundColor Cyan
$goProcesses = Get-Process -Name "go" -ErrorAction SilentlyContinue
if ($goProcesses) {
    $goProcesses | Stop-Process -Force
    Write-Host "✅ 后端服务已停止" -ForegroundColor Green
} else {
    Write-Host "✅ 未找到运行的后端服务" -ForegroundColor Green
}

# 停止Python爬虫进程
Write-Host "🕷️ 停止爬虫服务..." -ForegroundColor Cyan
$pythonProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*main.py*" }
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "✅ 爬虫服务已停止" -ForegroundColor Green
} else {
    Write-Host "✅ 未找到运行的爬虫服务" -ForegroundColor Green
}

# 停止Node.js前端进程
Write-Host "🌐 停止前端服务..." -ForegroundColor Cyan
$nodeProcesses = Get-Process -Name "node*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*next*" -or $_.CommandLine -like "*npm*" }
if ($nodeProcesses) {
    $nodeProcesses | Stop-Process -Force
    Write-Host "✅ 前端服务已停止" -ForegroundColor Green
} else {
    Write-Host "✅ 未找到运行的前端服务" -ForegroundColor Green
}

# 停止占用特定端口的进程
$ports = @(3000, 8080, 8001)
foreach ($port in $ports) {
    try {
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            $processId = $connection.OwningProcess
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "🔧 停止占用端口 $port 的进程: $($process.Name) (PID: $processId)" -ForegroundColor Cyan
                Stop-Process -Id $processId -Force
            }
        }
    } catch {
        # 忽略错误，继续处理下一个端口
    }
}

# 清理可能的残留PowerShell窗口
Write-Host "🔧 清理PowerShell窗口..." -ForegroundColor Cyan
$powershellProcesses = Get-Process -Name "powershell*" -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -like "*go run main.go*" -or 
    $_.CommandLine -like "*uvicorn*" -or 
    $_.CommandLine -like "*npm run dev*" 
}
if ($powershellProcesses) {
    $powershellProcesses | Stop-Process -Force
    Write-Host "✅ PowerShell服务窗口已清理" -ForegroundColor Green
}

Write-Host ""
Write-Host "🎉 NewsHub 项目已停止！" -ForegroundColor Green
Write-Host ""
Write-Host "📋 清理完成:" -ForegroundColor Yellow
Write-Host "  ✅ 后端服务已停止" -ForegroundColor White
Write-Host "  ✅ 爬虫服务已停止" -ForegroundColor White
Write-Host "  ✅ 前端服务已停止" -ForegroundColor White
Write-Host "  ✅ 服务进程已清理" -ForegroundColor White
Write-Host ""
Write-Host "💡 提示: 使用 '.\start.ps1' 重新启动所有服务" -ForegroundColor White
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 