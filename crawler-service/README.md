# NewsHub Crawler Service

基于 crawl4ai 的异步网页爬虫服务，支持多平台内容抓取。

## 功能特性

- 🚀 基于 FastAPI 的高性能异步 API
- 🕷️ 使用 crawl4ai 进行智能网页爬取
- 🔄 支持批量爬取和并发处理
- 📱 支持多个社交媒体平台（微博、抖音、小红书、B站）
- 📰 专门的新闻网站爬取功能
- 🛡️ 内置错误处理和重试机制
- 📊 RESTful API 接口

## 快速开始

### 1. 安装依赖

```bash
cd crawler-service
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件设置配置
```

### 3. 启动服务

```bash
# 方式1: 使用启动脚本
python start.py

# 方式2: 直接运行
python main.py

# 方式3: 使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. 访问 API 文档

打开浏览器访问: http://localhost:8001/docs

## API 接口

### 基础接口

- `GET /` - 服务状态
- `GET /health` - 健康检查

### 爬虫接口

- `POST /crawl` - 通用网页爬取
- `POST /crawl/news` - 新闻网站爬取
- `POST /crawl/batch` - 批量爬取

### 使用示例

#### 1. 基础爬取

```python
import requests

response = requests.post('http://localhost:8001/crawl', json={
    "url": "https://www.nbcnews.com/business",
    "extract_content": True,
    "extract_links": False
})

result = response.json()
print(result['markdown'])
```

#### 2. 新闻爬取

```python
response = requests.post('http://localhost:8001/crawl/news', 
                        params={"url": "https://www.nbcnews.com/business"})
result = response.json()
```

#### 3. 批量爬取

```python
urls = [
    "https://www.nbcnews.com/business",
    "https://www.cnn.com/business",
    "https://www.bbc.com/news/business"
]

response = requests.post('http://localhost:8001/crawl/batch', json=urls)
results = response.json()
```

## 平台支持

### 当前支持的平台

- **微博 (Weibo)** - 社交媒体内容
- **抖音 (Douyin)** - 短视频内容
- **小红书 (Xiaohongshu)** - 生活分享内容
- **B站 (Bilibili)** - 视频内容
- **新闻网站** - 通用新闻内容

### 使用平台爬虫

```python
from crawlers.platforms import CrawlerFactory

# 获取微博爬虫
weibo_crawler = CrawlerFactory.get_crawler('weibo')
posts = await weibo_crawler.crawl_posts('https://weibo.com/u/123456', limit=10)

# 获取支持的平台列表
platforms = CrawlerFactory.get_supported_platforms()
print(platforms)  # ['weibo', 'douyin', 'xiaohongshu', 'bilibili', 'news']
```

## 配置说明

### 环境变量

```env
# 服务配置
PORT=8001                    # 服务端口
LOG_LEVEL=INFO              # 日志级别

# 爬虫配置
CRAWLER_HEADLESS=true       # 无头模式
CRAWLER_TIMEOUT=30          # 超时时间(秒)
CRAWLER_MAX_CONCURRENT=5    # 最大并发数
```

## 开发指南

### 添加新平台支持

1. 在 `crawlers/platforms.py` 中创建新的爬虫类
2. 继承 `PlatformCrawler` 基类
3. 实现 `crawl_posts` 方法
4. 在 `CrawlerFactory` 中注册新平台

```python
class NewPlatformCrawler(PlatformCrawler):
    def __init__(self):
        super().__init__("new_platform")
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        # 实现爬取逻辑
        pass
```

### 项目结构

```
crawler-service/
├── main.py                 # 主应用文件
├── start.py               # 启动脚本
├── requirements.txt       # 依赖包
├── .env.example          # 环境变量示例
├── README.md             # 说明文档
└── crawlers/             # 爬虫模块
    ├── __init__.py
    └── platforms.py      # 平台爬虫实现
```

## 注意事项

1. **反爬机制**: 各平台都有反爬机制，实际使用时需要添加适当的延迟和请求头
2. **法律合规**: 请确保爬取行为符合目标网站的 robots.txt 和服务条款
3. **频率限制**: 建议添加请求频率限制，避免对目标服务器造成压力
4. **数据处理**: 爬取的数据需要进行清洗和验证

## 许可证

MIT License