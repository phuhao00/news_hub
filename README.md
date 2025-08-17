# NewsHub - 智能内容爬取与管理平台

一个现代化的内容爬取、管理和发布平台，支持多平台**真实搜索**和智能内容提取。

## 🚀 功能矩阵

| 类别 | 能力 | 说明 |
|------|------|------|
| 爬取 | 真实搜索、URL直抓、反爬策略 | 百度/搜狗/必应聚合，UA/间隔/重试 |
| 内容 | 标题/正文/媒体抽取、去重、质量评估 | MD5 去重、多指标质量评分 |
| 任务 | 创建/调度/重试、状态跟踪 | pending/running/completed/failed |
| 存储 | MongoDB + MinIO | 元数据入库，媒体入对象存储 |
| 生成 | AI 视频合成（多风格）、可选配音 | 基于选定内容合成视频 |
| 发布 | 多平台发布与状态跟踪 | 批量发布、错误重试 |
| 分析 | 指标与趋势、互动统计 | 概览/性能/互动维度 |
| 自动化 | 工作流与定时任务 | 触发器 + 动作流水线 |

## 🏗️ 系统架构

```mermaid
graph LR
    A[Next.js 14 前端] -- REST/JSON --> B[Go API (Gin)]
    B -- 任务下发/回调 --> C[Python 爬虫服务 (FastAPI/Playwright)]
    C -- 真实搜索/抓取 --> G[(搜索引擎/目标站点)]
    B -- 元数据/状态 --> D[(MongoDB)]
    B -- 媒体读写 --> E[(MinIO 对象存储)]
    subgraph 后端内部
        B --- F[任务调度器/重试]
        B --- H[去重与质量评估]
    end
    style D fill:#E3F2FD,stroke:#90CAF9
    style E fill:#F1F8E9,stroke:#A5D6A7
```

### 服务端口配置
- 前端: `http://localhost:3000`
- Go后端: `http://localhost:8081`（本地开发；Docker 为 `8080`）
- Python爬虫: `http://localhost:8001`
- MinIO: `9000`(API) / `9001`(Console)
- MongoDB: `localhost:27015`（本地），Docker 默认 `27017`

### 数据模型与关系（ER）

```mermaid
erDiagram
    CREATOR ||--o{ POST : has
    POST }o--o{ VIDEO : referenced_by
    VIDEO ||--o{ PUBLISHTASK : produces
    CRAWLERTASK ||--o{ CRAWLERCONTENT : generates
    CRAWLERCONTENT }o--|| POST : may_map_to

    CREATOR {
        ObjectID id
        string username
        string platform
        string profile_url
        int follower_count
        bool auto_crawl_enabled
        int crawl_interval
        time last_crawl_at
        string crawl_status
    }
    POST {
        ObjectID id
        ObjectID creator_id
        string platform
        string post_id
        string title
        string content
        string[] media_urls
        time published_at
    }
    VIDEO {
        ObjectID id
        ObjectID[] post_ids
        string style
        int duration
        string url
        string status
    }
    PUBLISHTASK {
        ObjectID id
        ObjectID video_id
        string[] platforms
        string status
    }
    CRAWLERTASK {
        ObjectID id
        string task_id
        string platform
        string url
        string status
        time created_at
    }
    CRAWLERCONTENT {
        ObjectID id
        ObjectID task_id
        string title
        string content
        string content_hash
        string author
        string platform
        string url
        time created_at
    }
```

### 部署拓扑

```mermaid
graph TB
    subgraph Client
        U[Browser/Creator]
    end

    subgraph Host/Dev Machine
        FE[Next.js Frontend :3000]
        BE[Go Backend (Gin) :8081]
        PY[Python Crawler :8001]
        DB[(MongoDB :27015/27017)]
        OBJ[(MinIO :9000/:9001)]
    end

    U --> FE --> BE --> PY
    BE <---> DB
    BE <---> OBJ
    PY --> DB
    PY --> OBJ
```

### 端口与服务一览

| 服务 | 端口 | 描述 | 备注 |
|------|------|------|------|
| 前端 Next.js | 3000 | Web 应用 | 开发环境
| Go 后端 | 8081 | API 服务 | Docker 默认 8080
| Python 爬虫 | 8001 | 爬虫/抽取服务 | FastAPI + Playwright
| MinIO API | 9000 | 对象存储 API | 媒体与文件
| MinIO Console | 9001 | MinIO 控制台 | Web 管理界面
| MongoDB | 27015/27017 | 文档数据库 | 本地 27015，Docker 27017

### 环境变量（.env.local 示例）

```bash
# 数据库
MONGODB_URI=mongodb://localhost:27015
DB_NAME=newshub

# MinIO 对象存储
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_USE_SSL=false
MINIO_BUCKET_NAME=newshub-media

# 服务端口
PORT=8081
CRAWLER_SERVICE_URL=http://localhost:8001
```

## 🛠️ 技术栈（表）

| 模块 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14, TypeScript, Tailwind CSS | App Router，实时刷新 |
| 后端 | Go, Gin | 高性能 API，JSON 日志 |
| 爬虫 | Python, FastAPI, Playwright/Requests, BS4 | 真实搜索与抽取 |
| 存储 | MongoDB, MinIO | 元数据 + 媒体对象 |
| 部署 | Docker Compose, Nginx | 统一编排与反代 |

## 🚀 快速开始

### 安装依赖

```bash
# 安装前端依赖
npm install

# 安装Go依赖
cd server
go mod tidy

# 安装Python依赖
cd ../crawler-service
pip install -r requirements.txt
```

### 环境变量表

| 键 | 示例值 | 说明 |
|----|--------|------|
| MONGODB_URI | mongodb://localhost:27015 | MongoDB 连接串（本地） |
| DB_NAME | newshub | 数据库名 |
| MINIO_ENDPOINT | localhost:9000 | MinIO API 端点 |
| MINIO_ACCESS_KEY | minioadmin | MinIO 访问密钥 |
| MINIO_SECRET_KEY | minioadmin123 | MinIO 密钥 |
| MINIO_USE_SSL | false | 是否启用 SSL |
| MINIO_BUCKET_NAME | newshub-media | 媒体桶名 |
| PORT | 8081 | Go 后端本地端口 |
| CRAWLER_SERVICE_URL | http://localhost:8001 | 爬虫服务地址 |
| NEXT_PUBLIC_API_URL | http://localhost/api | 前端在 Docker 下的 API 代理 |

### 配置数据库

```bash
# Windows
.\init-database.bat

# Linux/Mac
./init-database.sh

# PowerShell
.\init-database.ps1
```

### 启动服务

```powershell
# 一键启动（推荐，可选清库）
./start-all.ps1               # 正常启动
./start-all.ps1 -Interactive  # 启动时询问是否清库
./start-all.ps1 -CleanDB      # 非交互清库（保留 sessions/login_sessions/platform_configs）
```

### 测试爬虫功能

```bash
# 进入爬虫服务目录
cd crawler-service

# 运行测试脚本
python test_crawler.py
```

### 访问应用

- **主页**: http://localhost:3000
- **爬虫管理**: http://localhost:3000/crawler
- **登录状态管理**: http://localhost:3000/login-state
- **爬虫服务 API 文档**: http://localhost:8001/docs
- **后端健康检查**: http://localhost:8081/health

## 📖 使用指南（表）

| 功能 | 入口 | 动作 |
|------|------|------|
| 创建爬取任务 | `/crawler` | 选择平台/关键词或 URL，设置数量，开始任务 |
| 监控任务状态 | `/crawler` | 查看 pending/running/completed/failed |
| 浏览内容 | `/content` | 按平台/创作者筛选，查看详情/原文 |
| 生成视频 | `/generate` | 选择内容，设定风格/时长/分辨率，生成 |
| 发布内容 | `/publish` | 选择平台与文案，提交发布任务 |

## 🔧 配置文件

### 全局配置 (`config.json`)
```json
{
  "services": {
    "backend": {"port": 8080, "host": "0.0.0.0"},
    "crawler": {"port": 8001, "host": "0.0.0.0"},
    "frontend": {"port": 3000, "host": "0.0.0.0"}
  },
  "database": {
    "mongodb": {
      "uri": "mongodb://localhost:27017",
      "database": "newshub"
    }
  }
}
```

### 爬虫配置 (`crawler-service/config.json`)
```json
{
  "server": {"port": 8001, "host": "0.0.0.0"},
  "crawler": {
    "headless": true,
    "timeout": 30,
    "max_concurrent": 5
  },
  "platforms": {
    "weibo": {"enabled": true, "timeout": 60},
    "bilibili": {"enabled": true, "timeout": 60}
  }
}
```

## 📊 支持的平台

| 平台 | 搜索支持 | 数据来源 | 内容类型 | 特殊说明 |
|------|----------|----------|----------|----------|
| 微博 | ✅ | 搜索引擎聚合 | 帖子、话题、动态 | 通过搜索引擎获取相关内容 |
| B站 | ✅ | 搜索引擎聚合 | 视频、UP主、弹幕 | 视频内容和元数据提取 |
| 小红书 | ✅ | 搜索引擎聚合 | 笔记、种草、生活分享 | 生活内容丰富 |
| 抖音 | ✅ | 搜索引擎聚合 | 短视频、创作者 | 通过第三方渠道获取 |
| 新闻 | ✅ | 多源新闻聚合 | 文章、资讯 | 百度、搜狗、必应新闻 |

## 🛡️ 真实爬取策略

### 数据源策略
- **搜索引擎聚合**: 通过百度、搜狗、必应等搜索引擎获取内容
- **多源验证**: 使用多个数据源交叉验证内容质量
- **智能过滤**: 基于关键词匹配和内容相关性过滤

### 反爬机制
- **智能请求头**: 模拟真实浏览器行为
- **请求间隔**: 避免频率过高被封
- **错误重试**: 自动重试失败的请求
- **代理支持**: 可配置代理池（可选）

### 内容质量保证
- **相关性检查**: 确保内容与搜索词相关
- **长度过滤**: 过滤过短或无意义的内容
- **广告过滤**: 自动识别和过滤广告内容
- **重复检测**: 避免重复内容

## 📈 监控与日志

### 系统指标
- 访问 `/metrics` 查看系统指标
- 任务成功率、响应时间统计
- 内存和CPU使用情况

### 日志系统
- Go后端日志: 自动轮转，JSON格式
- Python服务日志: 详细的爬取过程
- 前端错误监控: 实时错误追踪

## 🔄 开发模式

```bash
# 前端开发服务器
npm run dev

# 后端热重载
cd server && go run main.go

# Python服务开发模式
cd crawler-service && uvicorn main:app --reload --port 8001

# 测试爬虫功能
cd crawler-service && python test_crawler.py
```

## 📦 生产部署

### Docker部署
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 传统部署
1. 编译Go二进制文件
2. 构建Next.js生产版本
3. 配置Nginx反向代理
4. 启动MongoDB和Python服务

## 🤝 贡献指南

1. Fork本仓库
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add some AmazingFeature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 详情请查看 [LICENSE](LICENSE) 文件。

## 🆘 常见问题

### Q: 为什么不直接爬取平台网站？
A: 现代社交媒体平台都有严格的反爬机制，直接爬取容易被封禁。我们通过搜索引擎聚合的方式获取相关内容，更加稳定可靠。

### Q: 爬取的内容是真实的吗？
A: 是的！我们从真实的搜索引擎获取内容，经过智能解析和质量过滤，确保内容的真实性和相关性。

### Q: 如何增加新的平台支持？
A: 在 `crawler-service/main.py` 中添加新的爬取方法，参考现有平台实现。

### Q: 数据库连接失败怎么办？
A: 确保MongoDB服务正在运行，检查连接配置是否正确。

### Q: 如何测试爬虫功能？
A: 运行 `python crawler-service/test_crawler.py` 来测试所有平台的爬取功能。

---

🎉 **现在就开始体验强大的真实内容爬取功能吧！**

## 🎬 AI视频生成功能 ⭐ **新增**

### 智能视频制作
NewsHub集成了强大的AI视频生成功能，可以将爬取的内容自动制作成高质量视频：

#### 支持的视频风格
- **📺 新闻播报风格**: 专业的新闻报道样式，适合资讯类内容
- **🎬 Vlog记录风格**: 生活化的视频风格，适合日常内容分享
- **📖 故事叙述风格**: 故事性强的叙述方式，适合深度内容

#### 视频配置选项
- **时长控制**: 30秒到5分钟，灵活适应不同平台需求
- **分辨率选择**: 1080p（推荐）/ 4K超高清
- **内容素材**: 支持多条爬取内容合成一个视频
- **自动配音**: AI语音合成技术，支持多种音色

#### 使用流程
1. 在**内容管理**页面选择要制作视频的内容
2. 进入**视频生成**页面配置视频参数
3. 选择视频风格、时长和分辨率
4. 点击生成，AI自动制作视频
5. 生成完成后可直接跳转到发布管理

## 📤 多平台发布管理

### 一键发布到社交媒体
支持将生成的视频内容一键发布到多个主流社交媒体平台：

#### 支持平台
| 平台 | 图标 | 功能特点 | 发布状态跟踪 |
|------|------|----------|-------------|
| 微博 | 📱 | 支持视频+文案发布 | ✅ |
| 抖音 | 🎵 | 短视频平台优化 | ✅ |
| 小红书 | 📖 | 生活方式内容 | ✅ |
| 哔哩哔哩 | 📺 | 视频平台专属 | ✅ |

#### 发布功能
- **批量发布**: 同时发布到多个平台
- **自定义文案**: 为每个平台定制发布文案
- **状态跟踪**: 实时监控发布进度和状态
- **错误处理**: 详细的错误信息和重试机制
- **发布链接**: 成功后提供平台链接

#### 发布状态
- **⏳ 等待发布**: 任务已创建，等待执行
- **🔄 发布中**: 正在向平台发布内容  
- **✅ 已发布**: 成功发布，可查看链接
- **❌ 发布失败**: 失败原因和错误详情

## 📋 内容管理（表）

| 类别 | 能力 | 操作 |
|------|------|------|
| 内容浏览 | 多维度筛选、全文搜索、卡片预览 | 预览、跳转原文 |
| 内容操作 | 批量选择、删除、导出 | 批量处理、一键清理 |
| 质量评估 | 相关性/长度/广告/重复 | 评分与标注 |
| 创作者 | 档案、平台分类、关联内容、表现分析 | 新建/删除/筛选 |

## 🔄 完整工作流程

### 从爬取到发布的完整链路

```mermaid
graph TD
    A[关键词搜索] --> B[内容爬取]
    B --> C[内容管理]
    C --> D[AI视频生成]
    D --> E[多平台发布]
    E --> F[发布状态跟踪]
    
    B --> G[内容筛选]
    G --> H[质量评估]
    H --> C
    
    C --> I[内容编辑]
    I --> D
    
    F --> J[数据分析]
    J --> K[优化策略]
```

### 交互时序图（爬取任务）

```mermaid
sequenceDiagram
    participant UI as Next.js 前端
    participant API as Go API (Gin)
    participant CR as Python 爬虫
    participant DB as MongoDB
    participant OS as MinIO

    UI->>API: 创建爬取任务 (platform, keyword, count)
    API->>DB: 记录任务 (pending)
    API->>CR: 下发任务
    CR->>CR: 实际搜索/抓取 (Playwright/Requests)
    CR->>DB: 写入内容与任务进度
    CR->>OS: 上传图片/视频
    API->>DB: 更新任务状态 (completed/failed)
    UI->>API: 轮询任务与内容
    API-->>UI: 返回任务状态与内容列表
```

### 数据流转图

```mermaid
flowchart LR
    SRC[搜索结果/目标站点] --> EXT[内容抽取]
    EXT --> DEDUP[去重]
    DEDUP --> QA[质量评估]
    QA --> DB[(MongoDB)]
    QA --> OS[(MinIO)]
    DB --> API[Go API]
    OS --> API
    API --> UI[Next.js 前端]
```

### 典型使用场景

#### 1. 新闻资讯制作
```bash
1. 搜索关键词："人工智能新闻"
2. 爬取相关新闻内容
3. 筛选高质量资讯
4. 生成新闻播报风格视频
5. 发布到微博、B站等平台
```

#### 2. 生活内容创作
```bash
1. 搜索关键词："美食推荐"
2. 爬取小红书、抖音相关内容
3. 选择优质生活内容
4. 生成Vlog风格视频
5. 发布到多个生活平台
```

#### 3. 教育内容制作
```bash
1. 搜索关键词："编程教程"
2. 爬取技术博客和视频
3. 整理教学内容
4. 生成故事叙述风格视频
5. 发布到B站等学习平台
```

## 🎯 功能导航

### 主要页面和功能

| 页面 | 路径 | 主要功能 | 适用场景 |
|------|------|----------|----------|
| 🏠 **主页** | `/` | 创作者管理、平台概览 | 项目首页和创作者管理 |
| 📝 **内容管理** | `/content` | 内容浏览、筛选、管理 | 查看和管理爬取的内容 |
| 🕷️ **爬虫控制** | `/crawler` | 爬取任务管理 | 创建和监控爬取任务 |
| 🎬 **视频生成** | `/generate` | AI视频制作 | 将内容制作成视频 |
| 📤 **发布管理** | `/publish` | 多平台发布控制 | 发布视频到社交媒体 |

### 快速功能入口

```bash
# 创建爬取任务
http://localhost:3000/crawler

# 查看爬取内容  
http://localhost:3000/content

# 生成AI视频
http://localhost:3000/generate

# 发布到社交媒体
http://localhost:3000/publish
```

## 📡 API 接口（表）

| 领域 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 爬虫任务 | POST | `/api/crawler/tasks` | 创建爬虫任务（后端代理到 Python） |
| 爬虫任务 | GET | `/api/crawler/tasks` | 列表/分页/过滤 |
| 爬虫任务 | GET | `/api/crawler/tasks/{id}` | 获取任务详情 |
| 爬虫任务 | PUT | `/api/crawler/tasks/{id}/status` | 更新任务状态/错误 |
| 爬虫内容 | GET | `/api/crawler/contents` | 按任务ID筛选内容 |
| 平台 | GET | `/api/crawler/platforms` | 支持平台列表 |
| 创作者 | POST | `/api/creators` | 新建创作者 |
| 创作者 | GET | `/api/creators` | 创作者列表 |
| 创作者 | DELETE | `/api/creators/{id}` | 删除创作者 |
| 视频 | POST | `/api/videos/generate` | 生成视频 |
| 视频 | GET | `/api/videos` | 视频列表 |
| 发布 | POST | `/api/publish` | 创建发布任务 |
| 发布 | GET | `/api/publish/tasks` | 发布任务列表 |

## ⚡ 高级功能

### 智能内容分析
- **关键词提取**: 自动提取内容关键词
- **情感分析**: 分析内容情感倾向
- **话题分类**: 智能归类内容话题
- **质量评分**: 基于多维度的内容质量评估

### 数据统计分析
- **爬取统计**: 各平台爬取数据统计
- **内容分析**: 内容类型和质量分布
- **发布效果**: 多平台发布效果追踪
- **趋势分析**: 内容热度和趋势分析

### 定时任务
- **定时爬取**: 设置定期爬取任务
- **自动生成**: 达到条件自动生成视频
- **定时发布**: 按计划自动发布内容
- **清理任务**: 定期清理过期数据

### 安全和隐私
- **数据加密**: 敏感数据加密存储
- **访问控制**: 基于角色的权限管理
- **审计日志**: 完整的操作日志记录
- **隐私保护**: 符合数据保护法规

## 🎉 **立即开始体验完整的内容创作工作流程！**

从智能爬取到AI视频生成，再到多平台发布 - NewsHub为您提供一站式的内容创作解决方案。

## 🖼️ 界面预览

> 以下为占位图示例，实际项目可替换为真实截图（建议放置于 `public/screenshots/`）。

![主页示意](./public/globe.svg)

![内容管理示意](./public/window.svg)

![发布管理示意](./public/file.svg)
