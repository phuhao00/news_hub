# Manual Crawl Service for Login State Management
# Provides manual crawling functionality for logged-in websites

import asyncio
import logging
import json
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse, urljoin
import re
from enum import Enum

from playwright.async_api import Page, Browser, BrowserContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel, HttpUrl
from bs4 import BeautifulSoup
import html2text

# Crawl4AI imports for intelligent extraction
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

from .models import (
    ManualCrawlRequest,
    CrawlResult,
    CrawlTaskStatus,
    PlatformType,
    CrawlTaskDocument
)

# 持续爬取相关的枚举和模型
class ContinuousTaskStatus(str, Enum):
    """持续爬取任务状态"""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

class ContinuousCrawlConfig(BaseModel):
    """持续爬取配置"""
    crawl_interval_seconds: int = 30
    max_crawls: Optional[int] = None
    enable_deduplication: bool = True
    stop_on_no_changes: bool = False
    max_idle_time_seconds: int = 300  # 5分钟无变化后停止
    content_change_threshold: float = 0.1  # 内容变化阈值

class ContinuousCrawlTask(BaseModel):
    """持续爬取任务"""
    task_id: str
    session_id: str
    user_id: str
    url: str
    platform: PlatformType
    status: ContinuousTaskStatus
    config: ContinuousCrawlConfig
    created_at: datetime
    last_crawl_at: Optional[datetime] = None
    next_crawl_at: Optional[datetime] = None
    crawl_count: int = 0
    content_hashes: List[str] = []
    last_content_hash: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None
from .session_manager import SessionManager
from .browser_manager import BrowserInstanceManager
from .cookie_store import CookieStore

logger = logging.getLogger(__name__)

def convert_objectid_to_str(document: dict) -> dict:
    """Convert MongoDB ObjectId fields to strings for JSON serialization"""
    if document is None:
        return None
    
    # Create a copy to avoid modifying the original
    converted = document.copy()
    
    # Convert _id field if present
    if '_id' in converted and isinstance(converted['_id'], ObjectId):
        converted['_id'] = str(converted['_id'])
    
    # Convert any other ObjectId fields recursively
    for key, value in converted.items():
        if isinstance(value, ObjectId):
            converted[key] = str(value)
        elif isinstance(value, dict):
            converted[key] = convert_objectid_to_str(value)
        elif isinstance(value, list):
            converted[key] = [convert_objectid_to_str(item) if isinstance(item, dict) else str(item) if isinstance(item, ObjectId) else item for item in value]
    
    return converted

class CrawlConfig(BaseModel):
    """Crawl configuration for different platforms"""
    platform: PlatformType
    extraction_schema: Dict[str, str]  # Schema for intelligent extraction
    wait_for: Optional[str] = "networkidle"  # Wait condition for page loading
    scroll_config: Optional[Dict[str, Any]] = None  # Scroll configuration
    custom_scripts: List[str] = []  # Custom JavaScript to execute
    timeout_ms: int = 30000  # Page load timeout
    word_count_threshold: int = 10  # Minimum word count for content
    
class ManualCrawlService:
    """Service for manual crawling of logged-in websites"""
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        session_manager: SessionManager,
        browser_manager: BrowserInstanceManager,
        cookie_store: CookieStore
    ):
        self.db = db
        self.session_manager = session_manager
        self.browser_manager = browser_manager
        self.cookie_store = cookie_store
        self.crawl_tasks = db.crawl_tasks
        
        # Platform-specific crawl configurations with intelligent extraction schemas
        self.platform_configs = {
            PlatformType.WEIBO: CrawlConfig(
                platform=PlatformType.WEIBO,
                extraction_schema={
                    "title": "The main title or headline of the Weibo post",
                    "content": "The main text content of the Weibo post",
                    "author": "The username or display name of the post author",
                    "publish_time": "The publication date and time of the post",
                    "images": "List of image URLs attached to the post",
                    "video": "Video URL if the post contains video content",
                    "likes": "Number of likes or reactions on the post",
                    "reposts": "Number of reposts or shares",
                    "comments": "Number of comments on the post"
                },
                wait_for="networkidle",
                scroll_config={"enabled": True, "max_scrolls": 3, "delay_ms": 1000},
                timeout_ms=15000,
                word_count_threshold=5
            ),
            PlatformType.XIAOHONGSHU: CrawlConfig(
                platform=PlatformType.XIAOHONGSHU,
                extraction_schema={
                    "title": "The title of the Xiaohongshu note or post",
                    "content": "The main description or content text of the note",
                    "author": "The username or nickname of the note author",
                    "publish_time": "The publication date of the note",
                    "images": "List of image URLs in the note",
                    "video": "Video URL if the note contains video",
                    "tags": "List of hashtags or tags associated with the note",
                    "likes": "Number of likes on the note",
                    "comments": "Number of comments on the note"
                },
                wait_for=None,
                scroll_config={"enabled": True, "max_scrolls": 2, "delay_ms": 1500},
                timeout_ms=10000,
                word_count_threshold=10,
                custom_scripts=[
                    "window.scrollTo(0, document.body.scrollHeight);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));"
                ]
            ),
            PlatformType.DOUYIN: CrawlConfig(
                platform=PlatformType.DOUYIN,
                extraction_schema={
                    "title": "The title or caption of the Douyin video",
                    "content": "The description or caption text of the video",
                    "author": "The username of the video creator",
                    "publish_time": "The upload date and time of the video",
                    "video": "The main video URL",
                    "cover": "The video thumbnail or cover image URL",
                    "likes": "Number of likes on the video",
                    "comments": "Number of comments on the video",
                    "shares": "Number of shares of the video"
                },
                wait_for="networkidle",
                scroll_config={"enabled": False},
                timeout_ms=25000,
                word_count_threshold=5
            )
        }
        
        # Initialize Crawl4AI crawler
        self.crawler = None
        
        # 登录状态检测配置
        self.login_indicators = {
            PlatformType.WEIBO: {
                "logged_in_selectors": [".WB_miniblog", ".gn_name", ".Avatar_avatar", ".user-info"],
                "login_required_selectors": [".login", ".WB_login", ".login-panel"],
                "login_url": "https://weibo.com/login.php"
            },
            PlatformType.DOUYIN: {
                "logged_in_selectors": [".user-info", ".avatar", ".user-avatar"],
                "login_required_selectors": [".login-button", ".login-panel", ".login-mask"],
                "login_url": "https://www.douyin.com/passport/web/login/"
            },
            PlatformType.XIAOHONGSHU: {
                "logged_in_selectors": [".user-info", ".avatar-wrapper", ".user-avatar"],
                "login_required_selectors": [".login-container", ".sign-button", ".login-mask"],
                "login_url": "https://www.xiaohongshu.com/explore"
            }
        }
        
        # 性能优化配置
        self.performance_config = {
            "max_content_length": 1024 * 1024,  # 1MB
            "dom_parse_timeout": 10,  # 10秒
            "crawl4ai_timeout": 30,  # 30秒
            "retry_delays": [1, 3, 5],  # 重试延迟
            "max_retries": 3
        }
        
        # 错误处理配置
        self.error_patterns = {
            "network_timeout": ["timeout", "timed out", "connection timeout"],
            "anti_crawler": ["blocked", "captcha", "verification", "robot", "challenge"],
            "login_required": ["login required", "unauthorized", "please login", "sign in"],
            "page_not_found": ["404", "not found", "page not exist"],
            "rate_limit": ["rate limit", "too many requests", "请求过于频繁"]
        }
    
    async def create_crawl_task(
        self,
        request: ManualCrawlRequest,
        user_id: str
    ) -> str:
        """Create a new crawl task"""
        try:
            # Validate session
            session = await self.session_manager.validate_session(request.session_id)
            if not session or session.get('user_id') != user_id:
                raise ValueError("Invalid session")
            
            # Create task document
            task_doc = CrawlTaskDocument(
                task_id=f"crawl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}",
                session_id=request.session_id,
                user_id=user_id,
                platform=session.get('platform'),  # 从session中获取platform
                url=str(request.url),
                status=CrawlTaskStatus.PENDING,
                request_data=request.dict(),  # 保存请求数据
                created_at=datetime.now(timezone.utc)
            )
            
            # Insert task
            await self.crawl_tasks.insert_one(task_doc.dict())
            
            logger.info(f"Created crawl task {task_doc.task_id} for user {user_id}")
            return task_doc.task_id
            
        except Exception as e:
            logger.error(f"Failed to create crawl task: {e}")
            raise
    
    async def execute_crawl_task(self, task_id: str) -> CrawlResult:
        """Execute a crawl task"""
        try:
            # Get task
            task_doc = await self.crawl_tasks.find_one({"task_id": task_id})
            if not task_doc:
                raise ValueError(f"Task {task_id} not found")
            
            logger.info(f"🚀 开始执行爬取任务 - 任务ID: {task_id}, URL: {task_doc['url']}, 平台: {task_doc['platform']}")
            
            # Update task status
            await self.crawl_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": CrawlTaskStatus.RUNNING.value,
                        "started_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Get browser instances for the session
            logger.info(f"Getting browser instances for session {task_doc['session_id']}")
            session_instances = await self.browser_manager.get_session_instances(
                task_doc["session_id"]
            )
            if not session_instances:
                logger.error(f"No browser instances found for session {task_doc['session_id']}")
                raise ValueError(f"No browser instance available for session {task_doc['session_id']}")
            
            logger.info(f"Found {len(session_instances)} browser instances for session {task_doc['session_id']}")
            
            # Select an active instance that's actually available in memory
            selected_instance = None
            instance_id = None
            
            for instance in session_instances:
                temp_instance_id = instance.get('instance_id')
                logger.debug(f"Checking instance {temp_instance_id}: active={instance.get('is_active', False)}")
                
                if instance.get("is_active", False):
                    # Verify the instance is actually available in memory
                    if temp_instance_id in self.browser_manager.browsers:
                        logger.info(f"Found available instance {temp_instance_id} in memory")
                        selected_instance = instance
                        instance_id = temp_instance_id
                        break
                    else:
                        logger.warning(f"Instance {temp_instance_id} is marked active in DB but not found in memory")
            
            if not selected_instance or not instance_id:
                # Log detailed information for debugging
                memory_instances = list(self.browser_manager.browsers.keys())
                db_instances = [inst.get('instance_id') for inst in session_instances if inst.get('is_active', False)]
                logger.error(f"No available browser instances found for session {task_doc['session_id']}")
                logger.error(f"DB active instances: {db_instances}")
                logger.error(f"Memory instances: {memory_instances}")
                raise ValueError(f"No available browser instance found for session {task_doc['session_id']}. DB has {len(db_instances)} active instances, memory has {len(memory_instances)} instances.")
            
            logger.info(f"Selected browser instance {instance_id} for crawl task {task_id}")
            
            # Get the browser instance using instance_id (this should now succeed)
            browser_instance = await self.browser_manager.get_browser_instance(instance_id)
            if not browser_instance:
                logger.error(f"Failed to get browser instance details for {instance_id} despite being in memory")
                raise ValueError(f"Failed to get browser instance details for {instance_id}")
            
            # Get the page from the browser manager's pages dictionary
            main_page_key = f"{instance_id}_main"
            page = self.browser_manager.pages.get(main_page_key)
            if not page:
                logger.error(f"No page available for browser instance {instance_id} (key: {main_page_key})")
                logger.debug(f"Available page keys: {list(self.browser_manager.pages.keys())}")
                raise ValueError(f"No page available in browser instance {instance_id}")
            
            logger.info(f"Successfully obtained page for crawl task {task_id} using instance {instance_id}")
            
            # Execute crawl
            result = await self._crawl_page(
                page,
                task_doc["url"],
                PlatformType(task_doc["platform"]),
                task_doc.get("config", {})
            )
            
            # Set the missing fields in the result
            result.task_id = task_id
            result.session_id = task_doc["session_id"]
            
            # Update task with result
            await self.crawl_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": CrawlTaskStatus.COMPLETED.value,
                        "result": result.dict(),
                        "completed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            logger.info(f"Completed crawl task {task_id}")
            return result
            
        except Exception as e:
            # Update task with error
            await self.crawl_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": CrawlTaskStatus.FAILED.value,
                        "error": str(e),
                        "failed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            logger.error(f"Failed to execute crawl task {task_id}: {e}")
            raise
    
    async def _crawl_page(
        self,
        page: Page,
        url: str,
        platform: PlatformType,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> CrawlResult:
        """Crawl a single page using Playwright HTML content with Crawl4AI intelligent extraction"""
        start_time = time.time()
        
        try:
            logger.info(f"📄 开始爬取页面内容 - URL: {url}, 平台: {platform}")
            
            # 检查登录状态
            login_status = await self._check_login_status(page, platform)
            if not login_status:
                logger.warning(f"检测到未登录状态，尝试自动重新登录: {url}")
                await self._attempt_auto_login(page, platform)
            else:
                logger.info(f"✅ 登录状态验证通过 - URL: {url}")
            
            # Get platform config
            config = self.platform_configs.get(platform)
            if not config:
                raise ValueError(f"Unsupported platform: {platform}")
            
            # Merge custom config
            if custom_config:
                config_dict = config.dict()
                config_dict.update(custom_config)
                config = CrawlConfig(**config_dict)
            
            # Get HTML content from the Playwright page
            logger.info(f"📥 获取页面HTML内容 - URL: {url}")
            html_content = await page.content()
            logger.info(f"📊 HTML内容获取完成 - 大小: {len(html_content)} bytes, URL: {url}")
            
            # 检查内容长度并截断
            if len(html_content) > self.performance_config["max_content_length"]:
                logger.warning(f"HTML内容过长 ({len(html_content)} bytes)，截断处理")
                html_content = html_content[:self.performance_config["max_content_length"]]
            
            # 反爬虫检测
            if await self._detect_anti_crawler(html_content, page):
                logger.warning(f"检测到反爬虫机制，等待后重试: {url}")
                await asyncio.sleep(5)  # 等待5秒
                html_content = await page.content()
            
            # Try Crawl4AI processing first, fallback to basic processing
            logger.info(f"🤖 尝试使用Crawl4AI智能提取 - URL: {url}")
            try:
                crawl4ai_result = await asyncio.wait_for(
                    self._process_html_with_crawl4ai(html_content, url, platform),
                    timeout=self.performance_config["crawl4ai_timeout"]
                )
                if crawl4ai_result:
                    # Convert Crawl4AI result to CrawlResult format
                    result = self._convert_crawl4ai_result(crawl4ai_result, url)
                    processing_time = time.time() - start_time
                    logger.info(f"✅ Crawl4AI智能提取成功 - URL: {url}, 耗时: {processing_time:.2f}s, 内容长度: {len(result.content) if result.content else 0} 字符")
                    return result
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Crawl4AI处理超时，回退到基础处理: {url}")
            except Exception as e:
                error_type = self._classify_error(str(e))
                logger.warning(f"❌ Crawl4AI处理失败 ({error_type})，回退到基础处理: {e}")
            
            # Fallback to basic HTML processing
            logger.info(f"🔧 使用基础HTML处理方法 - URL: {url}")
            result = await self._process_html_content(html_content, url, platform, config)
            processing_time = time.time() - start_time
            logger.info(f"✅ 基础处理完成 - URL: {url}, 耗时: {processing_time:.2f}s, 内容长度: {len(result.content) if result.content else 0} 字符")
            return result
            
        except Exception as e:
            error_type = self._classify_error(str(e))
            processing_time = time.time() - start_time
            logger.error(f"页面爬取失败 {url} ({error_type}) - 耗时: {processing_time:.2f}s: {e}")
            
            # 根据错误类型决定是否重试
            if error_type in ["network_timeout", "rate_limit"]:
                await asyncio.sleep(3)  # 等待后可能重试
            
            return CrawlResult(
                task_id="",
                session_id="",  # Will be set by caller
                url=url,
                status=CrawlTaskStatus.FAILED,
                title="",
                content=json.dumps({"error": str(e), "error_type": error_type}, ensure_ascii=False),
                links=[],
                images=[],
                metadata={
                    "error": str(e),
                    "error_type": error_type,
                    "processing_time": processing_time,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "extraction_method": "crawl4ai_llm_failed"
                },
                error_message=str(e),
                created_at=datetime.now(timezone.utc)
            )
    
    async def _process_html_content(
        self,
        html_content: str,
        url: str,
        platform: PlatformType,
        config: CrawlConfig
    ) -> CrawlResult:
        """Process HTML content directly without network requests"""
        start_time = time.time()  # 添加start_time变量定义
        try:
            logger.info(f"Processing HTML content for {url} (platform: {platform.value})")
            
            # 性能优化：限制HTML内容大小，避免内存过度使用
            max_html_size = self.performance_config.get("max_html_size", 5 * 1024 * 1024)  # 5MB
            if len(html_content) > max_html_size:
                logger.warning(f"HTML content too large ({len(html_content)} bytes), truncating to {max_html_size} bytes")
                html_content = html_content[:max_html_size]
            
            # 性能优化：使用lxml解析器（更快）
            try:
                soup = BeautifulSoup(html_content, 'lxml')
            except:
                # 回退到html.parser
                soup = BeautifulSoup(html_content, 'html.parser')
            
            # 性能优化：一次性提取所有需要的元素，避免多次遍历DOM
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else ""
            
            # 性能优化：批量移除不需要的元素
            for element in soup(["script", "style", "noscript", "iframe"]):
                element.decompose()
            
            # 性能优化：限制链接和图片提取数量
            max_links = self.performance_config.get("max_links_extract", 50)
            max_images = self.performance_config.get("max_images_extract", 30)
            
            # 一次性提取链接和图片
            link_elements = soup.find_all('a', href=True, limit=max_links)
            img_elements = soup.find_all('img', src=True, limit=max_images)
            
            # 性能优化：使用列表推导式，更高效
            links = [{
                'url': link['href'],
                'text': link.get_text().strip()[:100],  # 限制文本长度
                'title': link.get('title', '')[:100]
            } for link in link_elements]
            
            images = [{
                'url': img['src'],
                'alt': img.get('alt', '')[:100],
                'title': img.get('title', '')[:100]
            } for img in img_elements]
            
            # 性能优化：延迟文本内容提取，只在需要时进行
            text_content = None
            content = None
            
            # 性能优化：延迟初始化文本内容提取函数
            def get_text_content():
                nonlocal text_content, content
                if text_content is None:
                    text_content = soup.get_text()
                    lines = (line.strip() for line in text_content.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    content = '\n'.join(chunk for chunk in chunks if chunk)
                return text_content, content
            
            # Try to use Crawl4AI for intelligent extraction if available
            extracted_data = {}
            crawl4ai_timeout = self.performance_config.get("crawl4ai_timeout", 30)  # 30秒超时
            
            try:
                # 性能优化：添加超时控制
                async with asyncio.timeout(crawl4ai_timeout):
                    if not self.crawler:
                        browser_config = BrowserConfig(
                            headless=True,
                            browser_type="chromium"
                        )
                        self.crawler = AsyncWebCrawler(config=browser_config)
                        logger.info("Crawl4AI crawler initialized for HTML processing")
                    
                    # Create extraction strategy with platform-specific schema
                    extraction_strategy = LLMExtractionStrategy(
                        llm_config=LLMConfig(provider="openai"),
                        schema=config.extraction_schema,
                        extraction_type="schema",
                        instruction=f"Extract structured data from this {platform.value} page. Focus on the main content, author information, engagement metrics, and media URLs. Ensure all extracted text is clean and properly formatted."
                    )
                    
                    # Configure crawler run settings for HTML processing
                    run_config = CrawlerRunConfig(
                        word_count_threshold=config.word_count_threshold,
                        extraction_strategy=extraction_strategy,
                        bypass_cache=True  # Don't use cache for HTML processing
                    )
                    
                    # Process HTML with Crawl4AI (no network request)
                    result = await self.crawler.arun(
                        url=url,
                        html=html_content,
                        config=run_config
                    )
                    
                    if result.success and result.extracted_content:
                        try:
                            if isinstance(result.extracted_content, str):
                                extracted_data = json.loads(result.extracted_content)
                            else:
                                extracted_data = result.extracted_content
                            
                            # Handle case where extracted_data is a list
                            if isinstance(extracted_data, list):
                                if extracted_data:
                                    extracted_data = {"items": extracted_data}
                                else:
                                    extracted_data = {}
                            
                            logger.info(f"Crawl4AI extraction successful: {list(extracted_data.keys()) if isinstance(extracted_data, dict) else 'list format'}")
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Failed to parse Crawl4AI extracted content: {e}")
                            extracted_data = {}
                    else:
                        logger.warning("Crawl4AI extraction failed, using fallback")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Crawl4AI processing timeout after {crawl4ai_timeout}s, using fallback extraction")
            except Exception as e:
                logger.warning(f"Crawl4AI processing failed: {e}, using fallback extraction")
            
            # Fallback extraction if Crawl4AI failed
            if not extracted_data:
                # 性能优化：使用延迟加载的文本内容
                text_content, content = get_text_content()
                
                # Convert links and images to URL strings using unified method
                fallback_links = self._extract_urls_from_result(links[:10])
                fallback_images = self._extract_urls_from_result(images[:10])
                
                extracted_data = {
                    "title": title,
                    "content": content[:2000] if content else "",  # Limit content length
                    "links": fallback_links,  # Convert to URL strings
                    "images": fallback_images,  # Convert to URL strings
                    "text_length": len(content) if content else 0,
                    "extraction_method": "fallback_beautifulsoup"
                }
                logger.info(f"Using fallback BeautifulSoup extraction - Title: {title[:50]}{'...' if len(title) > 50 else ''}, Content length: {len(content) if content else 0}, Links: {len(fallback_links)}, Images: {len(fallback_images)}")
            
            # 性能监控：记录处理时间
            processing_end_time = time.time()
            processing_time = processing_end_time - start_time
            
            # 详细日志记录
            logger.info(f"HTML processing completed for {platform.value} - URL: {url[:100]}{'...' if len(url) > 100 else ''}")
            logger.info(f"Processing metrics - Time: {processing_time:.2f}s, HTML size: {len(html_content)} bytes, Title: {title[:50]}{'...' if len(title) > 50 else ''}")
            logger.info(f"Extraction results - Links: {len(links)}, Images: {len(images)}, Content length: {len(content) if content else 0} chars")
            
            # Prepare metadata with performance metrics
            metadata = {
                "url": url,
                "platform": platform.value,
                "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
                "word_count": len(content.split()) if content else 0,
                "success": True,
                "page_title": title,
                "content_length": len(html_content),
                "link_count": len(links),
                "image_count": len(images),
                "extraction_method": "html_processing_with_playwright",
                "processing_time_seconds": round(processing_time, 2),
                "html_size_bytes": len(html_content),
                "performance_metrics": {
                    "dom_parsing_optimized": True,
                    "lazy_text_extraction": True,
                    "crawl4ai_timeout": crawl4ai_timeout,
                    "content_truncated": len(html_content) > self.performance_config.get("max_html_size", 1000000)
                }
            }
            
            # Add meta tag information
            for meta in soup.find_all('meta'):
                name = meta.get('name') or meta.get('property')
                content_attr = meta.get('content')
                if name and content_attr:
                    metadata[f'meta_{name}'] = content_attr
            
            # Convert content to JSON string for storage
            content_json = json.dumps(extracted_data, ensure_ascii=False, default=str)
            
            # Convert links and images to string lists for CrawlResult model using unified method
            result_links = self._extract_urls_from_result(extracted_data.get("links", []))
            if not result_links:  # Fallback to BeautifulSoup extracted links
                result_links = self._extract_urls_from_result(links)
            
            result_images = self._extract_urls_from_result(extracted_data.get("images", []))
            if not result_images:  # Fallback to BeautifulSoup extracted images
                result_images = self._extract_urls_from_result(images)
            
            # Also extract from media_urls if available
            if "media_urls" in extracted_data:
                media_links = self._extract_urls_from_result(extracted_data["media_urls"])
                result_images.extend([url for url in media_links if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov'])])
                result_links.extend([url for url in media_links if not any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov'])])
            
            # Remove duplicates and limit count
            result_links = list(dict.fromkeys(result_links))[:20]  # Remove duplicates and limit
            result_images = list(dict.fromkeys(result_images))[:20]  # Remove duplicates and limit
            
            # 计算数据质量分数
            quality_score = self._calculate_data_quality_score(extracted_data)
            metadata["data_quality_score"] = quality_score
            
            # 如果质量分数较低，尝试增强fallback
            if quality_score < 0.5:
                logger.info(f"Low quality extraction (score: {quality_score}), trying enhanced fallback")
                enhanced_result = self._enhanced_fallback_extraction(html_content)
                
                if enhanced_result and (enhanced_result.get("title") or enhanced_result.get("content")):
                    # 合并结果，优先使用质量更好的数据
                    merged_result = self._merge_extraction_results(extracted_data, enhanced_result)
                    content_json = json.dumps(merged_result, ensure_ascii=False, default=str)
                    
                    # 更新链接和图片
                    result_links = self._extract_urls_from_result(merged_result.get("links", []))
                    result_images = self._extract_urls_from_result(merged_result.get("images", []))
                    
                    # 更新质量分数
                    quality_score = self._calculate_data_quality_score(merged_result)
                    metadata["data_quality_score"] = quality_score
                    metadata["extraction_method"] = "enhanced_fallback_merged"
            
            return CrawlResult(
                task_id="",  # Will be set by caller
                session_id="",  # Will be set by caller
                url=url,
                status=CrawlTaskStatus.COMPLETED,
                title=extracted_data.get("title", title),
                content=content_json,
                links=result_links,
                images=result_images,
                metadata=metadata,
                created_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Failed to process HTML content for {url}: {e}")
            return CrawlResult(
                task_id="",
                session_id="",
                url=url,
                status=CrawlTaskStatus.FAILED,
                title="",
                content=json.dumps({"error": str(e)}, ensure_ascii=False),
                links=[],
                images=[],
                metadata={
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "extraction_method": "crawl4ai_llm_with_playwright_failed"
                },
                error_message=str(e),
                created_at=datetime.now(timezone.utc)
            )
    
    async def _process_html_with_crawl4ai(self, html_content: str, url: str, platform: PlatformType) -> Optional[Dict[str, Any]]:
        """使用Crawl4AI直接处理HTML内容，避免重复网络请求"""
        try:
            # 创建Crawl4AI客户端
            async with AsyncWebCrawler(
                 headless=True,
                 browser_type="chromium",
                 verbose=False
             ) as crawler:
                # 根据平台定制提取策略
                extraction_strategy = self._get_extraction_strategy(platform)
                
                # 直接处理HTML内容，避免重复请求
                # 使用Crawl4AI的HTML处理能力而不是网络爬取
                from crawl4ai.content_filter import ContentFilter
                from crawl4ai.markdown_generation import MarkdownGenerator
                from crawl4ai.extraction_strategy import ExtractionStrategy
                
                # 创建内容过滤器和Markdown生成器
                content_filter = ContentFilter()
                markdown_generator = MarkdownGenerator()
                
                # 清理HTML内容
                cleaned_html = content_filter.filter_content(html_content)
                
                # 生成Markdown
                markdown_content = markdown_generator.generate_markdown(
                    cleaned_html,
                    base_url=url
                )
                
                # 应用提取策略
                extracted_content = {}
                if extraction_strategy and hasattr(extraction_strategy, 'extract'):
                    try:
                        extraction_result = await extraction_strategy.extract(
                            url=url,
                            html=cleaned_html,
                            markdown=markdown_content
                        )
                        
                        if isinstance(extraction_result, str):
                            extracted_content = json.loads(extraction_result)
                        else:
                            extracted_content = extraction_result
                    except Exception as e:
                        logger.warning(f"Extraction strategy failed for {url}: {e}")
                        # 使用基础提取作为fallback
                        extracted_content = self._basic_content_extraction(cleaned_html, markdown_content)
                else:
                    # 使用基础提取
                    extracted_content = self._basic_content_extraction(cleaned_html, markdown_content)
                
                return {
                    "title": extracted_content.get("title", ""),
                    "content": extracted_content.get("content", markdown_content or ""),
                    "author": extracted_content.get("author", ""),
                    "publish_time": extracted_content.get("publish_time", ""),
                    "tags": extracted_content.get("tags", []),
                    "summary": extracted_content.get("summary", ""),
                    "links": extracted_content.get("links", []),
                    "images": extracted_content.get("images", []),
                    "metadata": {
                        "extraction_method": "crawl4ai_html_direct",
                        "platform": platform.value,
                        "content_length": len(markdown_content or ""),
                        "success": True
                    }
                }
                    
        except Exception as e:
            logger.error(f"Error in Crawl4AI HTML processing for {url}: {e}")
            return None
    
    def _get_extraction_strategy(self, platform: PlatformType):
         """获取平台特定的提取策略"""
         try:
             # 根据平台创建优化的提取指令
             platform_instructions = {
                 PlatformType.WEIBO: """
                 从微博页面提取以下信息：
                 1. 标题：微博正文内容的前50个字符作为标题
                 2. 内容：完整的微博正文，包括话题标签和@用户
                 3. 作者：发布者的用户名和认证信息
                 4. 发布时间：准确的发布时间戳
                 5. 互动数据：点赞数、转发数、评论数
                 6. 媒体文件：图片、视频的完整URL
                 7. 话题标签：#话题#格式的标签
                 8. 位置信息：如果有地理位置标记
                 """,
                 PlatformType.DOUYIN: """
                 从抖音页面提取以下信息：
                 1. 标题：视频标题或描述文字
                 2. 内容：视频描述、话题标签、背景音乐信息
                 3. 作者：创作者用户名、粉丝数、认证状态
                 4. 发布时间：视频发布的时间
                 5. 互动数据：点赞数、评论数、分享数、播放量
                 6. 媒体文件：视频封面图、视频URL
                 7. 音乐信息：背景音乐名称和作者
                 8. 挑战话题：参与的挑战或话题
                 """,
                 PlatformType.XIAOHONGSHU: """
                 从小红书页面提取以下信息：
                 1. 标题：笔记标题
                 2. 内容：笔记正文内容，包括商品链接和标签
                 3. 作者：博主用户名、粉丝数、等级信息
                 4. 发布时间：笔记发布时间
                 5. 互动数据：点赞数、收藏数、评论数
                 6. 媒体文件：图片URL列表，视频URL
                 7. 商品信息：关联的商品链接和价格
                 8. 标签：笔记相关的标签和分类
                 """,
                 PlatformType.BILIBILI: """
                 从B站页面提取以下信息：
                 1. 标题：视频标题
                 2. 内容：视频简介、分P信息、相关链接
                 3. 作者：UP主用户名、粉丝数、等级
                 4. 发布时间：视频发布时间
                 5. 互动数据：播放量、点赞数、投币数、收藏数、分享数
                 6. 媒体文件：视频封面、视频URL
                 7. 分区信息：视频所属分区和标签
                 8. 弹幕数：弹幕总数
                 """
             }
             
             instruction = platform_instructions.get(platform, 
                 f"Extract structured data from this {platform.value} page. Focus on the main content, author information, engagement metrics, and media URLs.")
             
             # 创建LLM提取策略
             try:
                 from crawl4ai.extraction_strategy import LLMExtractionStrategy
                 from crawl4ai import LLMConfig
                 
                 return LLMExtractionStrategy(
                     llm_config=LLMConfig(provider="openai"),
                     extraction_type="schema",
                     instruction=instruction,
                     schema={
                         "type": "object",
                         "properties": {
                             "title": {"type": "string", "description": "内容标题"},
                             "content": {"type": "string", "description": "主要内容"},
                             "author": {"type": "string", "description": "作者信息"},
                             "publish_time": {"type": "string", "description": "发布时间"},
                             "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
                             "summary": {"type": "string", "description": "内容摘要"},
                             "engagement": {
                                 "type": "object",
                                 "properties": {
                                     "likes": {"type": "integer"},
                                     "shares": {"type": "integer"},
                                     "comments": {"type": "integer"},
                                     "views": {"type": "integer"}
                                 }
                             },
                             "media_urls": {
                                 "type": "object",
                                 "properties": {
                                     "images": {"type": "array", "items": {"type": "string"}},
                                     "videos": {"type": "array", "items": {"type": "string"}}
                                 }
                             }
                         },
                         "required": ["title", "content", "author"]
                     }
                 )
             except ImportError:
                 logger.warning("Crawl4AI LLM extraction not available, using basic extraction")
                 return None
                 
         except Exception as e:
             logger.warning(f"Failed to create extraction strategy for {platform}: {e}")
             return None
    
    def _basic_content_extraction(self, html_content: str, markdown_content: str) -> Dict[str, Any]:
        """基础内容提取作为fallback"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取标题
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # 提取链接
            links = []
            for link in soup.find_all('a', href=True):
                links.append({
                    'url': link['href'],
                    'text': link.get_text().strip()
                })
            
            # 提取图片
            images = []
            for img in soup.find_all('img', src=True):
                images.append({
                    'url': img['src'],
                    'alt': img.get('alt', '')
                })
            
            return {
                "title": title,
                "content": markdown_content or "",
                "links": links[:10],  # 限制数量
                "images": images[:10],  # 限制数量
                "extraction_method": "basic_fallback"
            }
        except Exception as e:
            logger.error(f"Basic content extraction failed: {e}")
            return {"content": markdown_content or "", "extraction_method": "minimal_fallback"}
    
    def _enhanced_fallback_extraction(self, html_content: str) -> Dict[str, Any]:
        """增强的fallback提取机制"""
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 智能标题提取
            title = self._extract_smart_title(soup)
            
            # 智能内容提取
            content = self._extract_smart_content(soup)
            
            # 智能作者提取
            author = self._extract_smart_author(soup)
            
            # 提取时间信息
            publish_time = self._extract_publish_time(soup)
            
            # 提取标签
            tags = self._extract_tags(soup)
            
            # 提取互动数据
            engagement = self._extract_engagement_data(soup)
            
            # 提取媒体URL
            media_urls = self._extract_media_urls(soup)
            
            return {
                'title': title,
                'content': content,
                'author': author,
                'publish_time': publish_time,
                'tags': tags,
                'summary': content[:200] + '...' if len(content) > 200 else content,
                'engagement': engagement,
                'media_urls': media_urls
            }
            
        except Exception as e:
            logger.error(f"Enhanced fallback extraction failed: {e}")
            return {
                'title': '',
                'content': '',
                'author': '',
                'publish_time': '',
                'tags': [],
                'summary': '',
                'engagement': {},
                'media_urls': {'images': [], 'videos': []}
            }
    
    def _extract_smart_title(self, soup) -> str:
        """智能标题提取"""
        # 优先级顺序的标题选择器
        title_selectors = [
            'h1',
            '.title',
            '[data-title]',
            '.post-title',
            '.article-title',
            'title'
        ]
        
        for selector in title_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 5:  # 过滤太短的标题
                    return text
        
        return ''
    
    def _extract_smart_content(self, soup) -> str:
        """智能内容提取"""
        # 移除不需要的元素
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # 内容选择器优先级
        content_selectors = [
            '.content',
            '.post-content',
            '.article-content',
            'main',
            '.main-content',
            'article',
            '.text'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 50:  # 过滤太短的内容
                    return text
        
        # 如果没有找到特定内容区域，提取body中的文本
        body = soup.find('body')
        if body:
            return body.get_text().strip()
        
        return soup.get_text().strip()
    
    def _extract_smart_author(self, soup) -> str:
        """智能作者提取"""
        author_selectors = [
            '.author',
            '.username',
            '.user-name',
            '[data-author]',
            '.post-author',
            '.by-author'
        ]
        
        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text:
                    return text
        
        return ''
    
    def _extract_publish_time(self, soup) -> str:
        """提取发布时间"""
        time_selectors = [
            'time',
            '.time',
            '.date',
            '.publish-time',
            '[datetime]'
        ]
        
        for selector in time_selectors:
            elements = soup.select(selector)
            for element in elements:
                # 尝试获取datetime属性
                datetime_attr = element.get('datetime')
                if datetime_attr:
                    return datetime_attr
                
                # 获取文本内容
                text = element.get_text().strip()
                if text:
                    return text
        
        return ''
    
    def _extract_tags(self, soup) -> List[str]:
        """提取标签"""
        tags = []
        tag_selectors = [
            '.tag',
            '.tags a',
            '.hashtag',
            '[data-tag]'
        ]
        
        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and text not in tags:
                    tags.append(text)
        
        return tags[:10]  # 限制标签数量
    
    def _extract_engagement_data(self, soup) -> Dict[str, int]:
        """提取互动数据"""
        engagement = {}
        
        # 查找包含数字的元素，可能是互动数据
        import re
        number_pattern = re.compile(r'\d+[kKwW万千百十]?')
        
        engagement_selectors = [
            '.like', '.likes',
            '.share', '.shares',
            '.comment', '.comments',
            '.view', '.views'
        ]
        
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                numbers = number_pattern.findall(text)
                if numbers:
                    key = selector.replace('.', '').replace('s', '')  # 标准化键名
                    engagement[key] = self._parse_number(numbers[0])
        
        return engagement
    
    def _extract_media_urls(self, soup) -> Dict[str, List[str]]:
        """提取媒体URL"""
        images = []
        videos = []
        
        # 提取图片
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src and not src.startswith('data:'):  # 排除base64图片
                images.append(src)
        
        # 提取视频
        for video in soup.find_all('video', src=True):
            videos.append(video['src'])
        
        for source in soup.find_all('source', src=True):
            videos.append(source['src'])
        
        return {
            'images': images[:10],  # 限制数量
            'videos': videos[:5]
        }
    
    def _parse_number(self, text: str) -> int:
        """解析数字文本（支持k、w等单位）"""
        try:
            text = text.lower().replace(',', '')
            if 'k' in text:
                return int(float(text.replace('k', '')) * 1000)
            elif 'w' in text or '万' in text:
                return int(float(text.replace('w', '').replace('万', '')) * 10000)
            else:
                return int(text)
        except:
            return 0
    
    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ''
        
        import re
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        # 移除特殊字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        return text
    
    def _clean_tags(self, tags) -> List[str]:
        """清理标签列表"""
        if not tags:
            return []
        
        cleaned_tags = []
        for tag in tags:
            if isinstance(tag, str):
                cleaned_tag = self._clean_text(tag)
                if cleaned_tag and cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
        
        return cleaned_tags[:10]  # 限制数量
    
    def _normalize_engagement(self, engagement) -> Dict[str, int]:
        """标准化互动数据"""
        if not isinstance(engagement, dict):
            return {}
        
        normalized = {}
        for key, value in engagement.items():
            try:
                if isinstance(value, (int, float)):
                    normalized[key] = int(value)
                elif isinstance(value, str):
                    normalized[key] = self._parse_number(value)
            except:
                continue
        
        return normalized
    
    def _normalize_media_urls(self, media_urls) -> Dict[str, List[str]]:
        """标准化媒体URL"""
        if not isinstance(media_urls, dict):
            return {'images': [], 'videos': []}
        
        result = {'images': [], 'videos': []}
        
        for key in ['images', 'videos']:
            urls = media_urls.get(key, [])
            if isinstance(urls, list):
                valid_urls = []
                for url in urls:
                    if isinstance(url, str) and url.strip():
                        valid_urls.append(url.strip())
                result[key] = valid_urls[:10]  # 限制数量
        
        return result
    
    def _convert_crawl4ai_result(self, crawl4ai_result: Dict[str, Any], url: str) -> CrawlResult:
        """将Crawl4AI结果转换为CrawlResult格式，包含增强的数据处理"""
        try:
            # 处理链接和图片，确保是字符串列表
            links = self._extract_urls_from_result(crawl4ai_result.get("links", []))
            images = self._extract_urls_from_result(crawl4ai_result.get("images", []))
            
            # 如果没有直接的links和images，尝试从media_urls获取
            if not links or not images:
                media_urls = crawl4ai_result.get("media_urls", {})
                if isinstance(media_urls, dict):
                    if not links:
                        links = self._extract_urls_from_result(media_urls.get("images", []))
                    if not images:
                        images = self._extract_urls_from_result(media_urls.get("videos", []))
            
            # 数据质量验证和清理
            title = self._clean_text(crawl4ai_result.get("title", ""))
            content = crawl4ai_result.get("content", "")
            
            # 如果关键数据缺失，记录警告
            if not title and not content:
                logger.warning(f"Both title and content are empty for URL: {url}")
            
            # 准备内容JSON
            content_json = json.dumps(crawl4ai_result, ensure_ascii=False, default=str)
            
            return CrawlResult(
                task_id="",  # Will be set by caller
                session_id="",  # Will be set by caller
                url=url,
                status=CrawlTaskStatus.COMPLETED,
                title=title,
                content=content_json,
                links=links,
                images=images,
                metadata={
                    **crawl4ai_result.get("metadata", {}),
                    "data_quality_score": self._calculate_data_quality_score(crawl4ai_result)
                },
                created_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.error(f"Failed to convert Crawl4AI result: {e}")
            # 返回基础结果
            return CrawlResult(
                task_id="",
                session_id="",
                url=url,
                status=CrawlTaskStatus.COMPLETED,
                title=crawl4ai_result.get("title", ""),
                content=json.dumps(crawl4ai_result, ensure_ascii=False, default=str),
                links=[],
                images=[],
                metadata={"conversion_error": str(e)},
                created_at=datetime.now(timezone.utc)
            )
    
    def _merge_extraction_results(self, primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
         """合并两个提取结果，优先使用质量更好的数据"""
         merged = primary.copy()
         
         # 合并标题（优先使用更长的有效标题）
         primary_title = primary.get('title', '').strip()
         fallback_title = fallback.get('title', '').strip()
         if len(fallback_title) > len(primary_title) and len(fallback_title) > 5:
             merged['title'] = fallback_title
         
         # 合并内容（优先使用更长的有效内容）
         primary_content = primary.get('content', '').strip()
         fallback_content = fallback.get('content', '').strip()
         if len(fallback_content) > len(primary_content) and len(fallback_content) > 50:
             merged['content'] = fallback_content
         
         # 合并作者信息
         if not merged.get('author') and fallback.get('author'):
             merged['author'] = fallback['author']
         
         # 合并时间信息
         if not merged.get('publish_time') and fallback.get('publish_time'):
             merged['publish_time'] = fallback['publish_time']
         
         # 合并标签
         primary_tags = merged.get('tags', [])
         fallback_tags = fallback.get('tags', [])
         if isinstance(fallback_tags, list) and fallback_tags:
             all_tags = list(primary_tags) if isinstance(primary_tags, list) else []
             for tag in fallback_tags:
                 if tag not in all_tags:
                     all_tags.append(tag)
             merged['tags'] = all_tags[:10]
         
         # 合并互动数据
         primary_engagement = merged.get('engagement', {})
         fallback_engagement = fallback.get('engagement', {})
         if isinstance(fallback_engagement, dict) and fallback_engagement:
             merged_engagement = primary_engagement.copy() if isinstance(primary_engagement, dict) else {}
             for key, value in fallback_engagement.items():
                 if key not in merged_engagement or not merged_engagement[key]:
                     merged_engagement[key] = value
             merged['engagement'] = merged_engagement
         
         # 合并媒体URL
         primary_media = merged.get('media_urls', {})
         fallback_media = fallback.get('media_urls', {})
         if isinstance(fallback_media, dict):
             merged_media = primary_media.copy() if isinstance(primary_media, dict) else {}
             for media_type in ['images', 'videos']:
                 primary_urls = merged_media.get(media_type, [])
                 fallback_urls = fallback_media.get(media_type, [])
                 if isinstance(fallback_urls, list) and fallback_urls:
                     all_urls = list(primary_urls) if isinstance(primary_urls, list) else []
                     for url in fallback_urls:
                         if url not in all_urls:
                             all_urls.append(url)
                     merged_media[media_type] = all_urls[:10]
             merged['media_urls'] = merged_media
         
         # 合并链接和图片（为了兼容性）
         if not merged.get('links') and fallback.get('links'):
             merged['links'] = fallback['links']
         if not merged.get('images') and fallback.get('images'):
             merged['images'] = fallback['images']
         
         return merged
    
    def _extract_urls_from_result(self, urls_data) -> List[str]:
         """从结果中提取URL字符串列表"""
         if not urls_data:
             return []
         
         if isinstance(urls_data, list):
             result = []
             for item in urls_data:
                 if isinstance(item, str):
                     result.append(item)
                 elif isinstance(item, dict) and item.get('url'):
                     result.append(item['url'])
             return result[:10]  # 限制数量
         
         return []
    
    def _convert_enhanced_result(self, enhanced_result: Dict[str, Any], url: str) -> CrawlResult:
         """将增强fallback结果转换为CrawlResult格式"""
         try:
             # 提取和清理数据
             title = self._clean_text(enhanced_result.get('title', ''))
             content = enhanced_result.get('content', '')
             
             # 处理媒体URL
             media_urls = enhanced_result.get('media_urls', {})
             links = self._extract_urls_from_result(media_urls.get('images', []))
             images = self._extract_urls_from_result(media_urls.get('videos', []))
             
             # 如果没有媒体URL，尝试从links和images字段获取
             if not links:
                 links = self._extract_urls_from_result(enhanced_result.get('links', []))
             if not images:
                 images = self._extract_urls_from_result(enhanced_result.get('images', []))
             
             # 准备内容JSON
             content_json = json.dumps(enhanced_result, ensure_ascii=False, default=str)
             
             # 计算质量分数
             quality_score = self._calculate_data_quality_score(enhanced_result)
             
             return CrawlResult(
                 task_id="",
                 session_id="",
                 url=url,
                 status=CrawlTaskStatus.COMPLETED,
                 title=title,
                 content=content_json,
                 links=links,
                 images=images,
                 metadata={
                     "extraction_method": "enhanced_fallback",
                     "data_quality_score": quality_score,
                     "author": enhanced_result.get('author', ''),
                     "publish_time": enhanced_result.get('publish_time', ''),
                     "tags": enhanced_result.get('tags', []),
                     "engagement": enhanced_result.get('engagement', {})
                 },
                 created_at=datetime.now(timezone.utc)
             )
             
         except Exception as e:
             logger.error(f"Failed to convert enhanced result: {e}")
             return CrawlResult(
                 task_id="",
                 session_id="",
                 url=url,
                 status=CrawlTaskStatus.FAILED,
                 title="",
                 content=json.dumps({"error": str(e)}, ensure_ascii=False),
                 links=[],
                 images=[],
                 metadata={"conversion_error": str(e), "data_quality_score": 0.0},
                 created_at=datetime.now(timezone.utc)
             )
    
    def _calculate_data_quality_score(self, data: Dict[str, Any]) -> float:
         """计算数据质量分数"""
         score = 0.0
         
         # 标题质量 (30%)
         title = data.get('title', '')
         if title:
             score += 0.3 * min(len(title) / 50, 1.0)
         
         # 内容质量 (40%)
         content = data.get('content', '')
         if content:
             score += 0.4 * min(len(content) / 200, 1.0)
         
         # 作者信息 (10%)
         if data.get('author'):
             score += 0.1
         
         # 时间信息 (10%)
         if data.get('publish_time'):
             score += 0.1
         
         # 媒体文件 (10%)
         media_urls = data.get('media_urls', {})
         if media_urls.get('images') or media_urls.get('videos'):
             score += 0.1
         
         return round(score, 2)
    
    async def cleanup(self):
        """Cleanup Crawl4AI resources"""
        if self.crawler:
            try:
                # In newer versions of Crawl4AI, cleanup is handled automatically
                # or through context managers
                logger.info("Crawl4AI crawler cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up Crawl4AI crawler: {e}")
            finally:
                self.crawler = None
    
    async def get_crawl_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get crawl task by ID"""
        task = await self.crawl_tasks.find_one({"task_id": task_id})
        return convert_objectid_to_str(task) if task else None
    
    async def list_crawl_tasks(
        self,
        user_id: str,
        platform: Optional[PlatformType] = None,
        status: Optional[CrawlTaskStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List crawl tasks for a user"""
        query = {"user_id": user_id}
        
        if platform:
            query["platform"] = platform.value
        
        if status:
            query["status"] = status.value
        
        cursor = self.crawl_tasks.find(query)
        cursor = cursor.sort("created_at", -1).skip(offset).limit(limit)
        
        tasks = await cursor.to_list(length=limit)
        return [convert_objectid_to_str(task) for task in tasks]
    
    async def delete_crawl_task(self, task_id: str, user_id: str) -> bool:
        """Delete a crawl task"""
        result = await self.crawl_tasks.delete_one({
            "task_id": task_id,
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """Clean up old crawl tasks"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.crawl_tasks.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        
        logger.info(f"Cleaned up {result.deleted_count} old crawl tasks")
        return result.deleted_count
    
    async def get_crawl_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get crawl statistics"""
        query = {}
        if user_id:
            query["user_id"] = user_id
        
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        status_counts = {}
        async for doc in self.crawl_tasks.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Platform statistics
        platform_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$platform",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        platform_counts = {}
        async for doc in self.crawl_tasks.aggregate(platform_pipeline):
            platform_counts[doc["_id"]] = doc["count"]
        
        total_tasks = await self.crawl_tasks.count_documents(query)
        
        return {
            "total_tasks": total_tasks,
            "status_distribution": status_counts,
            "platform_distribution": platform_counts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _classify_error(self, error_message: str) -> str:
        """错误分类"""
        error_message_lower = error_message.lower()
        
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern.lower() in error_message_lower:
                    return error_type
        
        return "unknown"
    

    
    async def _check_login_status(self, page: Page, platform: PlatformType) -> bool:
        """检查登录状态"""
        try:
            if platform not in self.login_indicators:
                return True  # 未配置检测规则，假设已登录
            
            indicators = self.login_indicators[platform]
            
            # 检查登录状态指示器
            for selector in indicators["logged_in_selectors"]:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.debug(f"找到登录状态指示器: {selector}")
                        return True
                except Exception:
                    continue
            
            # 检查是否需要登录
            for selector in indicators["login_required_selectors"]:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.warning(f"找到登录要求指示器: {selector}")
                        return False
                except Exception:
                    continue
            
            # 默认假设已登录
            return True
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return True  # 出错时假设已登录，避免阻塞
    
    async def _detect_anti_crawler(self, html_content: str, page: Page) -> bool:
        """检测反爬虫机制"""
        try:
            # 检查HTML内容中的反爬虫关键词
            anti_crawler_keywords = [
                "captcha", "verification", "robot", "blocked", 
                "challenge", "请完成验证", "人机验证", "滑动验证"
            ]
            
            html_lower = html_content.lower()
            for keyword in anti_crawler_keywords:
                if keyword in html_lower:
                    logger.warning(f"在HTML中检测到反爬虫关键词: {keyword}")
                    return True
            
            # 检查页面标题
            try:
                title = await page.title()
                title_lower = title.lower()
                for keyword in anti_crawler_keywords:
                    if keyword in title_lower:
                        logger.warning(f"在页面标题中检测到反爬虫关键词: {keyword}")
                        return True
            except Exception:
                pass
            
            # 检查特定的反爬虫元素
            anti_crawler_selectors = [
                ".captcha", "#captcha", ".verification", ".challenge",
                "[class*='captcha']", "[id*='captcha']", "[class*='verify']"
            ]
            
            for selector in anti_crawler_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.warning(f"检测到反爬虫元素: {selector}")
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"反爬虫检测失败: {e}")
            return False


class ContinuousCrawlService:
    """持续爬取服务"""
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        session_manager: SessionManager,
        browser_manager: BrowserInstanceManager,
        cookie_store: CookieStore
    ):
        self.db = db
        self.session_manager = session_manager
        self.browser_manager = browser_manager
        self.cookie_store = cookie_store
        self.continuous_tasks = db.continuous_crawl_tasks
        self.manual_crawl_service = ManualCrawlService(
            db, session_manager, browser_manager, cookie_store
        )
        
        # 活跃的持续爬取任务
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_locks: Dict[str, asyncio.Lock] = {}
        
    async def start_continuous_crawl(
        self,
        session_id: str,
        user_id: str,
        url: str,
        platform: PlatformType,
        config: Optional[ContinuousCrawlConfig] = None
    ) -> str:
        """启动持续爬取任务"""
        try:
            # 验证会话
            session = await self.session_manager.validate_session(session_id)
            if not session or session.get('user_id') != user_id:
                raise ValueError("Invalid session")
            
            # 使用默认配置
            if config is None:
                config = ContinuousCrawlConfig()
            
            # 创建任务ID
            task_id = f"continuous_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}"
            
            # 检查是否已有相同URL的活跃任务
            existing_task = await self.continuous_tasks.find_one({
                "session_id": session_id,
                "url": url,
                "status": {"$in": [ContinuousTaskStatus.RUNNING.value, ContinuousTaskStatus.PAUSED.value]}
            })
            
            if existing_task:
                logger.warning(f"Continuous crawl task already exists for URL {url} in session {session_id}")
                return existing_task["task_id"]
            
            # 创建任务文档
            task = ContinuousCrawlTask(
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                url=url,
                platform=platform,
                status=ContinuousTaskStatus.RUNNING,
                config=config,
                created_at=datetime.now(timezone.utc),
                next_crawl_at=datetime.now(timezone.utc)
            )
            
            # 保存到数据库
            await self.continuous_tasks.insert_one(task.dict())
            
            # 启动持续爬取任务
            crawl_task = asyncio.create_task(self._continuous_crawl_loop(task_id))
            self.active_tasks[task_id] = crawl_task
            self.task_locks[task_id] = asyncio.Lock()
            
            logger.info(f"Started continuous crawl task {task_id} for URL {url}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start continuous crawl: {e}")
            raise
    
    async def stop_continuous_crawl(self, task_id: str, user_id: str) -> bool:
        """停止持续爬取任务"""
        try:
            # 验证任务所有权
            task_doc = await self.continuous_tasks.find_one({
                "task_id": task_id,
                "user_id": user_id
            })
            
            if not task_doc:
                logger.warning(f"Continuous crawl task {task_id} not found for user {user_id}")
                return False
            
            # 更新任务状态
            await self.continuous_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": ContinuousTaskStatus.STOPPED.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # 取消活跃任务
            if task_id in self.active_tasks:
                self.active_tasks[task_id].cancel()
                del self.active_tasks[task_id]
            
            if task_id in self.task_locks:
                del self.task_locks[task_id]
            
            logger.info(f"Stopped continuous crawl task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop continuous crawl task {task_id}: {e}")
            return False
    
    async def _continuous_crawl_loop(self, task_id: str):
        """持续爬取循环"""
        try:
            while True:
                # 获取任务状态
                task_doc = await self.continuous_tasks.find_one({"task_id": task_id})
                if not task_doc:
                    logger.warning(f"Continuous crawl task {task_id} not found, stopping loop")
                    break
                
                task_status = ContinuousTaskStatus(task_doc["status"])
                
                # 检查是否应该停止
                if task_status in [ContinuousTaskStatus.STOPPED, ContinuousTaskStatus.ERROR]:
                    logger.info(f"Continuous crawl task {task_id} status is {task_status}, stopping loop")
                    break
                
                # 如果任务暂停，等待后继续检查
                if task_status == ContinuousTaskStatus.PAUSED:
                    await asyncio.sleep(5)
                    continue
                
                # 检查是否到了爬取时间
                now = datetime.now(timezone.utc)
                next_crawl_at = task_doc.get("next_crawl_at")
                if next_crawl_at:
                    # 确保 next_crawl_at 是带时区的 datetime
                    if next_crawl_at.tzinfo is None:
                        next_crawl_at = next_crawl_at.replace(tzinfo=timezone.utc)
                    
                    if now < next_crawl_at:
                        sleep_time = (next_crawl_at - now).total_seconds()
                        await asyncio.sleep(min(sleep_time, 5))  # 最多睡眠5秒
                        continue
                
                # 检查页面停留状态
                if not await self._check_page_stay(task_doc):
                    logger.info(f"User left page for task {task_id}, stopping continuous crawl")
                    await self.stop_continuous_crawl(task_id, task_doc["user_id"])
                    break
                
                # 执行爬取
                await self._execute_continuous_crawl(task_id)
                
                # 等待下次爬取间隔
                config = ContinuousCrawlConfig(**task_doc["config"])
                await asyncio.sleep(min(config.crawl_interval_seconds, 60))  # 最大间隔60秒
                
        except asyncio.CancelledError:
            logger.info(f"Continuous crawl task {task_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in continuous crawl loop for task {task_id}: {e}")
            # 更新任务状态为错误
            await self.continuous_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": ContinuousTaskStatus.ERROR.value,
                        "last_error": str(e),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$inc": {"error_count": 1}
                }
            )
        finally:
            # 清理资源
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            if task_id in self.task_locks:
                del self.task_locks[task_id]
    
    async def _check_page_stay(self, task_doc: Dict[str, Any]) -> bool:
        """检查用户是否还在页面上"""
        try:
            session_id = task_doc["session_id"]
            target_url = task_doc["url"]
            
            # 获取会话的浏览器实例
            session_instances = await self.browser_manager.get_session_instances(session_id)
            if not session_instances:
                return False
            
            # 检查是否有活跃实例在目标页面
            for instance in session_instances:
                if not instance.get("is_active", False):
                    continue
                
                instance_id = instance.get("instance_id")
                if not instance_id or instance_id not in self.browser_manager.browsers:
                    continue
                
                # 检查页面URL
                main_page_key = f"{instance_id}_main"
                page = self.browser_manager.pages.get(main_page_key)
                if page:
                    try:
                        current_url = page.url
                        # 简单的URL匹配检查
                        if self._urls_match(current_url, target_url):
                            return True
                    except Exception as e:
                        logger.warning(f"Failed to get page URL for instance {instance_id}: {e}")
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check page stay: {e}")
            return False
    
    def _urls_match(self, current_url: str, target_url: str) -> bool:
        """检查URL是否匹配"""
        try:
            # 解析URL
            current_parsed = urlparse(current_url)
            target_parsed = urlparse(target_url)
            
            # 比较域名和路径
            return (
                current_parsed.netloc == target_parsed.netloc and
                current_parsed.path == target_parsed.path
            )
        except Exception:
            return current_url == target_url
    
    async def _execute_continuous_crawl(self, task_id: str):
        """执行单次持续爬取"""
        async with self.task_locks.get(task_id, asyncio.Lock()):
            try:
                # 获取任务信息
                task_doc = await self.continuous_tasks.find_one({"task_id": task_id})
                if not task_doc:
                    return
                
                config = ContinuousCrawlConfig(**task_doc["config"])
                
                # 创建临时的手动爬取任务
                manual_request = ManualCrawlRequest(
                    session_id=task_doc["session_id"],
                    url=task_doc["url"],
                    platform=PlatformType(task_doc["platform"]),
                    config=task_doc.get("manual_config", {})
                )
                
                # 创建手动爬取任务
                manual_task_id = await self.manual_crawl_service.create_crawl_task(
                    manual_request,
                    task_doc["user_id"]
                )
                
                # 执行爬取
                result = await self.manual_crawl_service.execute_crawl_task(manual_task_id)
                
                # 处理爬取结果
                if result.success:
                    await self._process_crawl_result(task_id, result, config)
                else:
                    logger.warning(f"Crawl failed for continuous task {task_id}: {result.metadata.get('error')}")
                    await self._handle_crawl_error(task_id, result.metadata.get('error', 'Unknown error'))
                
            except Exception as e:
                logger.error(f"Failed to execute continuous crawl for task {task_id}: {e}")
                await self._handle_crawl_error(task_id, str(e))
    
    async def _process_crawl_result(
        self,
        task_id: str,
        result: CrawlResult,
        config: ContinuousCrawlConfig
    ):
        """处理爬取结果"""
        try:
            # 计算内容哈希
            content_hash = self._calculate_content_hash(result.content)
            
            # 获取当前任务状态
            task_doc = await self.continuous_tasks.find_one({"task_id": task_id})
            if not task_doc:
                return
            
            # 检查内容去重
            is_duplicate = False
            if config.enable_deduplication:
                last_hash = task_doc.get("last_content_hash")
                if last_hash == content_hash:
                    is_duplicate = True
                    logger.debug(f"Duplicate content detected for task {task_id}")
            
            # 更新任务状态
            now = datetime.now(timezone.utc)
            next_crawl_at = now + timedelta(seconds=config.crawl_interval_seconds)
            
            update_data = {
                "last_crawl_at": now,
                "next_crawl_at": next_crawl_at,
                "updated_at": now,
                "$inc": {"crawl_count": 1}
            }
            
            if not is_duplicate:
                update_data["last_content_hash"] = content_hash
                update_data["$push"] = {
                    "content_hashes": {
                        "$each": [content_hash],
                        "$slice": -10  # 只保留最近10个哈希
                    }
                }
            
            await self.continuous_tasks.update_one(
                {"task_id": task_id},
                update_data
            )
            
            # 检查是否应该停止（无变化停止条件）
            if config.stop_on_no_changes and is_duplicate:
                crawl_count = task_doc.get("crawl_count", 0)
                if crawl_count >= 3:  # 连续3次无变化则停止
                    logger.info(f"Stopping continuous crawl task {task_id} due to no content changes")
                    await self.stop_continuous_crawl(task_id, task_doc["user_id"])
            
            # 检查最大爬取次数
            if config.max_crawls and task_doc.get("crawl_count", 0) >= config.max_crawls:
                logger.info(f"Stopping continuous crawl task {task_id} due to max crawls reached")
                await self.stop_continuous_crawl(task_id, task_doc["user_id"])
            
        except Exception as e:
            logger.error(f"Failed to process crawl result for task {task_id}: {e}")
    
    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        """计算内容哈希"""
        try:
            # 提取主要内容字段
            main_content = {
                "title": content.get("title", ""),
                "content": content.get("content", ""),
                "author": content.get("author", "")
            }
            
            # 序列化并计算哈希
            content_str = json.dumps(main_content, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(content_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate content hash: {e}")
            return ""
    
    async def _handle_crawl_error(self, task_id: str, error_message: str):
        """处理爬取错误"""
        try:
            await self.continuous_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "last_error": error_message,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$inc": {"error_count": 1}
                }
            )
            
            # 如果错误次数过多，停止任务
            task_doc = await self.continuous_tasks.find_one({"task_id": task_id})
            if task_doc and task_doc.get("error_count", 0) >= 5:
                logger.warning(f"Stopping continuous crawl task {task_id} due to too many errors")
                await self.continuous_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"status": ContinuousTaskStatus.ERROR.value}}
                )
                
        except Exception as e:
            logger.error(f"Failed to handle crawl error for task {task_id}: {e}")
    
    async def get_continuous_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取持续爬取任务"""
        task = await self.continuous_tasks.find_one({"task_id": task_id})
        return convert_objectid_to_str(task) if task else None
    
    async def list_continuous_tasks(
        self,
        user_id: str,
        status: Optional[ContinuousTaskStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的持续爬取任务"""
        query = {"user_id": user_id}
        
        if status:
            query["status"] = status.value
        
        cursor = self.continuous_tasks.find(query)
        cursor = cursor.sort("created_at", -1).skip(offset).limit(limit)
        
        tasks = await cursor.to_list(length=limit)
        return [convert_objectid_to_str(task) for task in tasks]
    
    async def cleanup_stopped_tasks(self, days: int = 7) -> int:
        """清理已停止的任务"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.continuous_tasks.delete_many({
            "status": {"$in": [ContinuousTaskStatus.STOPPED.value, ContinuousTaskStatus.ERROR.value]},
            "updated_at": {"$lt": cutoff_date}
        })
        
        logger.info(f"Cleaned up {result.deleted_count} stopped continuous crawl tasks")
        return result.deleted_count
    
    async def _check_login_status(self, page: Page, platform: PlatformType) -> bool:
        """检查登录状态"""
        try:
            if platform not in self.login_indicators:
                return True  # 未配置检测规则，假设已登录
            
            indicators = self.login_indicators[platform]
            
            # 检查登录状态指示器
            for selector in indicators["logged_in_selectors"]:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.debug(f"找到登录状态指示器: {selector}")
                        return True
                except Exception:
                    continue
            
            # 检查是否需要登录
            for selector in indicators["login_required_selectors"]:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.warning(f"找到登录要求指示器: {selector}")
                        return False
                except Exception:
                    continue
            
            # 默认假设已登录
            return True
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return True  # 出错时假设已登录，避免阻塞
    
    async def _attempt_auto_login(self, page: Page, platform: PlatformType):
        """尝试自动重新登录"""
        try:
            if platform not in self.login_indicators:
                logger.warning(f"平台 {platform.value} 未配置自动登录")
                return
            
            login_url = self.login_indicators[platform]["login_url"]
            current_url = page.url
            
            # 如果当前不在登录页面，导航到登录页面
            if login_url not in current_url:
                logger.info(f"导航到登录页面: {login_url}")
                await page.goto(login_url, wait_until="networkidle")
                await asyncio.sleep(3)  # 等待页面加载
            
            # 这里可以添加更复杂的自动登录逻辑
            # 目前只是导航到登录页面，实际登录需要用户手动完成
            logger.info(f"已导航到登录页面，请手动完成登录: {login_url}")
            
        except Exception as e:
            logger.error(f"自动登录尝试失败: {e}")
    
    def _classify_error(self, error_message: str) -> str:
        """错误分类"""
        error_message_lower = error_message.lower()
        
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern.lower() in error_message_lower:
                    return error_type
        
        return "unknown"
    
    async def _detect_anti_crawler(self, html_content: str, page: Page) -> bool:
        """检测反爬虫机制"""
        try:
            # 检查HTML内容中的反爬虫关键词
            anti_crawler_keywords = [
                "captcha", "verification", "robot", "blocked", 
                "challenge", "请完成验证", "人机验证", "滑动验证"
            ]
            
            html_lower = html_content.lower()
            for keyword in anti_crawler_keywords:
                if keyword in html_lower:
                    logger.warning(f"在HTML中检测到反爬虫关键词: {keyword}")
                    return True
            
            # 检查页面标题
            try:
                title = await page.title()
                title_lower = title.lower()
                for keyword in anti_crawler_keywords:
                    if keyword in title_lower:
                        logger.warning(f"在页面标题中检测到反爬虫关键词: {keyword}")
                        return True
            except Exception:
                pass
            
            # 检查特定的反爬虫元素
            anti_crawler_selectors = [
                ".captcha", "#captcha", ".verification", ".challenge",
                "[class*='captcha']", "[id*='captcha']", "[class*='verify']"
            ]
            
            for selector in anti_crawler_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.warning(f"检测到反爬虫元素: {selector}")
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"反爬虫检测失败: {e}")
            return False