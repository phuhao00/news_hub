jiancianc#!/usr/bin/env pwsh
# NewsHub 项目自动安装脚本 (PowerShell)
# 自动检测环境、安装依赖、配置服务

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "=== NewsHub 项目自动安装脚本 ===" -ForegroundColor Green
Write-Host "正在检查系统环境并安装依赖..." -ForegroundColor Yellow
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[警告] 建议以管理员权限运行此脚本以获得最佳体验" -ForegroundColor Yellow
    Write-Host "某些功能可能需要管理员权限才能正常工作" -ForegroundColor Yellow
    Write-Host ""
}

# 函数：检查命令是否存在
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# 函数：检查端口是否可用
function Test-Port {
    param([int]$Port)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $false  # 端口被占用
    } catch {
        return $true   # 端口可用
    }
}

# 函数：安装 Chocolatey (Windows 包管理器)
function Install-Chocolatey {
    if (-not (Test-Command "choco")) {
        Write-Host "[1/7] 安装 Chocolatey 包管理器..." -ForegroundColor Cyan
        try {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            Write-Host "[SUCCESS] Chocolatey 安装成功" -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Chocolatey 安装失败: $_" -ForegroundColor Red
            Write-Host "请手动安装 Chocolatey 或使用其他方式安装依赖" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[SUCCESS] Chocolatey 已安装" -ForegroundColor Green
    }
}

# 函数：安装 Node.js
function Install-NodeJS {
    Write-Host "[2/7] 检查 Node.js..." -ForegroundColor Cyan
    if (-not (Test-Command "node")) {
        Write-Host "正在安装 Node.js..." -ForegroundColor Yellow
        if (Test-Command "choco") {
            choco install nodejs -y
        } else {
            Write-Host "请手动安装 Node.js: https://nodejs.org/" -ForegroundColor Red
            Write-Host "推荐版本: 18.x LTS 或更高" -ForegroundColor Yellow
            return $false
        }
    } else {
        $nodeVersion = node --version
        Write-Host "[SUCCESS] Node.js 已安装: $nodeVersion" -ForegroundColor Green
    }
    return $true
}

# 函数：安装 Python
function Install-Python {
    Write-Host "[3/7] 检查 Python..." -ForegroundColor Cyan
    if (-not (Test-Command "python")) {
        Write-Host "正在安装 Python..." -ForegroundColor Yellow
        if (Test-Command "choco") {
            choco install python -y
        } else {
            Write-Host "请手动安装 Python: https://www.python.org/downloads/" -ForegroundColor Red
            Write-Host "推荐版本: 3.9 或更高" -ForegroundColor Yellow
            return $false
        }
    } else {
        $pythonVersion = python --version
        Write-Host "[SUCCESS] Python 已安装: $pythonVersion" -ForegroundColor Green
    }
    return $true
}

# 函数：安装 Go
function Install-Go {
    Write-Host "[4/7] 检查 Go..." -ForegroundColor Cyan
    if (-not (Test-Command "go")) {
        Write-Host "正在安装 Go..." -ForegroundColor Yellow
        if (Test-Command "choco") {
            choco install golang -y
        } else {
            Write-Host "请手动安装 Go: https://golang.org/dl/" -ForegroundColor Red
            Write-Host "推荐版本: 1.19 或更高" -ForegroundColor Yellow
            return $false
        }
    } else {
        $goVersion = go version
        Write-Host "[SUCCESS] Go 已安装: $goVersion" -ForegroundColor Green
    }
    return $true
}

# 函数：安装 MongoDB
function Install-MongoDB {
    Write-Host "[5/7] 检查 MongoDB..." -ForegroundColor Cyan
    if (-not (Test-Command "mongod")) {
        Write-Host "正在安装 MongoDB..." -ForegroundColor Yellow
        if (Test-Command "choco") {
            choco install mongodb -y
        } else {
            Write-Host "请手动安装 MongoDB: https://www.mongodb.com/try/download/community" -ForegroundColor Red
            Write-Host "推荐版本: 6.0 或更高" -ForegroundColor Yellow
            return $false
        }
    } else {
        Write-Host "[SUCCESS] MongoDB 已安装" -ForegroundColor Green
    }
    return $true
}

# 函数：安装 Docker (可选)
function Install-Docker {
    Write-Host "[6/7] 检查 Docker (可选)..." -ForegroundColor Cyan
    if (-not (Test-Command "docker")) {
        Write-Host "Docker 未安装，将跳过 MinIO 容器部署" -ForegroundColor Yellow
        Write-Host "如需使用 MinIO，请手动安装 Docker Desktop" -ForegroundColor Yellow
        return $false
    } else {
        $dockerVersion = docker --version
        Write-Host "[SUCCESS] Docker 已安装: $dockerVersion" -ForegroundColor Green
        return $true
    }
}

# 函数：安装项目依赖
function Install-ProjectDependencies {
    Write-Host "[7/7] 安装项目依赖..." -ForegroundColor Cyan
    
    # 检查项目目录
    if (-not (Test-Path "package.json")) {
        Write-Host "[ERROR] 未找到 package.json，请确保在项目根目录运行此脚本" -ForegroundColor Red
        return $false
    }
    
    # 安装前端依赖
    Write-Host "安装前端依赖..." -ForegroundColor Yellow
    try {
        npm install
        Write-Host "[SUCCESS] 前端依赖安装完成" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] 前端依赖安装失败: $_" -ForegroundColor Red
        return $false
    }
    
    # 安装后端依赖
    Write-Host "安装后端依赖..." -ForegroundColor Yellow
    try {
        Set-Location "server"
        go mod tidy
        Set-Location ".."
        Write-Host "[SUCCESS] 后端依赖安装完成" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] 后端依赖安装失败: $_" -ForegroundColor Red
        Set-Location ".."
        return $false
    }
    
    # 安装爬虫服务依赖
    Write-Host "安装爬虫服务依赖..." -ForegroundColor Yellow
    try {
        Set-Location "crawler-service"
        pip install -r requirements.txt
        Set-Location ".."
        Write-Host "[SUCCESS] 爬虫服务依赖安装完成" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] 爬虫服务依赖安装失败: $_" -ForegroundColor Red
        Set-Location ".."
        return $false
    }
    
    # 安装根目录 Python 依赖
    Write-Host "安装根目录 Python 依赖..." -ForegroundColor Yellow
    try {
        pip install -r requirements.txt
        Write-Host "[SUCCESS] 根目录 Python 依赖安装完成" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] 根目录 Python 依赖安装失败，但不影响主要功能" -ForegroundColor Yellow
    }
    
    return $true
}

# 函数：检查端口占用
function Check-Ports {
    Write-Host "检查端口占用情况..." -ForegroundColor Cyan
    $ports = @(3000, 8081, 8001, 9000, 9001, 27017, 8080, 3001)
    $occupiedPorts = @()
    
    foreach ($port in $ports) {
        if (-not (Test-Port -Port $port)) {
            $occupiedPorts += $port
        }
    }
    
    if ($occupiedPorts.Count -gt 0) {
        Write-Host "[WARNING] 以下端口被占用: $($occupiedPorts -join ', ')" -ForegroundColor Yellow
        Write-Host "这可能会影响服务启动，请检查并关闭占用这些端口的程序" -ForegroundColor Yellow
    } else {
        Write-Host "[SUCCESS] 所有必需端口都可用" -ForegroundColor Green
    }
}

# 函数：创建必要的目录
function Create-Directories {
    Write-Host "创建必要的目录..." -ForegroundColor Cyan
    $directories = @("logs", "mongodb_data", "minio_data")
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "[SUCCESS] 创建目录: $dir" -ForegroundColor Green
        }
    }
}

# 主安装流程
Write-Host "开始安装流程..." -ForegroundColor Green
Write-Host ""

# 安装 Chocolatey
Install-Chocolatey

# 安装基础软件
$nodeOk = Install-NodeJS
$pythonOk = Install-Python
$goOk = Install-Go
$mongoOk = Install-MongoDB
$dockerOk = Install-Docker

# 检查基础环境
if (-not ($nodeOk -and $pythonOk -and $goOk)) {
    Write-Host "" 
    Write-Host "[ERROR] 基础环境安装不完整，请手动安装缺失的软件后重新运行" -ForegroundColor Red
    Write-Host "必需软件: Node.js, Python, Go" -ForegroundColor Yellow
    Write-Host "可选软件: MongoDB, Docker" -ForegroundColor Yellow
    exit 1
}

# 安装项目依赖
$depsOk = Install-ProjectDependencies
if (-not $depsOk) {
    Write-Host "" 
    Write-Host "[ERROR] 项目依赖安装失败" -ForegroundColor Red
    exit 1
}

# 创建目录
Create-Directories

# 检查端口
Check-Ports

Write-Host "" 
Write-Host "=== 安装完成 ===" -ForegroundColor Green
Write-Host "" 

# 显示安装结果
Write-Host "[INFO] 安装结果摘要:" -ForegroundColor White
Write-Host "- Node.js: $(if ($nodeOk) { '✅ 已安装' } else { '❌ 未安装' })" -ForegroundColor $(if ($nodeOk) { 'Green' } else { 'Red' })
Write-Host "- Python: $(if ($pythonOk) { '✅ 已安装' } else { '❌ 未安装' })" -ForegroundColor $(if ($pythonOk) { 'Green' } else { 'Red' })
Write-Host "- Go: $(if ($goOk) { '✅ 已安装' } else { '❌ 未安装' })" -ForegroundColor $(if ($goOk) { 'Green' } else { 'Red' })
Write-Host "- MongoDB: $(if ($mongoOk) { '✅ 已安装' } else { '❌ 未安装' })" -ForegroundColor $(if ($mongoOk) { 'Green' } else { 'Red' })
Write-Host "- Docker: $(if ($dockerOk) { '✅ 已安装' } else { '⚠️ 未安装 (可选)' })" -ForegroundColor $(if ($dockerOk) { 'Green' } else { 'Yellow' })
Write-Host "- 项目依赖: $(if ($depsOk) { '✅ 已安装' } else { '❌ 安装失败' })" -ForegroundColor $(if ($depsOk) { 'Green' } else { 'Red' })

Write-Host "" 
Write-Host "[NEXT] 下一步操作:" -ForegroundColor White
Write-Host "1. 运行 '.\start-all.ps1' 启动所有服务" -ForegroundColor Cyan
Write-Host "2. 访问 http://localhost:3000 使用应用" -ForegroundColor Cyan
Write-Host "3. 查看 README.md 了解详细使用说明" -ForegroundColor Cyan
Write-Host "4. 查看 DEPLOYMENT.md 了解部署指南" -ForegroundColor Cyan

Write-Host "" 
Write-Host "[TIPS] 使用提示:" -ForegroundColor White
Write-Host "- 使用 '.\stop-all.ps1' 停止所有服务" -ForegroundColor Gray
Write-Host "- 查看 'logs/' 目录获取详细日志" -ForegroundColor Gray
Write-Host "- 遇到问题请查看 DEPLOYMENT.md 故障排除部分" -ForegroundColor Gray

Write-Host "" 
Write-Host "🎉 NewsHub 安装完成！开始体验智能内容管理平台吧！" -ForegroundColor Green
Write-Host "" 

Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")