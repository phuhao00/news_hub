# NewsHub 一键启动指南

本项目提供了多个一键启动脚本，适用于不同的操作系统环境。

## 🚀 快速启动

### Windows 用户

#### 方式一：PowerShell 脚本（推荐）
```powershell
# 在项目根目录下运行
.\start.ps1
```

#### 方式二：批处理脚本
```cmd
# 在项目根目录下运行
start.bat
```

### Linux/macOS 用户

```bash
# 在项目根目录下运行
./start.sh
```

## 📋 启动脚本功能

所有启动脚本都会自动完成以下操作：

1. **依赖检查与安装**
   - 检查并安装前端依赖 (npm packages)
   - 创建Python虚拟环境并安装爬虫服务依赖
   - 检查Go模块依赖

2. **服务启动**
   - 后端服务 (Go) - 端口 8082
   - 爬虫服务 (Python) - 端口 8001
   - 前端服务 (Next.js) - 端口 3001

3. **健康检查**
   - 等待各服务启动完成
   - 验证端口监听状态
   - 提供服务访问地址

## 🌐 服务地址

启动成功后，可以通过以下地址访问各服务：

- **前端应用**: http://localhost:3001
- **后端API**: http://localhost:8082
- **爬虫服务**: http://localhost:8001

## ⚠️ 注意事项

### 系统要求

- **Node.js** (v16+)
- **Python** (v3.8+)
- **Go** (v1.19+)
- **Git**

### 端口占用

如果遇到端口占用问题，请检查以下端口是否被其他程序占用：
- 3001 (前端)
- 8082 (后端)
- 8001 (爬虫)

### PowerShell 执行策略

Windows用户如果无法执行PowerShell脚本，请以管理员身份运行PowerShell并执行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 停止服务

- **PowerShell脚本**: 按 `Ctrl+C` 停止所有服务
- **批处理脚本**: 关闭各个命令行窗口
- **Shell脚本**: 按 `Ctrl+C` 停止所有服务

## 🔧 手动启动

如果自动启动脚本遇到问题，也可以手动启动各服务：

### 1. 启动后端服务
```bash
cd server
go run main.go
```

### 2. 启动爬虫服务
```bash
cd crawler-service
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 3. 启动前端服务
```bash
npm install
npm run dev
```

## 🐛 故障排除

### 常见问题

1. **依赖安装失败**
   - 检查网络连接
   - 确保包管理器版本正确
   - 尝试清除缓存后重新安装

2. **服务启动失败**
   - 检查端口是否被占用
   - 查看错误日志
   - 确保所有依赖已正确安装

3. **权限问题**
   - Linux/macOS: 确保脚本有执行权限 `chmod +x start.sh`
   - Windows: 检查PowerShell执行策略

### 获取帮助

如果遇到问题，请检查：
1. 各服务的日志输出
2. 系统环境是否满足要求
3. 网络连接是否正常

---

**提示**: 首次启动可能需要较长时间来下载和安装依赖，请耐心等待。