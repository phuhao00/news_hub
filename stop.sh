#!/bin/bash

# NewsHub 项目停止脚本 (Linux/Mac)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 正在停止 NewsHub 项目...${NC}"

# 停止通过PID文件记录的进程
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${CYAN}🚀 停止后端服务 (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID
        sleep 2
        if kill -0 $BACKEND_PID 2>/dev/null; then
            echo -e "${YELLOW}⚠️ 强制停止后端服务...${NC}"
            kill -9 $BACKEND_PID 2>/dev/null
        fi
        echo -e "${GREEN}✅ 后端服务已停止${NC}"
    fi
    rm -f logs/backend.pid
fi

if [ -f "logs/crawler.pid" ]; then
    CRAWLER_PID=$(cat logs/crawler.pid)
    if kill -0 $CRAWLER_PID 2>/dev/null; then
        echo -e "${CYAN}🕷️ 停止爬虫服务 (PID: $CRAWLER_PID)...${NC}"
        kill $CRAWLER_PID
        sleep 2
        if kill -0 $CRAWLER_PID 2>/dev/null; then
            echo -e "${YELLOW}⚠️ 强制停止爬虫服务...${NC}"
            kill -9 $CRAWLER_PID 2>/dev/null
        fi
        echo -e "${GREEN}✅ 爬虫服务已停止${NC}"
    fi
    rm -f logs/crawler.pid
fi

if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${CYAN}🌐 停止前端服务 (PID: $FRONTEND_PID)...${NC}"
        kill $FRONTEND_PID
        sleep 2
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            echo -e "${YELLOW}⚠️ 强制停止前端服务...${NC}"
            kill -9 $FRONTEND_PID 2>/dev/null
        fi
        echo -e "${GREEN}✅ 前端服务已停止${NC}"
    fi
    rm -f logs/frontend.pid
fi

# 停止可能遗留的进程
echo -e "${YELLOW}🔍 检查并停止遗留进程...${NC}"

# 停止Go进程
GO_PIDS=$(pgrep -f "go run main.go")
if [ ! -z "$GO_PIDS" ]; then
    echo -e "${CYAN}🚀 停止Go后端进程...${NC}"
    echo $GO_PIDS | xargs kill 2>/dev/null
    sleep 1
    echo $GO_PIDS | xargs kill -9 2>/dev/null
fi

# 停止Python爬虫进程
PYTHON_PIDS=$(pgrep -f "uvicorn main:app")
if [ ! -z "$PYTHON_PIDS" ]; then
    echo -e "${CYAN}🕷️ 停止Python爬虫进程...${NC}"
    echo $PYTHON_PIDS | xargs kill 2>/dev/null
    sleep 1
    echo $PYTHON_PIDS | xargs kill -9 2>/dev/null
fi

# 停止Node.js前端进程
NODE_PIDS=$(pgrep -f "npm run dev\|next dev")
if [ ! -z "$NODE_PIDS" ]; then
    echo -e "${CYAN}🌐 停止Node.js前端进程...${NC}"
    echo $NODE_PIDS | xargs kill 2>/dev/null
    sleep 1
    echo $NODE_PIDS | xargs kill -9 2>/dev/null
fi

# 停止占用特定端口的进程
for port in 3000 8080 8001; do
    PORT_PID=$(lsof -ti :$port 2>/dev/null)
    if [ ! -z "$PORT_PID" ]; then
        echo -e "${CYAN}🔧 停止占用端口 $port 的进程 (PID: $PORT_PID)...${NC}"
        kill $PORT_PID 2>/dev/null
        sleep 1
        kill -9 $PORT_PID 2>/dev/null
    fi
done

echo ""
echo -e "${GREEN}🎉 NewsHub 项目已停止！${NC}"
echo ""
echo -e "${YELLOW}📋 清理完成:${NC}"
echo -e "  ${WHITE}✅ 后端服务已停止${NC}"
echo -e "  ${WHITE}✅ 爬虫服务已停止${NC}"
echo -e "  ${WHITE}✅ 前端服务已停止${NC}"
echo -e "  ${WHITE}✅ 进程PID文件已清理${NC}"
echo ""
echo -e "${WHITE}💡 提示: 使用 './start.sh' 重新启动所有服务${NC}"
echo "" 