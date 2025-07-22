#!/bin/bash
# 数据库一键初始化脚本
# 用于快速设置MongoDB数据库和初始数据

set -e

echo "=== NewsHub 数据库初始化脚本 ==="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: 未找到Docker，请先安装Docker${NC}"
        exit 1
    fi
    echo -e "${GREEN}Docker已安装 ✓${NC}"
}

# 检查MongoDB容器是否运行
check_mongo_container() {
    if docker ps --filter "name=newshub-mongodb" --format "table {{.Names}}" | grep -q "newshub-mongodb"; then
        return 0
    else
        return 1
    fi
}

# 启动MongoDB容器
start_mongo_container() {
    echo -e "${YELLOW}启动MongoDB容器...${NC}"
    
    # 检查是否存在容器
    if docker ps -a --filter "name=newshub-mongodb" --format "table {{.Names}}" | grep -q "newshub-mongodb"; then
        echo -e "${BLUE}发现已存在的MongoDB容器，正在启动...${NC}"
        docker start newshub-mongodb
    else
        echo -e "${BLUE}创建新的MongoDB容器...${NC}"
        docker run -d \
            --name newshub-mongodb \
            -p 27015:27017 \
            -v newshub_mongodb_data:/data/db \
            -v "$(pwd)/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js:ro" \
            mongo:latest
    fi
    
    # 等待MongoDB启动
    echo -e "${YELLOW}等待MongoDB启动...${NC}"
    sleep 10
    
    # 验证连接
    max_retries=30
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if docker exec newshub-mongodb mongosh --eval "db.adminCommand('ping')" --quiet &> /dev/null; then
            echo -e "${GREEN}MongoDB已成功启动！${NC}"
            return 0
        else
            retry_count=$((retry_count + 1))
            echo -e "${YELLOW}等待MongoDB启动... ($retry_count/$max_retries)${NC}"
            sleep 2
        fi
    done
    
    echo -e "${RED}MongoDB启动超时！${NC}"
    return 1
}

# 执行数据库初始化
initialize_database() {
    echo -e "${YELLOW}执行数据库初始化...${NC}"
    
    # 执行初始化脚本
    docker exec newshub-mongodb mongosh newshub /docker-entrypoint-initdb.d/init-mongo.js
    
    # 插入示例数据
    echo -e "${BLUE}插入示例数据...${NC}"
    
    cat > init-sample-data.js << 'EOF'
db = db.getSiblingDB('newshub');

// 插入示例创作者数据
db.creators.insertMany([
    {
        username: "tech_blogger",
        platform: "微博",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "news_reporter",
        platform: "抖音",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        username: "lifestyle_vlogger",
        platform: "小红书",
        created_at: new Date(),
        updated_at: new Date()
    }
]);

print("示例数据插入完成！");
EOF
    
    # 复制到容器并执行
    docker cp init-sample-data.js newshub-mongodb:/tmp/init-sample-data.js
    docker exec newshub-mongodb mongosh newshub /tmp/init-sample-data.js
    
    # 清理临时文件
    rm -f init-sample-data.js
    docker exec newshub-mongodb rm /tmp/init-sample-data.js
    
    echo -e "${GREEN}数据库初始化完成！${NC}"
}

# 显示数据库状态
show_database_status() {
    echo -e "\n${CYAN}=== 数据库状态 ===${NC}"
    
    # 显示集合信息
    echo -e "${BLUE}数据库集合:${NC}"
    docker exec newshub-mongodb mongosh newshub --eval "db.listCollections().forEach(printjson)" --quiet
    
    echo -e "\n${BLUE}创作者数量:${NC}"
    docker exec newshub-mongodb mongosh newshub --eval "print('创作者总数: ' + db.creators.countDocuments())" --quiet
    
    echo -e "\n${BLUE}示例创作者:${NC}"
    docker exec newshub-mongodb mongosh newshub --eval "db.creators.find().limit(3).forEach(printjson)" --quiet
}

# 主执行流程
main() {
    # 检查Docker
    check_docker
    
    # 检查MongoDB容器状态
    if check_mongo_container; then
        echo -e "${GREEN}MongoDB容器已在运行 ✓${NC}"
    else
        if ! start_mongo_container; then
            echo -e "${RED}MongoDB容器启动失败！${NC}"
            exit 1
        fi
    fi
    
    # 执行数据库初始化
    if initialize_database; then
        show_database_status
        
        echo -e "\n${GREEN}=== 初始化完成 ===${NC}"
        echo -e "${CYAN}MongoDB连接地址: mongodb://localhost:27015${NC}"
        echo -e "${CYAN}数据库名称: newshub${NC}"
        echo -e "\n${YELLOW}您现在可以启动后端服务了：${NC}"
        echo -e "${NC}cd server && go run main.go${NC}"
    else
        echo -e "${RED}数据库初始化失败！${NC}"
        exit 1
    fi
}

# 执行主函数
main "$@"