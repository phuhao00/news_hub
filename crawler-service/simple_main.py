import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import requests
from urllib.parse import urljoin, urlparse
import re
import time

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NewsHub Simple Crawler Service", version="1.0.0")

class CrawlRequest(BaseModel):
    url: str
    extract_content: bool = True
    extract_links: bool = False
    timeout: int = 30

class CrawlResponse(BaseModel):
    url: str
    title: str
    content: str
    text: str
    links: List[str] = []
    crawled_at: datetime
    success: bool
    error_message: str = None

class SimpleCrawlerService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_text_from_html(self, html_content: str) -> str:
        """从HTML中提取纯文本"""
        # 移除脚本和样式标签
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # 清理空白字符
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_title_from_html(self, html_content: str) -> str:
        """从HTML中提取标题"""
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            return title_match.group(1).strip()
        return ''
    
    def extract_links_from_html(self, html_content: str, base_url: str) -> List[str]:
        """从HTML中提取链接"""
        links = []
        link_pattern = r'<a[^>]+href=["\']([^"\'>]+)["\'][^>]*>'
        
        for match in re.finditer(link_pattern, html_content, re.IGNORECASE):
            link = match.group(1)
            # 转换为绝对URL
            absolute_link = urljoin(base_url, link)
            if absolute_link not in links:
                links.append(absolute_link)
        
        return links[:50]  # 限制链接数量
    
    async def crawl_url(self, request: CrawlRequest) -> CrawlResponse:
        """爬取指定URL"""
        try:
            # 发送HTTP请求
            response = self.session.get(request.url, timeout=request.timeout)
            response.raise_for_status()
            
            html_content = response.text
            
            # 提取标题
            title = self.extract_title_from_html(html_content)
            
            # 提取文本内容
            text_content = self.extract_text_from_html(html_content)
            
            # 提取链接
            links = []
            if request.extract_links:
                links = self.extract_links_from_html(html_content, request.url)
            
            return CrawlResponse(
                url=request.url,
                title=title,
                content=html_content[:5000] if request.extract_content else '',  # 限制内容长度
                text=text_content[:2000],  # 限制文本长度
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
                text='',
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
            timeout=30
        )
        return await self.crawl_url(request)

# 全局爬虫服务实例
crawler_service = SimpleCrawlerService()

@app.get("/")
async def root():
    return {"message": "NewsHub Simple Crawler Service is running", "version": "1.0.0"}

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
                    text='',
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
    request = CrawlRequest(url="https://www.nbcnews.com/business")
    result = await crawler_service.crawl_url(request)
    print(f"标题: {result.title}")
    print(f"内容长度: {len(result.text)}")
    print(f"文本预览: {result.text[:200]}...")

if __name__ == "__main__":
    # 可以直接运行示例
    # asyncio.run(example_crawl())
    
    # 或者启动FastAPI服务
    uvicorn.run(
        "simple_main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8001)),
        reload=True
    )