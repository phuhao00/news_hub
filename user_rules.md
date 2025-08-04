# NewsHub 项目开发规范

## 📋 项目概述

NewsHub 是一个现代化的新闻聚合和内容管理平台，采用微服务架构，支持多平台内容爬取、视频生成和发布功能。

## 🏗️ 技术栈

### 前端
- **框架**: Next.js 14+ (React 18+)
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **状态管理**: React Hooks
- **构建工具**: Webpack (Next.js 内置)

### 后端
- **语言**: Go 1.21+
- **框架**: Gin Web Framework
- **数据库**: MongoDB
- **容器化**: Docker + Docker Compose

### 爬虫服务
- **语言**: Python 3.9+
- **框架**: FastAPI
- **爬虫库**: BeautifulSoup4, Selenium, Requests
- **异步处理**: asyncio, aiohttp

## 📁 项目结构规范

```
newshub/
├── src/                    # 前端源码
│   ├── app/               # Next.js App Router
│   ├── components/        # 可复用组件
│   ├── types/            # TypeScript 类型定义
│   └── utils/            # 工具函数
├── server/               # Go 后端服务
│   ├── handlers/         # HTTP 处理器
│   ├── models/          # 数据模型
│   ├── middleware/      # 中间件
│   ├── config/          # 配置管理
│   └── utils/           # 工具函数
├── crawler-service/     # Python 爬虫服务
│   ├── crawlers/        # 爬虫实现
│   ├── main.py         # 服务入口
│   └── requirements.txt # Python 依赖
├── docker-compose.yml   # 容器编排
├── nginx.conf          # 反向代理配置
└── start.*             # 一键启动脚本
```

## 🔧 开发环境设置

### 必需工具
- Node.js 18+
- Go 1.21+
- Python 3.9+
- Docker & Docker Compose
- MongoDB (或使用 Docker)

### 环境变量
复制 `.env.example` 为 `.env` 并配置：
```bash
# 数据库配置
MONGODB_URI=mongodb://localhost:27017
DB_NAME=newshub

# 服务端口
BACKEND_PORT=8080
CRAWLER_PORT=8001
FRONTEND_PORT=3000
```

## 📝 编码规范

### TypeScript/JavaScript
- 使用 ESLint + Prettier 进行代码格式化
- 组件使用 PascalCase 命名
- 文件名使用 kebab-case
- 优先使用函数式组件和 Hooks
- 必须添加 TypeScript 类型注解

```typescript
// ✅ 正确示例
interface UserProps {
  id: string;
  name: string;
  email?: string;
}

const UserCard: React.FC<UserProps> = ({ id, name, email }) => {
  return (
    <div className="user-card">
      <h3>{name}</h3>
      {email && <p>{email}</p>}
    </div>
  );
};
```

### Go
- 遵循 Go 官方编码规范
- 使用 gofmt 格式化代码
- 包名使用小写单词
- 导出函数使用 PascalCase
- 私有函数使用 camelCase
- 必须添加错误处理

```go
// ✅ 正确示例
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
)

func GetUsers(c *gin.Context) {
    users, err := userService.GetAllUsers()
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{
            "error": err.Error(),
        })
        return
    }
    
    c.JSON(http.StatusOK, users)
}
```

### Python
- 遵循 PEP 8 编码规范
- 使用 black 进行代码格式化
- 类名使用 PascalCase
- 函数和变量使用 snake_case
- 必须添加类型注解 (Python 3.5+)

```python
# ✅ 正确示例
from typing import List, Optional
from pydantic import BaseModel

class CrawlRequest(BaseModel):
    url: str
    extract_content: bool = True
    css_selector: Optional[str] = None

async def crawl_url(request: CrawlRequest) -> CrawlResponse:
    try:
        # 爬取逻辑
        return CrawlResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        return CrawlResponse(success=False, error=str(e))
```

## 🗄️ 数据库规范

### MongoDB 集合命名
- 使用复数形式: `users`, `posts`, `crawler_tasks`
- 使用下划线分隔: `crawler_contents`, `publish_tasks`

### 索引策略
- 为查询频繁的字段创建索引
- 复合索引按查询频率排序
- 唯一索引防止数据重复

```javascript
// 示例索引
db.crawler_contents.createIndex({ "content_hash": 1 }, { unique: true });
db.posts.createIndex({ "platform": 1, "created_at": -1 });
```

## 🔄 API 设计规范

### RESTful API
- 使用标准 HTTP 方法: GET, POST, PUT, DELETE
- URL 使用名词复数形式: `/api/users`, `/api/posts`
- 状态码使用标准 HTTP 状态码
- 响应格式统一使用 JSON

```json
{
  "success": true,
  "data": {},
  "message": "操作成功",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 错误处理
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数无效",
    "details": []
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 🐳 Docker 使用规范

### Dockerfile 最佳实践
- 使用多阶段构建减少镜像大小
- 合并 RUN 指令减少层数
- 使用 .dockerignore 排除不必要文件
- 不在镜像中存储敏感信息

### docker-compose.yml
- 服务名使用小写
- 使用环境变量配置
- 设置合适的重启策略
- 配置健康检查

## 🧪 测试规范

### 前端测试
- 使用 Jest + React Testing Library
- 组件测试覆盖率 > 80%
- 集成测试覆盖关键用户流程

### 后端测试
- 使用 Go 内置 testing 包
- API 测试覆盖所有端点
- 单元测试覆盖率 > 85%

### 爬虫测试
- 使用 pytest 框架
- Mock 外部 HTTP 请求
- 测试各种异常情况

## 📚 文档规范

### 代码注释
- 公共 API 必须添加注释
- 复杂逻辑添加解释性注释
- 使用统一的注释格式

### README 文档
- 项目简介和功能特点
- 快速开始指南
- API 文档链接
- 贡献指南

## 🔒 安全规范

### 认证授权
- 使用 JWT 进行身份验证
- 实现基于角色的访问控制 (RBAC)
- API 密钥安全存储

### 数据安全
- 敏感数据加密存储
- 输入验证防止注入攻击
- 限制 API 调用频率

## 🚀 部署规范

### 环境管理
- 开发环境 (development)
- 测试环境 (staging)
- 生产环境 (production)

### CI/CD 流程
1. 代码提交触发自动化测试
2. 测试通过后构建 Docker 镜像
3. 部署到测试环境验证
4. 手动确认后部署到生产环境

## 📋 Git 工作流

### 分支策略
- `main`: 生产环境分支
- `develop`: 开发分支
- `feature/*`: 功能分支
- `hotfix/*`: 紧急修复分支

### 提交规范
```
type(scope): description

[optional body]

[optional footer]
```

类型:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

## 🔍 代码审查

### 审查要点
- 代码逻辑正确性
- 性能优化机会
- 安全漏洞检查
- 代码风格一致性
- 测试覆盖率

### 审查流程
1. 创建 Pull Request
2. 自动化测试通过
3. 至少一人代码审查
4. 修复审查意见
5. 合并到目标分支

## 📊 性能监控

### 关键指标
- API 响应时间
- 数据库查询性能
- 内存和 CPU 使用率
- 错误率和可用性

### 监控工具
- 应用性能监控 (APM)
- 日志聚合和分析
- 健康检查端点
- 告警机制

## 🎯 最佳实践

1. **代码质量**: 保持代码简洁、可读、可维护
2. **性能优化**: 避免 N+1 查询，使用缓存，优化数据库索引
3. **错误处理**: 优雅处理错误，提供有意义的错误信息
4. **日志记录**: 记录关键操作和错误信息
5. **配置管理**: 使用环境变量管理配置
6. **依赖管理**: 定期更新依赖，修复安全漏洞
7. **备份策略**: 定期备份数据库和重要文件
8. **文档维护**: 保持文档与代码同步更新

---

**注意**: 本规范是活文档，会根据项目发展和团队反馈持续更新。所有团队成员都应遵循这些规范，确保项目的一致性和可维护性。