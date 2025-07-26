#!/bin/bash

# NewsHub 项目启动脚本 (Linux/Mac)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 正在启动 NewsHub 项目...${NC}"

# 检查必要的工具
echo -e "${YELLOW}📋 检查系统环境...${NC}"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ 未找到 Node.js，请先安装 Node.js${NC}"
    exit 1
fi

# 检查 Go
if ! command -v go &> /dev/null; then
    echo -e "${RED}❌ 未找到 Go，请先安装 Go${NC}"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}❌ 未找到 Python，请先安装 Python${NC}"
    exit 1
fi

# 设置 Python 命令
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo -e "${GREEN}✅ 系统环境检查完成${NC}"

# 检查并启动 MongoDB
echo -e "${YELLOW}🗄️ 检查 MongoDB...${NC}"
if pgrep -x "mongod" > /dev/null; then
    echo -e "${GREEN}✅ MongoDB 已在运行${NC}"
else
    echo -e "${YELLOW}⚠️ MongoDB 未运行，请确保 MongoDB 已启动${NC}"
    echo -e "${YELLOW}💡 提示：可以运行 'mongod' 或 'brew services start mongodb/brew/mongodb-community' (Mac)${NC}"
fi

# 安装前端依赖
echo -e "${YELLOW}📦 安装前端依赖...${NC}"
if [ -f "package.json" ]; then
    npm install
    echo -e "${GREEN}✅ 前端依赖安装完成${NC}"
else
    echo -e "${RED}❌ 未找到 package.json${NC}"
    exit 1
fi

# 安装后端依赖
echo -e "${YELLOW}📦 安装后端依赖...${NC}"
cd server
if [ -f "go.mod" ]; then
    go mod tidy
    echo -e "${GREEN}✅ 后端依赖安装完成${NC}"
else
    echo -e "${RED}❌ 未找到 go.mod${NC}"
    exit 1
fi
cd ..

# 安装爬虫服务依赖
echo -e "${YELLOW}📦 安装爬虫服务依赖...${NC}"
cd crawler-service
if [ -f "requirements.txt" ]; then
    $PYTHON_CMD -m pip install -r requirements.txt
    echo -e "${GREEN}✅ 爬虫服务依赖安装完成${NC}"
else
    echo -e "${RED}❌ 未找到 requirements.txt${NC}"
    exit 1
fi
cd ..

# 初始化数据库
echo -e "${YELLOW}🗄️ 初始化数据库...${NC}"
if [ -f "init-mongo.js" ]; then
    if command -v mongo &> /dev/null; then
        mongo newshub init-mongo.js
        echo -e "${GREEN}✅ 数据库初始化完成${NC}"
    elif command -v mongosh &> /dev/null; then
        mongosh newshub init-mongo.js
        echo -e "${GREEN}✅ 数据库初始化完成${NC}"
    else
        echo -e "${YELLOW}⚠️ 未找到 mongo 或 mongosh 命令，请手动初始化数据库${NC}"
    fi
fi

echo -e "${GREEN}🎉 准备工作完成，正在启动服务...${NC}"
echo ""

# 创建日志目录
mkdir -p logs

# 启动后端服务
echo -e "${CYAN}🚀 启动后端服务 (端口: 8080)...${NC}"
cd server
nohup go run main.go > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
cd ..

sleep 2

# 启动爬虫服务
echo -e "${CYAN}🕷️ 启动爬虫服务 (端口: 8001)...${NC}"
cd crawler-service
nohup $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload > ../logs/crawler.log 2>&1 &
CRAWLER_PID=$!
echo $CRAWLER_PID > ../logs/crawler.pid
cd ..

sleep 3

# 启动前端服务
echo -e "${CYAN}🌐 启动前端服务 (端口: 3000)...${NC}"
nohup npm run dev > logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > logs/frontend.pid

sleep 5

echo ""
echo -e "${GREEN}🎉 NewsHub 项目启动完成！${NC}"
echo ""
echo -e "${YELLOW}📊 服务地址:${NC}"
echo -e "  ${WHITE}前端应用: http://localhost:3000${NC}"
echo -e "  ${WHITE}后端API: http://localhost:8080${NC}"
echo -e "  ${WHITE}爬虫服务: http://localhost:8001${NC}"
echo -e "  ${WHITE}API文档: http://localhost:8001/docs${NC}"
echo ""
echo -e "${YELLOW}🔧 系统监控:${NC}"
echo -e "  ${WHITE}健康检查: http://localhost:8080/health${NC}"
echo -e "  ${WHITE}系统指标: http://localhost:8080/metrics${NC}"
echo ""
echo -e "${YELLOW}📋 进程ID:${NC}"
echo -e "  ${WHITE}后端服务: $BACKEND_PID${NC}"
echo -e "  ${WHITE}爬虫服务: $CRAWLER_PID${NC}"
echo -e "  ${WHITE}前端服务: $FRONTEND_PID${NC}"
echo ""
echo -e "${YELLOW}📝 日志文件:${NC}"
echo -e "  ${WHITE}后端日志: logs/backend.log${NC}"
echo -e "  ${WHITE}爬虫日志: logs/crawler.log${NC}"
echo -e "  ${WHITE}前端日志: logs/frontend.log${NC}"
echo ""
echo -e "${GREEN}⭐ 开始使用 NewsHub 智能内容管理平台吧！${NC}"
echo ""

# 检查服务是否启动成功
sleep 3
echo -e "${YELLOW}🔍 检查服务状态...${NC}"

# 检查后端服务
if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "${GREEN}✅ 后端服务运行正常${NC}"
else
    echo -e "${RED}❌ 后端服务启动失败${NC}"
fi

# 检查爬虫服务
if curl -s http://localhost:8001/health > /dev/null; then
    echo -e "${GREEN}✅ 爬虫服务运行正常${NC}"
else
    echo -e "${RED}❌ 爬虫服务启动失败${NC}"
fi

# 检查前端服务
if curl -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}✅ 前端服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️ 前端服务可能还在启动中...${NC}"
fi

echo ""
echo -e "${WHITE}💡 提示: 使用 './stop.sh' 停止所有服务${NC}"
echo -e "${WHITE}💡 提示: 使用 'tail -f logs/*.log' 查看实时日志${NC}"
echo ""

# 如果是 macOS，尝试打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open http://localhost:3000
    echo -e "${GREEN}🌐 已在浏览器中打开 NewsHub 应用${NC}"
elif command -v xdg-open &> /dev/null; then
    sleep 2
    xdg-open http://localhost:3000 &> /dev/null
    echo -e "${GREEN}🌐 已在浏览器中打开 NewsHub 应用${NC}"
else
    echo -e "${YELLOW}💡 请手动在浏览器中访问: http://localhost:3000${NC}"
fi

echo ""