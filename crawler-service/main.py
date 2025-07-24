import asyncio
import logging
import platform
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

# Windows上的asyncio事件循环策略修复
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlRequest(BaseModel):
    url: str
    extract_content: bool = True
    extract_links: bool = False
    css_selector: str = None
    word_count_threshold: int = 10

class CrawlResponse(BaseModel):
    url: str
    title: str
    content: str
    markdown: str
    links: List[str] = []
    crawled_at: datetime
    success: bool
    error_message: str = None

class CrawlerService:
    def __init__(self):
        self.crawler = None
    
    async def initialize(self):
        """初始化爬虫"""
        try:
            self.crawler = AsyncWebCrawler(
                headless=True,
                verbose=False
            )
            await self.crawler.__aenter__()
            logger.info("Crawler service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize crawler: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.crawler:
                await self.crawler.__aexit__(None, None, None)
                logger.info("Crawler service cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# 全局爬虫服务实例
crawler_service = CrawlerService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    try:
        await crawler_service.initialize()
        logger.info("Application startup completed")
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # 关闭时
    try:
        await crawler_service.cleanup()
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}")

app = FastAPI(
    title="NewsHub Crawler Service", 
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """健康检查端点"""
    return {"message": "NewsHub Crawler Service is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "service": "crawler",
        "crawler_initialized": crawler_service.crawler is not None,
        "timestamp": datetime.now()
    }

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest):
    """爬取指定URL的内容"""
    try:
        if not crawler_service.crawler:
            raise HTTPException(status_code=503, detail="Crawler service not initialized")
        
        # 执行爬取
        result = await crawler_service.crawler.acrawl(
            url=request.url,
            css_selector=request.css_selector,
            word_count_threshold=request.word_count_threshold,
            extraction_strategy="cosine_similarity" if request.extract_content else None
        )
        
        return CrawlResponse(
            url=request.url,
            title=result.metadata.get('title', ''),
            content=result.cleaned_html or '',
            markdown=result.markdown or '',
            links=result.links.get('internal', []) if request.extract_links else [],
            crawled_at=datetime.now(),
            success=result.success,
            error_message=result.error_message if not result.success else None
        )
    
    except Exception as e:
        logger.error(f"Error crawling {request.url}: {e}")
        return CrawlResponse(
            url=request.url,
            title="",
            content="",
            markdown="",
            crawled_at=datetime.now(),
            success=False,
            error_message=str(e)
        )

@app.post("/crawl/batch")
async def crawl_batch(urls: List[str]):
    """批量爬取多个URL"""
    results = []
    for url in urls:
        request = CrawlRequest(url=url)
        result = await crawl_url(request)
        results.append(result)
    return {"results": results, "total": len(results)}

@app.get("/crawl/platforms")
async def get_supported_platforms():
    """获取支持的平台列表"""
    return {
        "platforms": [
            {"name": "Twitter", "domain": "twitter.com", "supported": True},
            {"name": "Reddit", "domain": "reddit.com", "supported": True},
            {"name": "Hacker News", "domain": "news.ycombinator.com", "supported": True},
            {"name": "Medium", "domain": "medium.com", "supported": True},
            {"name": "GitHub", "domain": "github.com", "supported": True},
            {"name": "Stack Overflow", "domain": "stackoverflow.com", "supported": True}
        ]
    }

# 示例爬虫函数
async def example_crawl():
    """示例爬虫函数"""
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
        )
        print(result.markdown)

if __name__ == "__main__":
    # 可以直接运行示例
    # asyncio.run(example_crawl())
    
    # 或者启动FastAPI服务
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8001)),
        reload=True
    )