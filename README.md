# NewHub - 社交媒体动态采集与发布平台

## 项目简介

NewHub是一个自动化的社交媒体内容采集和发布平台。它可以自动收集指定创作者在各大社交平台（微博、抖音、小红书、哔哩哔哩）的最新动态，生成视频内容，并支持一键发布到多个平台。

## 技术栈

- 前端：Next.js + TypeScript + Tailwind CSS
- 后端：Go + Gin
- 数据库：MongoDB
- 部署：Docker + Nginx

## 功能特点

- 多平台内容采集
- 自动视频生成
- 多平台一键发布
- 实时任务状态跟踪
- 容器化部署

## 系统要求

- Docker
- Docker Compose
- PowerShell（Windows）或 Bash（Linux/macOS）

## 快速开始

### 方式一：一键部署（推荐）

1. 克隆项目：
   ```bash
   git clone <repository-url>
   cd newshub
   ```

2. 配置环境变量：
   - 复制`.env.example`到`.env`
   - 修改环境变量配置

3. 一键部署：
   Windows：
   ```powershell
   .\deploy.ps1
   ```

   Linux/macOS：
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. 访问应用：
   - 前端界面：http://localhost
   - API接口：http://localhost/api
   - MongoDB：localhost:27015

### 方式二：本地开发

1. 克隆项目并安装依赖：
   ```bash
   git clone <repository-url>
   cd newshub
   make install  # 或手动安装前后端依赖
   ```

2. 初始化数据库：
   ```bash
   # 使用脚本初始化（推荐）
   make init-db
   
   # 或使用Go工具初始化
   make init-db-go
   
   # 或手动执行
   # Windows: .\init-database.ps1
   # Linux/macOS: ./init-database.sh
   ```

3. 启动开发服务：
   ```bash
   # 启动前端（新终端）
   make dev-frontend
   
   # 启动后端（新终端）
   make dev-backend
   ```

4. 访问应用：
   - 前端界面：http://localhost:3000
   - 后端API：http://localhost:8080
   - MongoDB：mongodb://localhost:27015

## 项目结构

```
├── src/                  # 前端源代码
│   ├── app/             # Next.js应用页面
│   ├── components/      # React组件
│   ├── types/          # TypeScript类型定义
│   └── utils/          # 工具函数
├── server/              # 后端源代码
│   ├── config/         # 配置文件
│   ├── handlers/       # 请求处理器
│   ├── models/         # 数据模型
│   └── main.go         # 主程序入口
├── Dockerfile.frontend  # 前端Docker配置
├── Dockerfile.backend   # 后端Docker配置
├── docker-compose.yml   # Docker编排配置
├── nginx.conf          # Nginx配置
└── init-mongo.js       # MongoDB初始化脚本
```

## 数据库管理

### 初始化数据库

项目提供了多种数据库初始化方式：

1. **脚本初始化（推荐）**：
   ```bash
   # Windows
   .\init-database.ps1
   
   # Linux/macOS
   ./init-database.sh
   
   # 或使用Makefile
   make init-db
   ```

2. **Go工具初始化**：
   ```bash
   cd server/cmd/init-db
   go run main.go
   
   # 或使用Makefile
   make init-db-go
   ```

3. **Docker方式**：
   ```bash
   # 启动MongoDB容器
   make start-db
   
   # 执行初始化
   make init-db
   ```

### 数据库操作

```bash
# 启动数据库
make start-db

# 停止数据库
make stop-db

# 清理数据库（谨慎使用）
make clean-db
```

## 开发指南

### 本地开发

使用Makefile命令简化开发流程：

```bash
# 查看所有可用命令
make help

# 安装依赖
make install

# 初始化数据库
make init-db

# 启动开发环境
make dev

# 分别启动前后端
make dev-frontend  # 前端：http://localhost:3000
make dev-backend   # 后端：http://localhost:8080

# 检查环境
make check
```

### 手动开发

1. 前端开发：
   ```bash
   npm install
   npm run dev
   ```

2. 后端开发：
   ```bash
   cd server
   go mod download
   go run main.go
   ```

### 构建部署

使用Docker Compose进行构建和部署：

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证

[MIT License](LICENSE)
