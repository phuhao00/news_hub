#!/bin/bash

# NewsHub 项目自动安装脚本 (Linux/macOS)
# 自动检测环境、安装依赖、配置服务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== NewsHub 项目自动安装脚本 ===${NC}"
echo -e "${YELLOW}正在检查系统环境并安装依赖...${NC}"
echo ""

# 检测操作系统
OS="Unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
    if [ -f /etc/debian_version ]; then
        DISTRO="Debian/Ubuntu"
        PKG_MANAGER="apt"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="RedHat/CentOS"
        PKG_MANAGER="yum"
    elif [ -f /etc/arch-release ]; then
        DISTRO="Arch"
        PKG_MANAGER="pacman"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    DISTRO="macOS"
    PKG_MANAGER="brew"
fi

echo -e "${CYAN}检测到系统: $OS ($DISTRO)${NC}"
echo ""

# 检查是否有 sudo 权限
if ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}[警告] 某些安装步骤可能需要 sudo 权限${NC}"
    echo -e "${YELLOW}请确保您有管理员权限或稍后手动安装缺失的软件${NC}"
    echo ""
fi

# 函数：检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 函数：检查端口是否可用
check_port() {
    local port=$1
    if command_exists nc; then
        ! nc -z localhost $port 2>/dev/null
    elif command_exists netstat; then
        ! netstat -tuln 2>/dev/null | grep -q ":$port "
    else
        true  # 如果没有检测工具，假设端口可用
    fi
}

# 函数：安装包管理器
install_package_manager() {
    echo -e "${CYAN}[1/7] 检查包管理器...${NC}"
    
    if [[ "$OS" == "macOS" ]]; then
        if ! command_exists brew; then
            echo -e "${YELLOW}正在安装 Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}[SUCCESS] Homebrew 安装成功${NC}"
            else
                echo -e "${RED}[ERROR] Homebrew 安装失败${NC}"
                return 1
            fi
        else
            echo -e "${GREEN}[SUCCESS] Homebrew 已安装${NC}"
        fi
    elif [[ "$OS" == "Linux" ]]; then
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            sudo apt update
            echo -e "${GREEN}[SUCCESS] APT 包管理器已更新${NC}"
        elif [[ "$PKG_MANAGER" == "yum" ]]; then
            sudo yum update -y
            echo -e "${GREEN}[SUCCESS] YUM 包管理器已更新${NC}"
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            sudo pacman -Sy
            echo -e "${GREEN}[SUCCESS] Pacman 包管理器已更新${NC}"
        fi
    fi
    return 0
}

# 函数：安装 Node.js
install_nodejs() {
    echo -e "${CYAN}[2/7] 检查 Node.js...${NC}"
    
    if ! command_exists node; then
        echo -e "${YELLOW}正在安装 Node.js...${NC}"
        
        if [[ "$OS" == "macOS" ]]; then
            brew install node
        elif [[ "$PKG_MANAGER" == "apt" ]]; then
            curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif [[ "$PKG_MANAGER" == "yum" ]]; then
            curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
            sudo yum install -y nodejs npm
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            sudo pacman -S nodejs npm
        else
            echo -e "${RED}[ERROR] 不支持的包管理器，请手动安装 Node.js${NC}"
            return 1
        fi
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[SUCCESS] Node.js 安装成功${NC}"
        else
            echo -e "${RED}[ERROR] Node.js 安装失败${NC}"
            return 1
        fi
    else
        local node_version=$(node --version)
        echo -e "${GREEN}[SUCCESS] Node.js 已安装: $node_version${NC}"
    fi
    return 0
}

# 函数：安装 Python
install_python() {
    echo -e "${CYAN}[3/7] 检查 Python...${NC}"
    
    if ! command_exists python3 && ! command_exists python; then
        echo -e "${YELLOW}正在安装 Python...${NC}"
        
        if [[ "$OS" == "macOS" ]]; then
            brew install python
        elif [[ "$PKG_MANAGER" == "apt" ]]; then
            sudo apt-get install -y python3 python3-pip python3-venv
        elif [[ "$PKG_MANAGER" == "yum" ]]; then
            sudo yum install -y python3 python3-pip
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            sudo pacman -S python python-pip
        else
            echo -e "${RED}[ERROR] 不支持的包管理器，请手动安装 Python${NC}"
            return 1
        fi
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[SUCCESS] Python 安装成功${NC}"
        else
            echo -e "${RED}[ERROR] Python 安装失败${NC}"
            return 1
        fi
    else
        if command_exists python3; then
            local python_version=$(python3 --version)
            echo -e "${GREEN}[SUCCESS] Python 已安装: $python_version${NC}"
        else
            local python_version=$(python --version)
            echo -e "${GREEN}[SUCCESS] Python 已安装: $python_version${NC}"
        fi
    fi
    return 0
}

# 函数：安装 Go
install_go() {
    echo -e "${CYAN}[4/7] 检查 Go...${NC}"
    
    if ! command_exists go; then
        echo -e "${YELLOW}正在安装 Go...${NC}"
        
        if [[ "$OS" == "macOS" ]]; then
            brew install go
        elif [[ "$PKG_MANAGER" == "apt" ]]; then
            # 安装最新版本的 Go
            GO_VERSION="1.21.5"
            wget -c https://golang.org/dl/go${GO_VERSION}.linux-amd64.tar.gz
            sudo tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz
            rm go${GO_VERSION}.linux-amd64.tar.gz
            
            # 添加到 PATH
            echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
            export PATH=$PATH:/usr/local/go/bin
        elif [[ "$PKG_MANAGER" == "yum" ]]; then
            sudo yum install -y golang
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            sudo pacman -S go
        else
            echo -e "${RED}[ERROR] 不支持的包管理器，请手动安装 Go${NC}"
            return 1
        fi
        
        if command_exists go; then
            echo -e "${GREEN}[SUCCESS] Go 安装成功${NC}"
        else
            echo -e "${RED}[ERROR] Go 安装失败${NC}"
            return 1
        fi
    else
        local go_version=$(go version)
        echo -e "${GREEN}[SUCCESS] Go 已安装: $go_version${NC}"
    fi
    return 0
}

# 函数：安装 MongoDB
install_mongodb() {
    echo -e "${CYAN}[5/7] 检查 MongoDB...${NC}"
    
    if ! command_exists mongod && ! command_exists mongo; then
        echo -e "${YELLOW}正在安装 MongoDB...${NC}"
        
        if [[ "$OS" == "macOS" ]]; then
            brew tap mongodb/brew
            brew install mongodb-community
        elif [[ "$PKG_MANAGER" == "apt" ]]; then
            # 安装 MongoDB 官方源
            wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
            echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
            sudo apt-get update
            sudo apt-get install -y mongodb-org
        elif [[ "$PKG_MANAGER" == "yum" ]]; then
            # 创建 MongoDB 源文件
            sudo tee /etc/yum.repos.d/mongodb-org-6.0.repo > /dev/null <<EOF
[mongodb-org-6.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/6.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-6.0.asc
EOF
            sudo yum install -y mongodb-org
        elif [[ "$PKG_MANAGER" == "pacman" ]]; then
            sudo pacman -S mongodb-bin
        else
            echo -e "${YELLOW}[WARNING] 无法自动安装 MongoDB，请手动安装${NC}"
            return 1
        fi
        
        if command_exists mongod; then
            echo -e "${GREEN}[SUCCESS] MongoDB 安装成功${NC}"
        else
            echo -e "${YELLOW}[WARNING] MongoDB 安装可能失败，请手动检查${NC}"
        fi
    else
        echo -e "${GREEN}[SUCCESS] MongoDB 已安装${NC}"
    fi
    return 0
}

# 函数：安装 Docker (可选)
install_docker() {
    echo -e "${CYAN}[6/7] 检查 Docker (可选)...${NC}"
    
    if ! command_exists docker; then
        echo -e "${YELLOW}Docker 未安装，将跳过 MinIO 容器部署${NC}"
        echo -e "${YELLOW}如需使用 MinIO，请手动安装 Docker${NC}"
        
        if [[ "$OS" == "macOS" ]]; then
            echo -e "${YELLOW}macOS 用户请下载 Docker Desktop: https://www.docker.com/products/docker-desktop${NC}"
        elif [[ "$OS" == "Linux" ]]; then
            echo -e "${YELLOW}Linux 用户可运行: curl -fsSL https://get.docker.com | sh${NC}"
        fi
        return 1
    else
        local docker_version=$(docker --version)
        echo -e "${GREEN}[SUCCESS] Docker 已安装: $docker_version${NC}"
        return 0
    fi
}

# 函数：安装项目依赖
install_project_dependencies() {
    echo -e "${CYAN}[7/7] 安装项目依赖...${NC}"
    
    # 检查项目目录
    if [ ! -f "package.json" ]; then
        echo -e "${RED}[ERROR] 未找到 package.json，请确保在项目根目录运行此脚本${NC}"
        return 1
    fi
    
    # 设置 Python 命令
    PYTHON_CMD="python3"
    if ! command_exists python3; then
        PYTHON_CMD="python"
    fi
    
    # 安装前端依赖
    echo -e "${YELLOW}安装前端依赖...${NC}"
    if npm install; then
        echo -e "${GREEN}[SUCCESS] 前端依赖安装完成${NC}"
    else
        echo -e "${RED}[ERROR] 前端依赖安装失败${NC}"
        return 1
    fi
    
    # 安装后端依赖
    echo -e "${YELLOW}安装后端依赖...${NC}"
    if cd server && go mod tidy && cd ..; then
        echo -e "${GREEN}[SUCCESS] 后端依赖安装完成${NC}"
    else
        echo -e "${RED}[ERROR] 后端依赖安装失败${NC}"
        cd ..
        return 1
    fi
    
    # 安装爬虫服务依赖
    echo -e "${YELLOW}安装爬虫服务依赖...${NC}"
    if cd crawler-service && $PYTHON_CMD -m pip install -r requirements.txt && cd ..; then
        echo -e "${GREEN}[SUCCESS] 爬虫服务依赖安装完成${NC}"
    else
        echo -e "${RED}[ERROR] 爬虫服务依赖安装失败${NC}"
        cd ..
        return 1
    fi
    
    # 安装根目录 Python 依赖
    echo -e "${YELLOW}安装根目录 Python 依赖...${NC}"
    if $PYTHON_CMD -m pip install -r requirements.txt; then
        echo -e "${GREEN}[SUCCESS] 根目录 Python 依赖安装完成${NC}"
    else
        echo -e "${YELLOW}[WARNING] 根目录 Python 依赖安装失败，但不影响主要功能${NC}"
    fi
    
    return 0
}

# 函数：检查端口占用
check_ports() {
    echo -e "${CYAN}检查端口占用情况...${NC}"
    local ports=(3000 8081 8001 9000 9001 27017 8080 3001)
    local occupied_ports=()
    
    for port in "${ports[@]}"; do
        if ! check_port $port; then
            occupied_ports+=("$port")
        fi
    done
    
    if [ ${#occupied_ports[@]} -gt 0 ]; then
        echo -e "${YELLOW}[WARNING] 以下端口被占用: ${occupied_ports[*]}${NC}"
        echo -e "${YELLOW}这可能会影响服务启动，请检查并关闭占用这些端口的程序${NC}"
    else
        echo -e "${GREEN}[SUCCESS] 所有必需端口都可用${NC}"
    fi
}

# 函数：创建必要的目录
create_directories() {
    echo -e "${CYAN}创建必要的目录...${NC}"
    local directories=("logs" "mongodb_data" "minio_data")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo -e "${GREEN}[SUCCESS] 创建目录: $dir${NC}"
        fi
    done
}

# 函数：设置执行权限
set_permissions() {
    echo -e "${CYAN}设置脚本执行权限...${NC}"
    local scripts=("start.sh" "stop.sh" "start-all.ps1" "install.sh")
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            chmod +x "$script"
            echo -e "${GREEN}[SUCCESS] 设置执行权限: $script${NC}"
        fi
    done
}

# 主安装流程
echo -e "${GREEN}开始安装流程...${NC}"
echo ""

# 安装包管理器
install_package_manager

# 安装基础软件
node_ok=false
python_ok=false
go_ok=false
mongo_ok=false
docker_ok=false

if install_nodejs; then node_ok=true; fi
if install_python; then python_ok=true; fi
if install_go; then go_ok=true; fi
if install_mongodb; then mongo_ok=true; fi
if install_docker; then docker_ok=true; fi

# 检查基础环境
if ! $node_ok || ! $python_ok || ! $go_ok; then
    echo ""
    echo -e "${RED}[ERROR] 基础环境安装不完整，请手动安装缺失的软件后重新运行${NC}"
    echo -e "${YELLOW}必需软件: Node.js, Python, Go${NC}"
    echo -e "${YELLOW}可选软件: MongoDB, Docker${NC}"
    exit 1
fi

# 安装项目依赖
deps_ok=false
if install_project_dependencies; then deps_ok=true; fi

if ! $deps_ok; then
    echo ""
    echo -e "${RED}[ERROR] 项目依赖安装失败${NC}"
    exit 1
fi

# 创建目录和设置权限
create_directories
set_permissions

# 检查端口
check_ports

echo ""
echo -e "${GREEN}=== 安装完成 ===${NC}"
echo ""

# 显示安装结果
echo -e "${WHITE}[INFO] 安装结果摘要:${NC}"
echo -e "- Node.js: $(if $node_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${RED}❌ 未安装${NC}'; fi)"
echo -e "- Python: $(if $python_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${RED}❌ 未安装${NC}'; fi)"
echo -e "- Go: $(if $go_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${RED}❌ 未安装${NC}'; fi)"
echo -e "- MongoDB: $(if $mongo_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${RED}❌ 未安装${NC}'; fi)"
echo -e "- Docker: $(if $docker_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${YELLOW}⚠️ 未安装 (可选)${NC}'; fi)"
echo -e "- 项目依赖: $(if $deps_ok; then echo -e '${GREEN}✅ 已安装${NC}'; else echo -e '${RED}❌ 安装失败${NC}'; fi)"

echo ""
echo -e "${WHITE}[NEXT] 下一步操作:${NC}"
echo -e "${CYAN}1. 运行 './start.sh' 启动所有服务${NC}"
echo -e "${CYAN}2. 访问 http://localhost:3000 使用应用${NC}"
echo -e "${CYAN}3. 查看 README.md 了解详细使用说明${NC}"
echo -e "${CYAN}4. 查看 DEPLOYMENT.md 了解部署指南${NC}"

echo ""
echo -e "${WHITE}[TIPS] 使用提示:${NC}"
echo -e "${GRAY}- 使用 './stop.sh' 停止所有服务${NC}"
echo -e "${GRAY}- 查看 'logs/' 目录获取详细日志${NC}"
echo -e "${GRAY}- 遇到问题请查看 DEPLOYMENT.md 故障排除部分${NC}"

echo ""
echo -e "${GREEN}🎉 NewsHub 安装完成！开始体验智能内容管理平台吧！${NC}"
echo ""