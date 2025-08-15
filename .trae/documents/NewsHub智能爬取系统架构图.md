# NewsHub智能爬取系统架构图

## 1. 系统整体架构

### 1.1 核心架构图

```mermaid
graph TB
    subgraph "用户层"
        U[用户浏览器]
    end

    subgraph "前端层 (端口:3000)"
        FE[Next.js 15 + React 19]
        FE_UI[用户界面]
        FE_API[API客户端]
    end

    subgraph "后端服务层 (端口:8081)"
        BE[Go + Gin 后端服务]
        BE_API[RESTful API]
        BE_TASK[任务调度器]
        BE_HANDLER[请求处理器]
    end

    subgraph "爬虫服务层 (端口:8001)"
        CR[Python FastAPI 爬虫服务]
        MCP[MCP集成服务]
        WORKER[Worker线程池]
        SCHEDULER[智能调度器]
    end

    subgraph "数据存储层"
        MONGO[(MongoDB:27017)]
        MINIO[(MinIO:9000)]
        REDIS[(Redis:6379)]
    end

    subgraph "外部平台"
        WEIBO[微博]
        DOUYIN[抖音]
        XHS[小红书]
        BILI[B站]
    end

    U --> FE
    FE --> FE_UI
    FE --> FE_API
    FE_API --> BE_API
    BE --> BE_TASK
    BE --> BE_HANDLER
    BE_API --> CR
    CR --> MCP
    CR --> WORKER
    CR --> SCHEDULER
    
    BE --> MONGO
    CR --> MONGO
    CR --> REDIS
    BE --> MINIO
    
    MCP --> WEIBO
    MCP --> DOUYIN
    MCP --> XHS
    MCP --> BILI
```

### 1.2 技术栈分布

| 层级 | 技术栈 | 端口 | 职责 |
|------|--------|------|------|
| 前端层 | Next.js 15 + React 19 + TypeScript + Tailwind CSS | 3000 | 用户界面、数据展示、交互逻辑 |
| 后端层 | Go + Gin + MongoDB | 8081 | API服务、业务逻辑、数据管理 |
| 爬虫层 | Python + FastAPI + Crawl4AI + MCP | 8001 | 智能爬取、内容提取、任务调度 |
| 数据层 | MongoDB + MinIO + Redis | 27017/9000/6379 | 数据存储、文件存储、缓存队列 |

## 2. 服务间通信架构

### 2.1 通信流程图

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端(3000)
    participant BE as 后端(8081)
    participant CR as 爬虫服务(8001)
    participant DB as MongoDB
    participant RD as Redis

    U->>FE: 发起爬取请求
    FE->>BE: POST /api/v1/tasks
    BE->>DB: 创建任务记录
    BE->>CR: POST /crawl/task
    CR->>RD: 任务入队列
    CR->>BE: 返回任务ID
    BE->>FE: 返回任务状态
    FE->>U: 显示任务创建成功
    
    loop 异步处理
        CR->>RD: 获取队列任务
        CR->>CR: 执行爬取逻辑
        CR->>DB: 更新任务状态
        CR->>BE: PUT /api/v1/tasks/{id}/status
    end
    
    U->>FE: 查询任务状态
    FE->>BE: GET /api/v1/tasks/{id}
    BE->>DB: 查询任务信息
    BE->>FE: 返回任务详情
    FE->>U: 显示爬取结果
```

### 2.2 API接口规范

#### 后端API (端口:8081)
```
POST /api/v1/tasks          # 创建爬取任务
GET  /api/v1/tasks/{id}     # 查询任务状态
PUT  /api/v1/tasks/{id}/status # 更新任务状态
GET  /api/v1/tasks          # 获取任务列表
```

#### 爬虫服务API (端口:8001)
```
POST /crawl/task           # 创建爬取任务
GET  /crawl/status/{id}    # 查询爬取状态
POST /crawl/manual         # 手动爬取
GET  /health               # 健康检查
```

## 3. MCP集成架构

### 3.1 MCP服务架构

```mermaid
graph LR
    subgraph "MCP集成层"
        MCP_SERVER[MCP服务器]
        BROWSER_MGR[浏览器管理器]
        SESSION_MGR[会话管理器]
        LOGIN_STATE[登录状态管理]
    end

    subgraph "浏览器实例"
        CHROME1[Chrome实例1]
        CHROME2[Chrome实例2]
        CHROME3[Chrome实例N]
    end

    subgraph "平台适配"
        WEIBO_ADAPTER[微博适配器]
        DOUYIN_ADAPTER[抖音适配器]
        XHS_ADAPTER[小红书适配器]
        BILI_ADAPTER[B站适配器]
    end

    MCP_SERVER --> BROWSER_MGR
    BROWSER_MGR --> SESSION_MGR
    SESSION_MGR --> LOGIN_STATE
    
    BROWSER_MGR --> CHROME1
    BROWSER_MGR --> CHROME2
    BROWSER_MGR --> CHROME3
    
    LOGIN_STATE --> WEIBO_ADAPTER
    LOGIN_STATE --> DOUYIN_ADAPTER
    LOGIN_STATE --> XHS_ADAPTER
    LOGIN_STATE --> BILI_ADAPTER
```

### 3.2 MCP工作流程

1. **浏览器实例管理**
   - 动态创建和销毁Chrome实例
   - 维护登录状态和Cookie
   - 实现会话持久化

2. **平台适配**
   - 针对不同平台的特定逻辑
   - URL识别和内容页检测
   - 反爬虫策略应对

3. **实时爬取触发**
   - 用户导航时自动触发
   - 智能识别目标内容页
   - 异步任务创建和调度

## 4. 异步任务调度架构

### 4.1 任务调度流程

```mermaid
flowchart TD
    START[任务创建] --> VALIDATE[任务验证]
    VALIDATE --> QUEUE[Redis队列]
    
    subgraph "优先级队列"
        HIGH[高优先级队列]
        MEDIUM[中优先级队列]
        LOW[低优先级队列]
    end
    
    QUEUE --> HIGH
    QUEUE --> MEDIUM
    QUEUE --> LOW
    
    subgraph "Worker线程池"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker N]
    end
    
    HIGH --> W1
    MEDIUM --> W2
    LOW --> W3
    
    W1 --> PROCESS[任务处理]
    W2 --> PROCESS
    W3 --> PROCESS
    
    PROCESS --> SUCCESS{处理成功?}
    SUCCESS -->|是| STORE[存储结果]
    SUCCESS -->|否| RETRY[重试机制]
    
    RETRY --> FALLBACK[降级处理]
    FALLBACK --> CRAWL4AI[Crawl4AI爬取]
    CRAWL4AI --> STORE
    
    STORE --> END[任务完成]
```

### 4.2 任务状态管理

| 状态 | 描述 | 下一状态 |
|------|------|----------|
| PENDING | 等待处理 | PROCESSING |
| PROCESSING | 正在处理 | SUCCESS/FAILED |
| SUCCESS | 处理成功 | COMPLETED |
| FAILED | 处理失败 | RETRY/FAILED |
| RETRY | 重试中 | PROCESSING/FAILED |
| COMPLETED | 已完成 | - |

## 5. 智能爬取系统核心组件

### 5.1 智能识别层

```mermaid
graph TD
    URL[输入URL] --> DETECT[URL检测]
    DETECT --> PLATFORM{平台识别}
    
    PLATFORM -->|微博| WEIBO_RULE[微博规则]
    PLATFORM -->|抖音| DOUYIN_RULE[抖音规则]
    PLATFORM -->|小红书| XHS_RULE[小红书规则]
    PLATFORM -->|B站| BILI_RULE[B站规则]
    
    WEIBO_RULE --> CONTENT_CHECK[内容页检测]
    DOUYIN_RULE --> CONTENT_CHECK
    XHS_RULE --> CONTENT_CHECK
    BILI_RULE --> CONTENT_CHECK
    
    CONTENT_CHECK --> VALID{是否内容页}
    VALID -->|是| EXTRACT[内容提取]
    VALID -->|否| SKIP[跳过处理]
```

### 5.2 数据提取层

```mermaid
flowchart LR
    subgraph "提取策略"
        SCREENSHOT[截图提取]
        DOM[DOM解析]
        API[API调用]
    end
    
    subgraph "内容处理"
        CLEAN[内容清洗]
        FORMAT[格式标准化]
        VALIDATE[数据验证]
    end
    
    subgraph "质量评估"
        SCORE[质量评分]
        FILTER[内容过滤]
        ENHANCE[内容增强]
    end
    
    SCREENSHOT --> CLEAN
    DOM --> CLEAN
    API --> CLEAN
    
    CLEAN --> FORMAT
    FORMAT --> VALIDATE
    VALIDATE --> SCORE
    SCORE --> FILTER
    FILTER --> ENHANCE
```

### 5.3 数据流转架构

```mermaid
flowchart TD
    INPUT[原始数据] --> EXTRACT[智能提取]
    EXTRACT --> PROCESS[数据处理]
    PROCESS --> QUALITY[质量评估]
    
    QUALITY --> PASS{质量检查}
    PASS -->|通过| MONGO[(MongoDB存储)]
    PASS -->|失败| FALLBACK[降级处理]
    
    FALLBACK --> CRAWL4AI[Crawl4AI重试]
    CRAWL4AI --> REPROCESS[重新处理]
    REPROCESS --> MONGO
    
    MONGO --> INDEX[建立索引]
    INDEX --> SEARCH[搜索服务]
    
    subgraph "存储结构"
        TASK_COLL[任务集合]
        RESULT_COLL[结果集合]
        LOG_COLL[日志集合]
    end
    
    MONGO --> TASK_COLL
    MONGO --> RESULT_COLL
    MONGO --> LOG_COLL
```

## 6. 部署架构

### 6.1 Docker容器化架构

```mermaid
graph TB
    subgraph "Docker Host"
        subgraph "应用容器"
            FE_CONTAINER[frontend:3000]
            BE_CONTAINER[backend:8081]
            CR_CONTAINER[crawler:8001]
        end
        
        subgraph "数据容器"
            MONGO_CONTAINER[mongodb:27017]
            REDIS_CONTAINER[redis:6379]
            MINIO_CONTAINER[minio:9000]
        end
        
        subgraph "网络"
            NETWORK[newshub-network]
        end
    end
    
    FE_CONTAINER -.-> NETWORK
    BE_CONTAINER -.-> NETWORK
    CR_CONTAINER -.-> NETWORK
    MONGO_CONTAINER -.-> NETWORK
    REDIS_CONTAINER -.-> NETWORK
    MINIO_CONTAINER -.-> NETWORK
```

### 6.2 服务依赖关系

```mermaid
graph TD
    MONGO[MongoDB] --> BE[Backend]
    REDIS[Redis] --> CR[Crawler]
    MINIO[MinIO] --> BE
    
    BE --> FE[Frontend]
    CR --> BE
    
    subgraph "启动顺序"
        S1[1. 数据服务]
        S2[2. 后端服务]
        S3[3. 爬虫服务]
        S4[4. 前端服务]
    end
    
    S1 --> S2
    S2 --> S3
    S3 --> S4
```

### 6.3 配置管理

| 配置文件 | 路径 | 用途 |
|----------|------|------|
| docker-compose.yml | 根目录 | 容器编排配置 |
| config.json | 根目录 | 全局配置 |
| crawler-service/config.json | 爬虫服务 | 爬虫专用配置 |
| .env | 各服务目录 | 环境变量配置 |

## 7. 监控和运维

### 7.1 健康检查

```mermaid
flowchart LR
    subgraph "健康检查"
        FE_HEALTH[前端健康检查]
        BE_HEALTH[后端健康检查]
        CR_HEALTH[爬虫健康检查]
        DB_HEALTH[数据库健康检查]
    end
    
    subgraph "监控指标"
        CPU[CPU使用率]
        MEMORY[内存使用率]
        DISK[磁盘使用率]
        NETWORK[网络状态]
    end
    
    subgraph "日志管理"
        APP_LOG[应用日志]
        ERROR_LOG[错误日志]
        ACCESS_LOG[访问日志]
    end
    
    FE_HEALTH --> CPU
    BE_HEALTH --> MEMORY
    CR_HEALTH --> DISK
    DB_HEALTH --> NETWORK
    
    CPU --> APP_LOG
    MEMORY --> ERROR_LOG
    DISK --> ACCESS_LOG
```

### 7.2 启动脚本

- **start-all.ps1**: 一键启动所有服务
- **stop-all.ps1**: 一键停止所有服务
- **deploy.ps1**: 部署脚本

## 8. 扩展性设计

### 8.1 水平扩展

- **前端**: 支持多实例负载均衡
- **后端**: 无状态设计，支持集群部署
- **爬虫**: Worker线程池动态扩缩容
- **数据库**: MongoDB副本集和分片

### 8.2 功能扩展

- **新平台支持**: 插件化平台适配器
- **AI增强**: 集成更多AI能力
- **实时处理**: 流式数据处理
- **分布式**: 跨节点任务调度

---

*本架构图展示了NewsHub智能爬取系统的完整技术架构，包括各个组件的职责分工、通信方式和数据流转过程，为系统的开发、部署和维护提供了清晰的技术指导。*