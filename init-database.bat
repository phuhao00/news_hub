@echo off
echo === NewsHub 数据库初始化 ===
echo.

REM 检查Docker是否安装
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Docker，请先安装 Docker Desktop
    pause
    exit /b 1
)

echo Docker 已安装 ✓
echo.

REM 检查是否有运行中的MongoDB容器
echo 检查 MongoDB 容器状态...
for /f "tokens=*" %%i in ('docker ps --filter "name=newshub-mongodb" --format "{{.Names}}"') do set RUNNING_CONTAINER=%%i

if defined RUNNING_CONTAINER (
    echo MongoDB 容器已在运行: %RUNNING_CONTAINER%
    goto :init_db
)

REM 检查是否有已存在的容器
for /f "tokens=*" %%i in ('docker ps -a --filter "name=newshub-mongodb" --format "{{.Names}}"') do set EXISTING_CONTAINER=%%i

if defined EXISTING_CONTAINER (
    echo 启动已存在的 MongoDB 容器...
    docker start newshub-mongodb
) else (
    echo 创建新的 MongoDB 容器...
    docker run -d --name newshub-mongodb -p 27017:27017 -v "%cd%\init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js" mongo:latest
)

REM 等待MongoDB启动
echo 等待 MongoDB 启动...
set /a attempts=0
:wait_loop
set /a attempts+=1
if %attempts% gtr 30 (
    echo MongoDB 启动超时
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul
docker exec newshub-mongodb mongosh --eval "db.adminCommand('ping')" >nul 2>&1
if %errorlevel% neq 0 (
    echo 等待中... (%attempts%/30)
    goto :wait_loop
)

echo MongoDB 已就绪!
echo.

:init_db
echo 执行数据库初始化...
docker exec newshub-mongodb mongosh newshub /docker-entrypoint-initdb.d/init-mongo.js

echo.
echo 插入示例数据...

REM 创建示例数据脚本
echo db = db.getSiblingDB("newshub"); > temp_init.js
echo. >> temp_init.js
echo db.creators.insertMany([ >> temp_init.js
echo     { >> temp_init.js
echo         username: "tech_blogger", >> temp_init.js
echo         platform: "weibo", >> temp_init.js
echo         created_at: new Date(), >> temp_init.js
echo         updated_at: new Date() >> temp_init.js
echo     }, >> temp_init.js
echo     { >> temp_init.js
echo         username: "news_reporter", >> temp_init.js
echo         platform: "douyin", >> temp_init.js
echo         created_at: new Date(), >> temp_init.js
echo         updated_at: new Date() >> temp_init.js
echo     }, >> temp_init.js
echo     { >> temp_init.js
echo         username: "lifestyle_vlogger", >> temp_init.js
echo         platform: "xiaohongshu", >> temp_init.js
echo         created_at: new Date(), >> temp_init.js
echo         updated_at: new Date() >> temp_init.js
echo     } >> temp_init.js
echo ]); >> temp_init.js
echo. >> temp_init.js
echo print("Sample data inserted successfully!"); >> temp_init.js

REM 执行示例数据插入
docker cp temp_init.js newshub-mongodb:/tmp/temp_init.js
docker exec newshub-mongodb mongosh newshub /tmp/temp_init.js
docker exec newshub-mongodb rm /tmp/temp_init.js
del temp_init.js

echo.
echo === 数据库状态 ===
echo 数据库列表:
docker exec newshub-mongodb mongosh --eval "show dbs"
echo.
echo 集合列表:
docker exec newshub-mongodb mongosh newshub --eval "show collections"
echo.
echo 创作者数据:
docker exec newshub-mongodb mongosh newshub --eval "db.creators.find().pretty()"

echo.
echo === 初始化完成 ===
echo MongoDB 连接地址: mongodb://localhost:27015
echo 数据库名称: newshub
echo.
echo 您现在可以启动后端服务了：
echo cd server ^&^& go run main.go
echo.
pause