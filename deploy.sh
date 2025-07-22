#!/bin/bash

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "请先安装Docker！"
    exit 1
}

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "请先安装Docker Compose！"
    exit 1
}

# 停止并删除现有容器
echo "正在清理现有容器..."
docker-compose down -v

# 构建并启动服务
echo "正在构建并启动服务..."
docker-compose up --build -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

echo "
部署完成！应用现在可以通过以下地址访问：
- 前端界面：http://localhost
- API接口：http://localhost/api
- MongoDB：localhost:27017
"