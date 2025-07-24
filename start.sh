#!/bin/bash
# NewsHub 一键启动脚本 (Linux/macOS)
# 启动前端、后端和爬虫服务

echo "=== NewsHub 一键启动脚本 ==="
echo "正在启动 NewsHub 应用的所有服务..."

# 检查是否在正确的目录
if [ ! -f "package.json" ]; then
    echo "错误: 请在 NewsHub 项目根目录下运行此脚本"
    exit 1
fi

# 函数：检查端口是否被占用
check_port() {
    local port=$1
    if command -v nc >/dev/null 2>&1; then
        nc -z localhost $port >/dev/null 2>&1
    elif command -v telnet >/dev/null 2>&1; then
        timeout 1 telnet localhost $port >/dev/null 2>&1
    else
        # 使用lsof作为备选
        lsof -i :$port >/dev/null 2>&1
    fi
}

# 函数：等待服务启动
wait_for_service() {
    local port=$1
    local service_name=$2
    local timeout=${3:-30}
    
    echo "等待 $service_name 启动 (端口 $port)..."
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        if check_port $port; then
            echo "✓ $service_name 已启动"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    echo "✗ $service_name 启动超时"
    return 1
}

# 清理函数
cleanup() {
    echo "\n正在停止所有服务..."
    jobs -p | xargs -r kill
    echo "所有服务已停止"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 检查并安装前端依赖
echo "\n1. 检查前端依赖..."
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "前端依赖安装失败"
        exit 1
    fi
fi

# 检查并安装爬虫服务依赖
echo "\n2. 检查爬虫服务依赖..."
cd crawler-service
if [ ! -d ".venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境并安装依赖
source .venv/bin/activate
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "爬虫服务依赖安装失败"
    exit 1
fi
cd ..

# 检查Go环境和后端依赖
echo "\n3. 检查后端服务..."
cd server
go mod tidy
if [ $? -ne 0 ]; then
    echo "后端依赖检查失败"
    exit 1
fi
cd ..

# 启动服务
echo "\n4. 启动服务..."

# 启动后端服务 (端口 8082)
echo "启动后端服务..."
cd server
go run main.go &
BACKEND_PID=$!
cd ..

# 等待后端服务启动
if ! wait_for_service 8082 "后端服务"; then
    echo "后端服务启动失败，停止所有服务"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# 启动爬虫服务 (端口 8001)
echo "启动爬虫服务..."
cd crawler-service
source .venv/bin/activate
python main.py &
CRAWLER_PID=$!
cd ..

# 等待爬虫服务启动
if ! wait_for_service 8001 "爬虫服务"; then
    echo "爬虫服务启动失败，停止所有服务"
    kill $BACKEND_PID $CRAWLER_PID 2>/dev/null
    exit 1
fi

# 启动前端服务 (端口 3001)
echo "启动前端服务..."
npm run dev &
FRONTEND_PID=$!

# 等待前端服务启动
if ! wait_for_service 3001 "前端服务"; then
    echo "前端服务启动失败，停止所有服务"
    kill $BACKEND_PID $CRAWLER_PID $FRONTEND_PID 2>/dev/null
    exit 1
fi

echo "\n=== 所有服务启动成功! ==="
echo "前端服务: http://localhost:3001"
echo "后端服务: http://localhost:8082"
echo "爬虫服务: http://localhost:8001"
echo "\n按 Ctrl+C 停止所有服务"

# 等待用户中断
wait