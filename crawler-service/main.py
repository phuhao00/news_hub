import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NewsHub Crawler Service", version="1.0.0")

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
    
    async def crawl_url(self, request: CrawlRequest) -> CrawlResponse:
        """爬取指定URL"""
        try:
            if not self.crawler:
                await self.initialize()
            
            # 执行爬取
            result = await self.crawler.arun(
                url=request.url,
                css_selector=request.css_selector,
                word_count_threshold=request.word_count_threshold,
                extract_links=request.extract_links
            )
            
            # 提取链接
            links = []
            if request.extract_links and hasattr(result, 'links'):
                links = result.links.get('internal', []) + result.links.get('external', [])
            
            return CrawlResponse(
                url=request.url,
                title=result.metadata.get('title', '') if result.metadata else '',
                content=result.cleaned_html or '',
                markdown=result.markdown or '',
                links=links,
                crawled_at=datetime.now(),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to crawl {request.url}: {e}")
            return CrawlResponse(
                url=request.url,
                title='',
                content='',
                markdown='',
                crawled_at=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def crawl_news_site(self, site_url: str) -> CrawlResponse:
        """专门用于爬取新闻网站"""
        request = CrawlRequest(
            url=site_url,
            extract_content=True,
            extract_links=True,
            css_selector="article, .article, .news-content, .post-content, main",
            word_count_threshold=50
        )
        return await self.crawl_url(request)
    
    async def cleanup(self):
        """清理资源"""
        if self.crawler:
            try:
                await self.crawler.__aexit__(None, None, None)
                logger.info("Crawler service cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

# 全局爬虫服务实例
crawler_service = CrawlerService()

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化爬虫"""
    await crawler_service.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await crawler_service.cleanup()

@app.get("/")
async def root():
    return {"message": "NewsHub Crawler Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest):
    """爬取指定URL"""
    try:
        result = await crawler_service.crawl_url(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/crawl/news", response_model=CrawlResponse)
async def crawl_news(url: str):
    """专门爬取新闻网站"""
    try:
        result = await crawler_service.crawl_news_site(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/crawl/batch", response_model=List[CrawlResponse])
async def crawl_batch(urls: List[str]):
    """批量爬取多个URL"""
    try:
        tasks = []
        for url in urls:
            request = CrawlRequest(url=url)
            tasks.append(crawler_service.crawl_url(request))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(CrawlResponse(
                    url=urls[i],
                    title='',
                    content='',
                    markdown='',
                    crawled_at=datetime.now(),
                    success=False,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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