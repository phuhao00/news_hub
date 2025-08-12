# NewsHub 项目启动指南

## 🚀 快速启动

### 一键启动所有服务
```powershell
./start-all.ps1
```

### 一键停止所有服务
```powershell
./stop-all.ps1
```

## 📋 服务架构

本项目采用微服务架构，包含以下服务：

| 服务 | 端口 | 描述 | 启动方式 |
|------|------|------|----------|
| 前端 (Next.js) | 3000 | 用户界面 | `npm run dev` |
| 后端 (Go) | 8081 | API服务 | `cd server && go run main.go` |
| 爬虫服务 (Python) | 8001 | 内容爬取 | `cd crawler-service && python main.py` |
| MinIO | 9000/9001 | 对象存储 | Docker容器 |
| MongoDB | 27015 | 数据库 | Docker容器 |

## 🔧 手动启动步骤

如果需要手动启动各个服务，请按以下顺序操作：

### 1. 启动 MinIO 对象存储
```powershell
./start-minio.ps1
```
- API地址: http://localhost:9000
- 管理控制台: http://localhost:9001
- 用户名: `minioadmin`
- 密码: `minioadmin123`

### 2. 启动 MongoDB 数据库
```powershell
./init-database.ps1
```
- 连接地址: `mongodb://localhost:27015`
- 数据库名: `newshub`

### 3. 启动后端 Go 服务
```powershell
cd server
go mod tidy  # 首次运行需要安装依赖
go run main.go
```
- API地址: http://localhost:8081
- 健康检查: http://localhost:8081/health

### 4. 启动前端 Next.js 服务
```powershell
npm install  # 首次运行需要安装依赖
npm run dev
```
- 应用地址: http://localhost:3000

### 5. 启动爬虫 Python 服务
```powershell
cd crawler-service
pip install -r requirements.txt  # 首次运行需要安装依赖
python main.py
```
- 服务地址: http://localhost:8001
- API文档: http://localhost:8001/docs

## 🌐 访问地址

启动完成后，可以通过以下地址访问各个服务：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8081
- **爬虫服务**: http://localhost:8001
- **MinIO控制台**: http://localhost:9001
- **API文档**: http://localhost:8001/docs

## 🛠️ 开发环境要求

### 必需软件
- **Node.js** (v18+)
- **Go** (v1.19+)
- **Python** (v3.8+)
- **Docker** (用于MinIO和MongoDB)

### 环境变量配置

项目根目录下的 `.env.local` 文件包含本地开发环境配置：

```env
# MongoDB配置
MONGODB_URI=mongodb://localhost:27015
DB_NAME=newshub

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_USE_SSL=false
MINIO_BUCKET_NAME=newshub-media

# 服务端口配置
PORT=8081
CRAWLER_SERVICE_URL=http://localhost:8001
```

## 🔍 故障排除

### 常见问题

1. **端口被占用**
   ```powershell
   # 查看端口占用情况
   netstat -ano | findstr :3000
   netstat -ano | findstr :8081
   netstat -ano | findstr :8001
   ```

2. **Docker服务未启动**
   ```powershell
   # 启动Docker Desktop
   # 或检查Docker服务状态
   docker --version
   ```

3. **依赖包缺失**
   ```powershell
   # Go依赖
   cd server && go mod tidy
   
   # Node.js依赖
   npm install
   
   # Python依赖
   cd crawler-service && pip install -r requirements.txt
   ```

4. **数据库连接失败**
   - 确保MongoDB容器正在运行
   - 检查端口27015是否可用
   - 验证连接字符串配置

5. **MinIO连接失败**
   - 确保MinIO容器正在运行
   - 检查端口9000和9001是否可用
   - 验证访问密钥配置

### 日志查看

- **后端日志**: 在后端服务终端窗口查看
- **前端日志**: 在前端服务终端窗口查看
- **爬虫日志**: 在爬虫服务终端窗口查看
- **Docker日志**: `docker logs <container_name>`

## 📚 开发指南

### 项目结构
```
newshub/
├── src/                    # 前端源码 (Next.js)
├── server/                 # 后端源码 (Go)
├── crawler-service/        # 爬虫服务 (Python)
├── docker-compose.yml      # Docker编排文件
├── start-all.ps1          # 一键启动脚本
├── stop-all.ps1           # 一键停止脚本
└── PROJECT_STARTUP.md     # 本文档
```

### API接口

- **健康检查**: `GET /health`
- **创作者管理**: `/api/creators`
- **内容管理**: `/api/posts`
- **视频管理**: `/api/videos`
- **发布管理**: `/api/publish`
- **存储管理**: `/api/storage`
- **爬虫管理**: `/api/crawler`

### 数据库集合

- `creators`: 创作者信息
- `posts`: 帖子内容
- `videos`: 视频信息
- `publish_tasks`: 发布任务
- `crawler_tasks`: 爬取任务
- `crawler_contents`: 爬取内容

## 🚀 部署说明

### Docker部署
```powershell
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止所有服务
docker-compose down
```

### 生产环境配置

1. 修改环境变量配置
2. 配置反向代理 (Nginx)
3. 设置SSL证书
4. 配置监控和日志
5. 设置自动备份

---

**📞 技术支持**: 如遇问题，请查看项目文档或联系开发团队。