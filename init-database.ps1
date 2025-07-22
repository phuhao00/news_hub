# NewsHub 数据库初始化脚本
# 用于初始化 MongoDB 数据库和插入示例数据

# 检查 Docker 是否安装
function Test-Docker {
    try {
        docker --version | Out-Null
        return $true
    }
    catch {
        Write-Host "错误: 未找到 Docker，请先安装 Docker Desktop" -ForegroundColor Red
        return $false
    }
}

# 启动 MongoDB 容器
function Start-MongoContainer {
    Write-Host "检查 MongoDB 容器状态..." -ForegroundColor Yellow
    
    $containerExists = docker ps -a --filter "name=newshub-mongodb" --format "{{.Names}}" | Select-String "newshub-mongodb"
    
    if ($containerExists) {
        Write-Host "MongoDB 容器已存在，正在启动..." -ForegroundColor Blue
        docker start newshub-mongodb
    } else {
        Write-Host "创建并启动 MongoDB 容器..." -ForegroundColor Blue
        docker run -d --name newshub-mongodb -p 27015:27017 -v "${PWD}/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js" mongo:latest
    }
    
    # 等待 MongoDB 启动
    Write-Host "等待 MongoDB 启动..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    
    do {
        Start-Sleep -Seconds 2
        $attempt++
        $isReady = docker exec newshub-mongodb mongosh --eval "db.adminCommand('ping')" 2>$null
        if ($isReady) {
            Write-Host "MongoDB 已就绪!" -ForegroundColor Green
            return $true
        }
        Write-Host "等待中... ($attempt/$maxAttempts)" -ForegroundColor Gray
    } while ($attempt -lt $maxAttempts)
    
    Write-Host "MongoDB 启动超时" -ForegroundColor Red
    return $false
}

# 执行数据库初始化
function Initialize-Database {
    Write-Host "执行数据库初始化..." -ForegroundColor Yellow
    
    try {
        # 执行初始化脚本
        docker exec newshub-mongodb mongosh newshub /docker-entrypoint-initdb.d/init-mongo.js
        
        # 插入示例数据
        Write-Host "插入示例数据..." -ForegroundColor Blue
        
        # 创建示例数据脚本文件
        $sampleScript = @'
db = db.getSiblingDB("newshub");

db.creators.insertMany([
    {
        username: "tech_blogger",
        platform: "weibo",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "news_reporter", 
        platform: "douyin",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "lifestyle_vlogger",
        platform: "xiaohongshu",
        created_at: new Date(),
        updated_at: new Date()
    }
]);

print("Sample data inserted successfully!");
'@
        
        $tempFile = "init-sample-data.js"
        $sampleScript | Out-File -FilePath $tempFile -Encoding UTF8
        
        # 复制到容器并执行
        docker cp $tempFile newshub-mongodb:/tmp/init-sample-data.js
        docker exec newshub-mongodb mongosh newshub /tmp/init-sample-data.js
        
        # 清理临时文件
        Remove-Item $tempFile -Force
        docker exec newshub-mongodb rm /tmp/init-sample-data.js
        
        Write-Host "数据库初始化完成!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "数据库初始化失败: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 显示数据库状态
function Show-DatabaseStatus {
    Write-Host "\n=== 数据库状态 ===" -ForegroundColor Cyan
    
    try {
        # 显示数据库信息
        Write-Host "数据库列表:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh --eval "show dbs"
        
        Write-Host "\n集合列表:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh newshub --eval "show collections"
        
        Write-Host "\n创作者数据:" -ForegroundColor Yellow
        docker exec newshub-mongodb mongosh newshub --eval "db.creators.find().pretty()"
        
    }
    catch {
        Write-Host "无法获取数据库状态: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 主函数
function Main {
    Write-Host "=== NewsHub 数据库初始化 ===" -ForegroundColor Cyan
    
    # 检查 Docker
    if (-not (Test-Docker)) {
        exit 1
    }
    
    # 启动 MongoDB 容器
    if (-not (Start-MongoContainer)) {
        Write-Host "MongoDB 容器启动失败" -ForegroundColor Red
        exit 1
    }
    
    # 初始化数据库
    if (Initialize-Database) {
        Show-DatabaseStatus
        Write-Host "\n数据库初始化成功完成!" -ForegroundColor Green
        Write-Host "MongoDB 连接地址: mongodb://localhost:27015" -ForegroundColor Cyan
        Write-Host "数据库名称: newshub" -ForegroundColor Cyan
    } else {
        Write-Host "数据库初始化失败" -ForegroundColor Red
        exit 1
    }
}

# 错误处理
try {
    Main
}
catch {
    Write-Host "脚本执行出错: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}