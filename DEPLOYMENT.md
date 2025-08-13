# NewsHub 部署指南

## 📋 系统要求

### 基础环境
- **操作系统**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **内存**: 最低 4GB，推荐 8GB+
- **存储**: 最低 10GB 可用空间
- **网络**: 稳定的互联网连接

### 必需软件
- **Node.js**: 18.0+ (推荐 LTS 版本)
- **Python**: 3.9+ (推荐 3.11)
- **Go**: 1.19+ (推荐 1.21)
- **MongoDB**: 6.0+ (社区版)
- **Docker**: 20.10+ (可选，用于 MinIO)
- **Git**: 2.30+

## 🚀 快速部署

### 1. 克隆项目
```bash
git clone https://github.com/your-org/newshub.git
cd newshub
```

### 2. 一键启动 (推荐)

#### Windows (PowerShell)
```powershell
# 管理员权限运行 PowerShell
.\start-all.ps1
```

#### Linux/macOS
```bash
# 添加执行权限
chmod +x start.sh stop.sh

# 启动所有服务
./start.sh
```

#### Windows (批处理)
```cmd
# 双击运行或命令行执行
start.bat
```

### 3. 验证部署
访问以下地址确认服务正常运行：
- **前端应用**: http://localhost:3000
- **后端 API**: http://localhost:8081/health
- **爬虫服务**: http://localhost:8001/docs
- **MinIO 控制台**: http://localhost:9001

## 🔧 手动部署

### 1. 安装依赖

#### 前端依赖
```bash
npm install
# 或使用 yarn
yarn install
```

#### 后端依赖
```bash
cd server
go mod tidy
cd ..
```

#### 爬虫服务依赖
```bash
cd crawler-service
pip install -r requirements.txt
# 或使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
cd ..
```

### 2. 配置数据库

#### MongoDB 安装和配置
```bash
# Ubuntu/Debian
sudo apt-get install mongodb

# macOS (使用 Homebrew)
brew install mongodb-community

# Windows
# 下载并安装 MongoDB Community Server
```

#### 初始化数据库
```bash
# Windows
.\init-database.ps1

# Linux/macOS
./init-database.sh
```

### 3. 配置 MinIO (对象存储)

#### 使用 Docker (推荐)
```bash
# Windows
.\start-minio.ps1

# Linux/macOS
docker-compose -f docker-compose.minio.yml up -d
```

#### 手动安装
```bash
# 下载 MinIO 二进制文件
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio

# 启动 MinIO
export MINIO_ROOT_USER=minioadmin
export MINIO_ROOT_PASSWORD=minioadmin123
./minio server ./minio-data --console-address ":9001"
```

### 4. 启动服务

#### 后端服务
```bash
cd server
go run main.go
# 或编译后运行
go build -o newshub-backend
./newshub-backend
```

#### 爬虫服务
```bash
cd crawler-service
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

#### 前端服务
```bash
npm run dev
# 或生产模式
npm run build
npm start
```

## 🐳 Docker 部署

### 1. 构建镜像
```bash
# 构建所有服务镜像
docker-compose build

# 或单独构建
docker build -f Dockerfile.frontend -t newshub-frontend .
docker build -f Dockerfile.backend -t newshub-backend .
docker build -f Dockerfile.crawler -t newshub-crawler .
```

### 2. 启动容器
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 3. Docker Compose 配置
```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
      - crawler

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8081:8081"
    depends_on:
      - mongodb
      - minio

  crawler:
    build:
      context: .
      dockerfile: Dockerfile.crawler
    ports:
      - "8001:8001"
    depends_on:
      - mongodb
      - minio

  mongodb:
    image: mongo:6.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  mongodb_data:
  minio_data:
```

## ⚙️ 配置文件

### 1. 全局配置 (config.json)
```json
{
  "services": {
    "backend": {
      "port": 8081,
      "host": "0.0.0.0"
    },
    "crawler": {
      "port": 8001,
      "host": "0.0.0.0"
    },
    "frontend": {
      "port": 3000,
      "host": "0.0.0.0"
    }
  },
  "database": {
    "mongodb": {
      "uri": "mongodb://localhost:27017",
      "database": "newshub"
    }
  },
  "storage": {
    "minio": {
      "endpoint": "localhost:9000",
      "accessKey": "minioadmin",
      "secretKey": "minioadmin123",
      "bucket": "newshub"
    }
  }
}
```

### 2. 环境变量配置
创建 `.env` 文件：
```bash
# 数据库配置
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=newshub

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=newshub

# 服务端口
BACKEND_PORT=8081
CRAWLER_PORT=8001
FRONTEND_PORT=3000

# 安全配置
JWT_SECRET=your-jwt-secret-key
API_KEY=your-api-key

# 爬虫配置
CRAWLER_TIMEOUT=30
CRAWLER_MAX_CONCURRENT=5
CRAWLER_HEADLESS=true

# 日志配置
LOG_LEVEL=info
LOG_FILE=logs/app.log
```

## 🔒 安全配置

### 1. 防火墙设置
```bash
# Ubuntu/Debian
sudo ufw allow 3000
sudo ufw allow 8081
sudo ufw allow 8001
sudo ufw allow 9000
sudo ufw allow 9001
sudo ufw allow 27017

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8081/tcp
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload
```

### 2. SSL/TLS 配置
```nginx
# nginx.conf 示例
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 数据库安全
```javascript
// MongoDB 用户创建
use newshub
db.createUser({
  user: "newshub_user",
  pwd: "secure_password",
  roles: [
    { role: "readWrite", db: "newshub" }
  ]
})
```

## 📊 监控和日志

### 1. 日志配置
```bash
# 创建日志目录
mkdir -p logs

# 日志轮转配置 (logrotate)
sudo vim /etc/logrotate.d/newshub
```

### 2. 系统监控
```bash
# 安装监控工具
sudo apt-get install htop iotop nethogs

# 监控脚本
#!/bin/bash
echo "=== NewsHub System Monitor ==="
echo "CPU Usage:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}'
echo "Memory Usage:"
free -h
echo "Disk Usage:"
df -h
echo "Network Connections:"
netstat -tuln | grep -E ':(3000|8081|8001|9000|27017)'
```

### 3. 健康检查
```bash
#!/bin/bash
# health-check.sh
services=("3000" "8081" "8001" "9000" "27017")
for port in "${services[@]}"; do
    if nc -z localhost $port; then
        echo "✅ Port $port is open"
    else
        echo "❌ Port $port is closed"
    fi
done
```

## 🚨 故障排除

### 常见问题

#### 1. 端口占用
```bash
# 查看端口占用
netstat -tulpn | grep :3000
lsof -i :3000

# 杀死占用进程
kill -9 $(lsof -t -i:3000)
```

#### 2. 依赖安装失败
```bash
# 清理 npm 缓存
npm cache clean --force
rm -rf node_modules package-lock.json
npm install

# 清理 Go 模块缓存
go clean -modcache
go mod download

# 清理 Python 缓存
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

#### 3. 数据库连接失败
```bash
# 检查 MongoDB 状态
sudo systemctl status mongod

# 重启 MongoDB
sudo systemctl restart mongod

# 检查连接
mongo --eval "db.adminCommand('ismaster')"
```

#### 4. 内存不足
```bash
# 增加交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 日志分析
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
grep -i error logs/app.log

# 查看系统日志
sudo journalctl -u newshub -f
```

## 🔄 更新和维护

### 1. 应用更新
```bash
# 停止服务
./stop.sh

# 拉取最新代码
git pull origin main

# 更新依赖
npm install
cd server && go mod tidy && cd ..
cd crawler-service && pip install -r requirements.txt && cd ..

# 重启服务
./start.sh
```

### 2. 数据备份
```bash
# MongoDB 备份
mongodump --db newshub --out backup/$(date +%Y%m%d)

# MinIO 备份
mc mirror minio/newshub backup/minio/$(date +%Y%m%d)
```

### 3. 性能优化
```bash
# 数据库索引优化
mongo newshub --eval "db.posts.createIndex({created_at: -1})"

# 清理临时文件
find . -name "*.tmp" -delete
find . -name "*.log" -mtime +7 -delete
```

## 📞 技术支持

### 获取帮助
- **文档**: 查看项目 README.md
- **问题反馈**: 提交 GitHub Issues
- **社区讨论**: 加入项目讨论群
- **邮件支持**: support@newshub.com

### 贡献代码
1. Fork 项目仓库
2. 创建功能分支
3. 提交代码更改
4. 创建 Pull Request
5. 等待代码审查

---

**🎉 恭喜！NewsHub 部署完成，开始享受智能内容管理的便利吧！**