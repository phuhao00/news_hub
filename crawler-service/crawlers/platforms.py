import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from pydantic import BaseModel
import re
import json

logger = logging.getLogger(__name__)

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

class PlatformCrawler:
    """平台爬虫基类"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.crawler = None
    
    async def initialize(self):
        """初始化爬虫"""
        if not self.crawler:
            self.crawler = AsyncWebCrawler(headless=True, verbose=False)
            await self.crawler.__aenter__()
    
    async def cleanup(self):
        """清理资源"""
        if self.crawler:
            await self.crawler.__aexit__(None, None, None)
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取创作者的帖子"""
        raise NotImplementedError

class WeiboCrawler(PlatformCrawler):
    """微博爬虫"""
    
    def __init__(self):
        super().__init__("weibo")
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取微博帖子"""
        try:
            await self.initialize()
            
            result = await self.crawler.arun(
                url=creator_url,
                css_selector=".card-wrap, .WB_detail, .WB_feed_detail",
                word_count_threshold=10
            )
            
            posts = []
            # 这里需要根据微博的实际HTML结构来解析
            # 由于微博有反爬机制，这里提供一个模拟的实现
            
            # 模拟数据
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
            logger.error(f"Failed to crawl Weibo posts: {e}")
            return []

class DouyinCrawler(PlatformCrawler):
    """抖音爬虫"""
    
    def __init__(self):
        super().__init__("douyin")
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取抖音视频"""
        try:
            await self.initialize()
            
            result = await self.crawler.arun(
                url=creator_url,
                css_selector=".video-info, .aweme-video-meta",
                word_count_threshold=5
            )
            
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
            logger.error(f"Failed to crawl Douyin posts: {e}")
            return []

class XiaohongshuCrawler(PlatformCrawler):
    """小红书爬虫"""
    
    def __init__(self):
        super().__init__("xiaohongshu")
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取小红书笔记"""
        try:
            await self.initialize()
            
            result = await self.crawler.arun(
                url=creator_url,
                css_selector=".note-item, .feeds-page",
                word_count_threshold=10
            )
            
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
            logger.error(f"Failed to crawl Xiaohongshu posts: {e}")
            return []

class BilibiliCrawler(PlatformCrawler):
    """B站爬虫"""
    
    def __init__(self):
        super().__init__("bilibili")
    
    async def crawl_posts(self, creator_url: str, limit: int = 10) -> List[PostData]:
        """爬取B站视频"""
        try:
            await self.initialize()
            
            result = await self.crawler.arun(
                url=creator_url,
                css_selector=".video-episode-card, .bili-video-card",
                word_count_threshold=10
            )
            
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
            logger.error(f"Failed to crawl Bilibili posts: {e}")
            return []

class NewsCrawler(PlatformCrawler):
    """新闻网站爬虫"""
    
    def __init__(self):
        super().__init__("news")
    
    async def crawl_news_articles(self, news_url: str, limit: int = 10) -> List[PostData]:
        """爬取新闻文章"""
        try:
            await self.initialize()
            
            result = await self.crawler.arun(
                url=news_url,
                css_selector="article, .article, .news-item, .story",
                word_count_threshold=50,
                extract_links=True
            )
            
            posts = []
            
            # 提取文章链接
            if hasattr(result, 'links') and result.links:
                article_links = result.links.get('internal', [])[:limit]
                
                # 爬取每篇文章的详细内容
                for link in article_links:
                    try:
                        article_result = await self.crawler.arun(
                            url=link,
                            css_selector="article, .article-content, .story-body",
                            word_count_threshold=100
                        )
                        
                        title = article_result.metadata.get('title', '') if article_result.metadata else ''
                        content = article_result.cleaned_html or ''
                        
                        if title and content:
                            post = PostData(
                                title=title,
                                content=content[:1000] + '...' if len(content) > 1000 else content,
                                author="新闻编辑",
                                platform="news",
                                url=link,
                                published_at=datetime.now(),
                                tags=["新闻", "资讯"]
                            )
                            posts.append(post)
                    except Exception as e:
                        logger.warning(f"Failed to crawl article {link}: {e}")
                        continue
            
            return posts
            
        except Exception as e:
            logger.error(f"Failed to crawl news articles: {e}")
            return []

# 爬虫工厂
class CrawlerFactory:
    """爬虫工厂类"""
    
    _crawlers = {
        'weibo': WeiboCrawler,
        'douyin': DouyinCrawler,
        'xiaohongshu': XiaohongshuCrawler,
        'bilibili': BilibiliCrawler,
        'news': NewsCrawler
    }
    
    @classmethod
    def get_crawler(cls, platform: str) -> PlatformCrawler:
        """获取指定平台的爬虫"""
        crawler_class = cls._crawlers.get(platform.lower())
        if not crawler_class:
            raise ValueError(f"Unsupported platform: {platform}")
        return crawler_class()
    
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """获取支持的平台列表"""
        return list(cls._crawlers.keys())