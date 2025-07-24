import asyncio
import logging
import platform
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import html2text
import re
import json

# Windows上的asyncio事件循环策略修复
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

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

class PostData(BaseModel):
    title: str
    content: str
    author: str
    platform: str
    url: str
    published_at: Optional[datetime] = None
    tags: List[str] = []
    images: List[str] = []
    video_url: Optional[str] = None

class PlatformCrawlRequest(BaseModel):
    creator_url: str
    platform: str
    limit: int = 10

# ==================== 核心爬虫服务 ====================

class UnifiedCrawlerService:
    """统一爬虫服务，整合所有爬虫功能"""
    
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
            logger.info("统一爬虫服务初始化成功")
        except Exception as e:
            logger.error(f"初始化爬虫服务失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.session:
                self.session.close()
                logger.info("统一爬虫服务清理完成")
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

    # ==================== 平台特定爬虫方法 ====================
    
    async def crawl_weibo_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取微博帖子"""
        try:
            posts = []
            # 模拟微博数据（实际使用时需要根据微博API或HTML结构调整）
            for i in range(min(limit, 5)):
                post = PostData(
                    title=f"微博帖子 {i+1}",
                    content=f"这是来自微博的内容 {i+1}，包含了一些有趣的信息...",
                    author="微博用户",
                    platform="weibo",
                    url=f"{creator_url}/post/{i+1}",
                    published_at=datetime.now(),
                    tags=["微博", "社交媒体"]
                )
                posts.append(post)
            return posts
        except Exception as e:
            logger.error(f"爬取微博帖子失败: {e}")
            return []
    
    async def crawl_douyin_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取抖音视频"""
        try:
            posts = []
            # 模拟抖音数据
            for i in range(min(limit, 5)):
                post = PostData(
                    title=f"抖音视频 {i+1}",
                    content=f"这是抖音视频的描述 {i+1}，展示了精彩的内容...",
                    author="抖音创作者",
                    platform="douyin",
                    url=f"{creator_url}/video/{i+1}",
                    published_at=datetime.now(),
                    tags=["抖音", "短视频"],
                    video_url=f"https://example.com/video_{i+1}.mp4"
                )
                posts.append(post)
            return posts
        except Exception as e:
            logger.error(f"爬取抖音视频失败: {e}")
            return []
    
    async def crawl_xiaohongshu_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取小红书笔记"""
        try:
            posts = []
            # 模拟小红书数据
            for i in range(min(limit, 5)):
                post = PostData(
                    title=f"小红书笔记 {i+1}",
                    content=f"这是小红书的笔记内容 {i+1}，分享了生活中的美好瞬间...",
                    author="小红书博主",
                    platform="xiaohongshu",
                    url=f"{creator_url}/note/{i+1}",
                    published_at=datetime.now(),
                    tags=["小红书", "生活分享"],
                    images=[f"https://example.com/image_{i+1}.jpg"]
                )
                posts.append(post)
            return posts
        except Exception as e:
            logger.error(f"爬取小红书笔记失败: {e}")
            return []
    
    async def crawl_bilibili_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取B站视频"""
        try:
            posts = []
            # 模拟B站数据
            for i in range(min(limit, 5)):
                post = PostData(
                    title=f"B站视频 {i+1}",
                    content=f"这是B站视频的简介 {i+1}，包含了精彩的内容和知识分享...",
                    author="B站UP主",
                    platform="bilibili",
                    url=f"{creator_url}/video/BV{i+1}",
                    published_at=datetime.now(),
                    tags=["B站", "视频"],
                    video_url=f"https://example.com/bilibili_video_{i+1}.mp4"
                )
                posts.append(post)
            return posts
        except Exception as e:
            logger.error(f"爬取B站视频失败: {e}")
            return []
    
    async def crawl_news_articles(self, news_url: str, limit: int = 10) -> List[PostData]:
        """爬取新闻文章"""
        try:
            posts = []
            # 模拟新闻数据
            for i in range(min(limit, 5)):
                post = PostData(
                    title=f"新闻文章 {i+1}",
                    content=f"这是新闻文章的内容 {i+1}，报道了最新的时事动态...",
                    author="新闻编辑",
                    platform="news",
                    url=f"{news_url}/article/{i+1}",
                    published_at=datetime.now(),
                    tags=["新闻", "资讯"]
                )
                posts.append(post)
            return posts
        except Exception as e:
            logger.error(f"爬取新闻文章失败: {e}")
            return []
    
    async def crawl_platform_posts(self, request: PlatformCrawlRequest) -> List[PostData]:
        """根据平台类型爬取帖子"""
        platform = request.platform.lower()
        
        if platform == 'weibo':
            return await self.crawl_weibo_posts(request.creator_url, request.limit)
        elif platform == 'douyin':
            return await self.crawl_douyin_posts(request.creator_url, request.limit)
        elif platform == 'xiaohongshu':
            return await self.crawl_xiaohongshu_posts(request.creator_url, request.limit)
        elif platform == 'bilibili':
            return await self.crawl_bilibili_posts(request.creator_url, request.limit)
        elif platform == 'news':
            return await self.crawl_news_articles(request.creator_url, request.limit)
        else:
            raise ValueError(f"不支持的平台: {platform}")

# ==================== 全局服务实例 ====================

crawler_service = UnifiedCrawlerService()

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

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="NewsHub 统一爬虫服务", 
    version="2.0.0",
    description="整合了通用爬虫和平台特定爬虫的统一服务",
    lifespan=lifespan
)

# ==================== API 端点 ====================

@app.get("/")
async def root():
    """健康检查端点"""
    return {
        "message": "NewsHub 统一爬虫服务正在运行", 
        "status": "healthy", 
        "version": "2.0.0",
        "features": ["通用爬虫", "平台爬虫", "批量处理"]
    }

@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "service": "unified-crawler",
        "crawler_initialized": crawler_service.session is not None,
        "timestamp": datetime.now(),
        "supported_platforms": ["weibo", "douyin", "xiaohongshu", "bilibili", "news"],
        "features": ["requests", "beautifulsoup", "html2text", "platform-specific"]
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

@app.post("/crawl/platform")
async def crawl_platform(request: PlatformCrawlRequest):
    """爬取指定平台的创作者内容"""
    try:
        if not crawler_service.session:
            raise HTTPException(status_code=503, detail="爬虫服务未初始化")
        
        posts = await crawler_service.crawl_platform_posts(request)
        return {
            "platform": request.platform,
            "creator_url": request.creator_url,
            "posts": posts,
            "total": len(posts),
            "crawled_at": datetime.now()
        }
    
    except Exception as e:
        logger.error(f"爬取平台内容出错 {request.platform}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/platforms")
async def get_supported_platforms():
    """获取支持的平台列表"""
    return {
        "platforms": [
            {
                "name": "微博",
                "key": "weibo",
                "domain": "weibo.com",
                "supported": True,
                "content_type": "社交媒体帖子"
            },
            {
                "name": "抖音",
                "key": "douyin",
                "domain": "douyin.com",
                "supported": True,
                "content_type": "短视频"
            },
            {
                "name": "小红书",
                "key": "xiaohongshu",
                "domain": "xiaohongshu.com",
                "supported": True,
                "content_type": "生活笔记"
            },
            {
                "name": "哔哩哔哩",
                "key": "bilibili",
                "domain": "bilibili.com",
                "supported": True,
                "content_type": "视频内容"
            },
            {
                "name": "新闻网站",
                "key": "news",
                "domain": "*.news.*",
                "supported": True,
                "content_type": "新闻文章"
            },
            {
                "name": "通用网站",
                "key": "general",
                "domain": "*",
                "supported": True,
                "content_type": "网页内容"
            }
        ],
        "note": "统一爬虫服务，支持通用网页爬取和平台特定内容提取"
    }

@app.get("/status")
async def get_service_status():
    """获取服务状态"""
    return {
        "service": "unified-crawler",
        "version": "2.0.0",
        "status": "running",
        "initialized": crawler_service.session is not None,
        "uptime": datetime.now(),
        "endpoints": [
            "/crawl - 通用URL爬取",
            "/crawl/batch - 批量URL爬取",
            "/crawl/platform - 平台特定爬取",
            "/platforms - 支持的平台列表",
            "/health - 健康检查"
        ]
    }

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8001)),
        reload=False  # 生产环境建议关闭reload
    )