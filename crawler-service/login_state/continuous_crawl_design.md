# 持续爬取服务设计文档

## 概述
当前的ManualCrawlService只执行单次爬取，用户需要一个持续爬取机制：只要停留在页面上就需要持续爬取内容。

## 架构设计

### 1. ContinuousCrawlService类
- 继承或组合ManualCrawlService的功能
- 管理持续爬取任务的生命周期
- 实现页面停留检测和定时爬取

### 2. 核心组件

#### 2.1 页面停留检测器 (PageStayDetector)
- 监控用户是否还在目标页面
- 检测页面URL变化
- 检测浏览器标签页状态
- 检测页面可见性(visibility API)

#### 2.2 定时爬取调度器 (CrawlScheduler)
- 可配置的爬取间隔(默认30秒)
- 智能调度避免资源冲突
- 支持动态调整间隔

#### 2.3 内容去重器 (ContentDeduplicator)
- 基于内容哈希的去重
- 增量内容检测
- 避免重复存储相同内容

#### 2.4 任务管理器 (ContinuousTaskManager)
- 管理持续爬取任务状态
- 处理任务启动、暂停、停止
- 资源清理和错误恢复

### 3. 数据模型

#### 3.1 ContinuousCrawlTask
```python
class ContinuousCrawlTask:
    task_id: str
    session_id: str
    user_id: str
    url: str
    platform: PlatformType
    status: ContinuousTaskStatus  # RUNNING, PAUSED, STOPPED
    config: ContinuousCrawlConfig
    created_at: datetime
    last_crawl_at: datetime
    next_crawl_at: datetime
    crawl_count: int
    content_hashes: List[str]  # 用于去重
```

#### 3.2 ContinuousCrawlConfig
```python
class ContinuousCrawlConfig:
    crawl_interval_seconds: int = 30
    max_crawls: Optional[int] = None
    enable_deduplication: bool = True
    stop_on_no_changes: bool = False
    max_idle_time_seconds: int = 300  # 5分钟无变化后停止
```

### 4. 工作流程

#### 4.1 启动持续爬取
1. 用户访问目标页面
2. 检测到页面稳定后启动持续爬取
3. 创建ContinuousCrawlTask
4. 开始定时爬取循环

#### 4.2 持续爬取循环
1. 检查页面停留状态
2. 如果用户还在页面，执行爬取
3. 内容去重和存储
4. 调度下次爬取
5. 重复循环

#### 4.3 停止条件
- 用户离开页面(URL变化)
- 浏览器标签页关闭
- 手动停止
- 达到最大爬取次数
- 长时间无内容变化

### 5. 集成点

#### 5.1 与BrowserManager集成
- 监听页面导航事件
- 检测页面状态变化
- 管理页面生命周期

#### 5.2 与现有API集成
- 扩展现有的爬取API
- 添加持续爬取控制接口
- 提供任务状态查询

### 6. 性能考虑

#### 6.1 资源管理
- 限制同时运行的持续爬取任务数量
- 智能调整爬取频率
- 及时清理停止的任务

#### 6.2 错误处理
- 网络错误重试机制
- 页面加载失败降级
- 异常情况下的任务恢复

## 实现计划

1. 创建ContinuousCrawlService基础类
2. 实现页面停留检测机制
3. 添加定时爬取调度器
4. 实现内容去重功能
5. 集成到BrowserManager
6. 添加API接口
7. 测试和优化