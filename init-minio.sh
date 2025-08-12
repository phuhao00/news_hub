#!/bin/bash

# 等待MinIO服务启动
echo "等待MinIO服务启动..."
sleep 10

# 配置MinIO客户端
mc alias set myminio http://minio:9000 minioadmin minioadmin123

# 创建bucket
echo "创建bucket: newshub-media"
mc mb myminio/newshub-media

# 设置bucket策略为公开读取
echo "设置bucket策略"
mc anonymous set public myminio/newshub-media

# 创建子目录结构
echo "创建目录结构"
mc cp /dev/null myminio/newshub-media/images/.keep
mc cp /dev/null myminio/newshub-media/videos/.keep
mc cp /dev/null myminio/newshub-media/thumbnails/.keep

echo "MinIO初始化完成"