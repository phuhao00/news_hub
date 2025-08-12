# MinIO 独立部署指南

本文档说明如何单独运行MinIO Docker容器，而其他服务在本地运行。

## 文件说明

- `docker-compose.minio.yml` - MinIO独立Docker配置
- `start-minio.ps1` - 启动MinIO服务的PowerShell脚本
- `stop-minio.ps1` - 停止MinIO服务的PowerShell脚本
- `.env.local` - 本地开发环境配置文件

## 快速开始

### 1. 启动MinIO服务

```powershell
# 使用PowerShell脚本启动
.\start-minio.ps1

# 或者直接使用docker-compose
docker-compose -f docker-compose.minio.yml up -d
```

### 2. 访问MinIO

- **API地址**: http://localhost:9000
- **管理控制台**: http://localhost:9001
- **用户名**: minioadmin
- **密码**: minioadmin123

### 3. 启动本地服务

#### 后端服务
```bash
cd server
# 使用本地环境配置
export $(cat ../.env.local | xargs)
go run main.go
```

#### 前端服务
```bash
# 复制环境配置
cp .env.local .env.local
npm run dev
```

#### 爬虫服务
```bash
cd crawler-service
# 设置环境变量
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin123
export MINIO_USE_SSL=false
export MINIO_BUCKET_NAME=newshub-media
python main.py
```

### 4. 停止MinIO服务

```powershell
# 使用PowerShell脚本停止
.\stop-minio.ps1

# 或者直接使用docker-compose
docker-compose -f docker-compose.minio.yml down
```

## 环境配置

### 本地开发环境变量

所有本地服务都应该使用 `.env.local` 文件中的配置，主要包括：

```env
# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_USE_SSL=false
MINIO_BUCKET_NAME=newshub-media

# 数据库配置
MONGODB_URI=mongodb://localhost:27017
DB_NAME=newshub

# 服务端口
PORT=8080
CRAWLER_PORT=8001
```

## 网络配置

MinIO Docker容器通过以下端口暴露服务：
- `9000` - MinIO API端口
- `9001` - MinIO Web控制台端口

本地服务可以通过 `localhost:9000` 访问MinIO API。

## 数据持久化

MinIO数据存储在Docker volume `minio_data` 中，即使容器重启数据也不会丢失。

## 故障排除

### 1. 端口冲突
如果端口9000或9001被占用，请修改 `docker-compose.minio.yml` 中的端口映射。

### 2. 连接失败
确保：
- Docker Desktop正在运行
- MinIO容器已成功启动
- 防火墙没有阻止端口访问

### 3. 权限问题
如果遇到文件权限问题，请确保Docker有足够的权限访问挂载的目录。

## 监控和日志

查看MinIO容器日志：
```bash
docker-compose -f docker-compose.minio.yml logs -f minio
```

查看容器状态：
```bash
docker-compose -f docker-compose.minio.yml ps
```