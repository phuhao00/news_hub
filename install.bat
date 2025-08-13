@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM NewsHub 项目自动安装脚本 (Windows)
REM 自动检测环境、安装依赖、配置服务

echo ===============================================
echo           NewsHub 项目自动安装脚本
echo ===============================================
echo 正在检查系统环境并安装依赖...
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] 检测到管理员权限
) else (
    echo [WARNING] 未检测到管理员权限，某些安装步骤可能失败
    echo [WARNING] 建议以管理员身份运行此脚本
    echo.
)

REM 设置变量
set "NODE_OK=false"
set "PYTHON_OK=false"
set "GO_OK=false"
set "CHOCO_OK=false"
set "DEPS_OK=false"

REM 函数：检查命令是否存在
:check_command
where %1 >nul 2>&1
if %errorLevel% == 0 (
    exit /b 0
) else (
    exit /b 1
)

REM 函数：检查端口是否被占用
:check_port
netstat -an | findstr ":%1 " >nul 2>&1
if %errorLevel% == 0 (
    exit /b 1
) else (
    exit /b 0
)

REM [1/7] 检查并安装 Chocolatey
echo [1/7] 检查 Chocolatey...
call :check_command choco
if %errorLevel% == 0 (
    echo [SUCCESS] Chocolatey 已安装
    set "CHOCO_OK=true"
) else (
    echo [INFO] 正在安装 Chocolatey...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    
    REM 刷新环境变量
    call refreshenv
    
    call :check_command choco
    if !errorLevel! == 0 (
        echo [SUCCESS] Chocolatey 安装成功
        set "CHOCO_OK=true"
    ) else (
        echo [ERROR] Chocolatey 安装失败
        echo [INFO] 将尝试手动安装其他软件
    )
)
echo.

REM [2/7] 检查并安装 Node.js
echo [2/7] 检查 Node.js...
call :check_command node
if %errorLevel% == 0 (
    for