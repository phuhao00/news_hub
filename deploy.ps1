# 检查Docker是否安装
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "请先安装Docker！"
    exit 1
}

# 检查Docker Compose是否安装
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Error "请先安装Docker Compose！"
    exit 1
}

# 停止并删除现有容器
Write-Host "正在清理现有容器..."
docker-compose down -v

# 构建并启动服务
Write-Host "正在构建并启动服务..."
docker-compose up --build -d

# 等待服务启动
Write-Host "等待服务启动..."
Start-Sleep -Seconds 10

# 检查服务状态
Write-Host "检查服务状态..."
docker-compose ps

Write-Host "
部署完成！应用现在可以通过以下地址访问：
- 前端界面：http://localhost
- API接口：http://localhost/api
- MongoDB：localhost:27015
"