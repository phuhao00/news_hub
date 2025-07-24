import asyncio
import logging
import requests
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import re

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlRequest(BaseModel):
    url: str
    extract_content: bool = True
    extract_links: bool = False
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

class MinimalCrawlerService:
    def __init__(self):
        self.session = None
        
    async def initialize(self):
        """初始化爬虫服务"""
        try:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            logger.info("最小化爬虫服务初始化成功")
        except Exception as e:
            logger.error(f"初始化爬虫服务失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.session:
                self.session.close()
                logger.info("最小化爬虫服务清理完成")
        except Exception as e:
            logger.error(f"清理过程中出错: {e}")

    def extract_title(self, html: str) -> str:
        """使用正则表达式提取标题"""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return ""

    def extract_content(self, html: str) -> str:
        """使用正则表达式提取内容"""
        # 移除脚本和样式
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', html)
        
        # 清理空白字符
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    def extract_links(self, html: str, base_url: str) -> List[str]:
        """使用正则表达式提取链接"""
        links = []
        link_pattern = r'<a[^>]+href=["\']([^"\'>]+)["\'][^>]*>'
        matches = re.findall(link_pattern, html, re.IGNORECASE)
        
        for href in matches:
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                # 简单的URL拼接
                if base_url.endswith('/'):
                    links.append(base_url + href[1:])
                else:
                    links.append(base_url + href)
        
        return list(set(links))[:50]  # 去重并限制数量

    async def crawl_url(self, request: CrawlRequest) -> CrawlResponse:
        """爬取指定URL"""
        try:
            if not self.session:
                await self.initialize()
            
            # 发起请求
            response = self.session.get(request.url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            html = response.text
            
            # 提取标题
            title = self.extract_title(html)
            
            # 提取内容
            content = ""
            if request.extract_content:
                content = self.extract_content(html)
                
                # 检查字数阈值
                word_count = len(content.split())
                if word_count < request.word_count_threshold:
                    content = "内容过短或提取失败"
            
            # 提取链接
            links = []
            if request.extract_links:
                links = self.extract_links(html, request.url)
            
            # 简单的Markdown转换
            markdown = content  # 简化版本，直接使用文本内容
            
            return CrawlResponse(
                url=request.url,
                title=title,
                content=content,
                markdown=markdown,
                links=links,
                crawled_at=datetime.now(),
                success=True
            )
            
        except Exception as e:
            logger.error(f"爬取 {request.url} 失败: {e}")
            return CrawlResponse(
                url=request.url,
                title="",
                content="",
                markdown="",
                crawled_at=datetime.now(),
                success=False,
                error_message=str(e)
            )

# 全局爬虫服务实例
crawler_service = MinimalCrawlerService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    try:
        await crawler_service.initialize()
        logger.info("应用启动完成")
    except Exception as e:
        logger.error(f"应用初始化失败: {e}")
        raise
    
    yield
    
    # 关闭时
    try:
        await crawler_service.cleanup()
        logger.info("应用关闭完成")
    except Exception as e:
        logger.error(f"应用关闭过程中出错: {e}")

app = FastAPI(
    title="NewsHub 最小化爬虫服务", 
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """健康检查端点"""
    return {"message": "NewsHub 最小化爬虫服务正在运行", "status": "healthy", "type": "minimal"}

@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "service": "minimal-crawler",
        "crawler_initialized": crawler_service.session is not None,
        "timestamp": datetime.now(),
        "features": ["requests", "regex"]
    }

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest):
    """爬取指定URL的内容"""
    try:
        if not crawler_service.session:
            raise HTTPException(status_code=503, detail="爬虫服务未初始化")
        
        result = await crawler_service.crawl_url(request)
        return result
    
    except Exception as e:
        logger.error(f"爬取URL出错 {request.url}: {e}")
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
            {"name": "通用网站", "domain": "*", "supported": True, "method": "requests+regex"},
            {"name": "新闻网站", "domain": "news.*", "supported": True, "method": "文本提取"},
            {"name": "博客网站", "domain": "blog.*", "supported": True, "method": "内容提取"}
        ],
        "note": "最小化爬虫，仅使用requests和正则表达式，无外部依赖"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)