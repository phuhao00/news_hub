@echo off
chcp 65001 >nul
echo === NewsHub 一键启动脚本 ===
echo 正在启动 NewsHub 应用的所有服务...

REM 检查是否在正确的目录
if not exist "package.json" (
    echo 错误: 请在 NewsHub 项目根目录下运行此脚本
    pause
    exit /b 1
)

REM 检查并安装前端依赖
echo.
echo 1. 检查前端依赖...
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo 前端依赖安装失败
        pause
        exit /b 1
    )
)

REM 检查并安装爬虫服务依赖
echo.
echo 2. 检查爬虫服务依赖...
cd crawler-service
if not exist ".venv" (
    echo 创建Python虚拟环境...
    python -m venv .venv
)

REM 激活虚拟环境并安装依赖
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo 爬虫服务依赖安装失败
    pause
    exit /b 1
)
cd ..

REM 检查Go环境和后端依赖
echo.
echo 3. 检查后端服务...
cd server
go mod tidy
if errorlevel 1 (
    echo 后端依赖检查失败
    pause
    exit /b 1
)
cd ..

REM 启动服务
echo.
echo 4. 启动服务...

REM 启动后端服务
echo 启动后端服务...
start "NewsHub Backend" cmd /k "cd server && go run main.go"

REM 等待2秒
timeout /t 2 /nobreak >nul

REM 启动爬虫服务
echo 启动爬虫服务...
start "NewsHub Crawler" cmd /k "cd crawler-service && .venv\Scripts\activate.bat && python main.py"

REM 等待2秒
timeout /t 2 /nobreak >nul

REM 启动前端服务
echo 启动前端服务...
start "NewsHub Frontend" cmd /k "npm run dev"

echo.
echo === 所有服务正在启动 ===
echo 前端服务: http://localhost:3001
echo 后端服务: http://localhost:8082
echo 爬虫服务: http://localhost:8001
echo.
echo 请等待几秒钟让服务完全启动...
echo 按任意键退出启动脚本 (服务将继续在后台运行)
pause >nul