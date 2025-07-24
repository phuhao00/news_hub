import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import html2text

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

class SimpleCrawlerService:
    def __init__(self):
        self.session = None
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        
    async def initialize(self):
        """初始化爬虫服务"""
        try:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            logger.info("简化爬虫服务初始化成功")
        except Exception as e:
            logger.error(f"初始化爬虫服务失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.session:
                self.session.close()
                logger.info("简化爬虫服务清理完成")
        except Exception as e:
            logger.error(f"清理过程中出错: {e}")

    def extract_content(self, soup: BeautifulSoup, css_selector: Optional[str] = None) -> str:
        """提取页面内容"""
        if css_selector:
            content_elements = soup.select(css_selector)
            if content_elements:
                return ' '.join([elem.get_text(strip=True) for elem in content_elements])
        
        # 默认提取策略
        # 移除脚本和样式
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # 寻找主要内容区域
        main_selectors = [
            'main', 'article', '.content', '.post-content', 
            '.article-content', '.news-content', '#content',
            '.entry-content', '.post-body'
        ]
        
        for selector in main_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return content_elem.get_text(strip=True)
        
        # 如果没找到，使用body
        body = soup.find('body')
        if body:
            return body.get_text(strip=True)
        
        return soup.get_text(strip=True)

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取页面链接"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                from urllib.parse import urljoin
                links.append(urljoin(base_url, href))
        return list(set(links))  # 去重

    async def crawl_url(self, request: CrawlRequest) -> CrawlResponse:
        """爬取指定URL"""
        try:
            if not self.session:
                await self.initialize()
            
            # 发起请求
            response = self.session.get(request.url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 提取内容
            content = ""
            if request.extract_content:
                content = self.extract_content(soup, request.css_selector)
                
                # 检查字数阈值
                word_count = len(content.split())
                if word_count < request.word_count_threshold:
                    content = soup.get_text(strip=True)
            
            # 提取链接
            links = []
            if request.extract_links:
                links = self.extract_links(soup, request.url)
            
            # 转换为Markdown
            markdown = ""
            if content:
                # 从原始HTML生成Markdown
                if request.css_selector:
                    content_elements = soup.select(request.css_selector)
                    if content_elements:
                        html_content = ''.join([str(elem) for elem in content_elements])
                    else:
                        html_content = str(soup)
                else:
                    html_content = str(soup)
                
                markdown = self.html_converter.handle(html_content)
            
            return CrawlResponse(
                url=request.url,
                title=title,
                content=content,
                markdown=markdown,
                links=links[:50],  # 限制链接数量
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
crawler_service = SimpleCrawlerService()

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
    title="NewsHub 简化爬虫服务", 
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """健康检查端点"""
    return {"message": "NewsHub 简化爬虫服务正在运行", "status": "healthy", "type": "simplified"}

@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "service": "simplified-crawler",
        "crawler_initialized": crawler_service.session is not None,
        "timestamp": datetime.now(),
        "features": ["requests", "beautifulsoup", "html2text"]
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
            {"name": "通用网站", "domain": "*", "supported": True, "method": "requests+beautifulsoup"},
            {"name": "新闻网站", "domain": "news.*", "supported": True, "method": "html解析"},
            {"name": "博客网站", "domain": "blog.*", "supported": True, "method": "内容提取"},
            {"name": "GitHub", "domain": "github.com", "supported": True, "method": "静态内容"},
            {"name": "Stack Overflow", "domain": "stackoverflow.com", "supported": True, "method": "问答提取"}
        ],
        "note": "简化版爬虫，不支持JavaScript渲染，但兼容性更好"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)