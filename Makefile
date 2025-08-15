# NewsHub 项目管理 Makefile

.PHONY: help init-db start-db stop-db clean-db dev build docker-up docker-down

# 默认目标
help:
	@echo "NewsHub 项目管理命令:"
	@echo ""
	@echo "数据库管理:"
	@echo "  init-db      - 初始化数据库（推荐）"
	@echo "  init-db-go  - 使用Go工具初始化数据库"
	@echo "  start-db     - 启动MongoDB容器"
	@echo "  stop-db      - 停止MongoDB容器"
	@echo "  clean-db     - 清理数据库数据"
	@echo ""
	@echo "开发服务:"
	@echo "  dev          - 启动开发环境"
	@echo "  dev-frontend - 启动前端开发服务器"
	@echo "  dev-backend  - 启动后端开发服务器"
	@echo ""
	@echo "Docker管理:"
	@echo "  docker-up    - 启动所有Docker服务"
	@echo "  docker-down  - 停止所有Docker服务"
	@echo "  build        - 构建Docker镜像"
	@echo ""
	@echo "其他:"
	@echo "  clean        - 清理临时文件"
	@echo "  install      - 安装依赖"

# 数据库初始化（推荐方式）
init-db:
	@echo "正在初始化数据库..."
ifeq ($(OS),Windows_NT)
	@powershell -ExecutionPolicy Bypass -File ./init-database.ps1
else
	@chmod +x ./init-database.sh
	@./init-database.sh
endif

# 使用Go工具初始化数据库
init-db-go:
	@echo "使用Go工具初始化数据库..."
	@cd server/cmd/init-db && go mod tidy && go run main.go

# 启动MongoDB容器
start-db:
	@echo "启动MongoDB容器..."
	@docker run -d --name newshub-mongodb -p 27017:27017 -v newshub_mongodb_data:/data/db mongo:latest || docker start newshub-mongodb
	@echo "MongoDB已启动在端口 27017"

# 停止MongoDB容器
stop-db:
	@echo "停止MongoDB容器..."
	@docker stop newshub-mongodb || true

# 清理数据库数据
clean-db:
	@echo "警告：这将删除所有数据库数据！"
	@read -p "确认继续？(y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@docker stop newshub-mongodb || true
	@docker rm newshub-mongodb || true
	@docker volume rm newshub_mongodb_data || true
	@echo "数据库数据已清理"

# 启动开发环境
dev: init-db
	@echo "启动开发环境..."
	@echo "前端: http://localhost:3000"
	@echo "后端: http://localhost:8080"
	@echo "MongoDB: mongodb://localhost:27015"
	@echo ""
	@echo "请在不同终端中运行："
	@echo "1. make dev-frontend"
	@echo "2. make dev-backend"

# 启动前端开发服务器
dev-frontend:
	@echo "启动前端开发服务器..."
	@npm install
	@npm run dev

# 启动后端开发服务器
dev-backend:
	@echo "启动后端开发服务器..."
	@cd server && go mod tidy && go run main.go

# Docker管理
docker-up:
	@echo "启动Docker服务..."
	@docker-compose up -d
	@echo "服务已启动："
	@echo "  前端: http://localhost"
	@echo "  后端API: http://localhost/api"
	@echo "  MongoDB: mongodb://localhost:27015"

docker-down:
	@echo "停止Docker服务..."
	@docker-compose down

build:
	@echo "构建Docker镜像..."
	@docker-compose build

# 安装依赖
install:
	@echo "安装前端依赖..."
	@npm install
	@echo "安装后端依赖..."
	@cd server && go mod tidy
	@cd server/cmd/init-db && go mod tidy

# 清理临时文件
clean:
	@echo "清理临时文件..."
	@rm -rf node_modules/.cache
	@rm -rf .next
	@rm -rf server/tmp
	@rm -f init-sample-data.js
	@echo "清理完成"

# 检查环境
check:
	@echo "检查开发环境..."
	@echo "Node.js版本:"
	@node --version || echo "❌ Node.js 未安装"
	@echo "Go版本:"
	@go version || echo "❌ Go 未安装"
	@echo "Docker版本:"
	@docker --version || echo "❌ Docker 未安装"
	@echo "MongoDB连接测试:"
	@docker exec newshub-mongodb mongosh --eval "db.adminCommand('ping')" --quiet 2>/dev/null && echo "✅ MongoDB 连接正常" || echo "❌ MongoDB 未运行"