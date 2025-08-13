# Manual Crawl Service for Login State Management
# Provides manual crawling functionality for logged-in websites

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, urljoin
import json
import re

from playwright.async_api import Page, Browser, BrowserContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel, HttpUrl

from .models import (
    ManualCrawlRequest,
    CrawlResult,
    CrawlTaskStatus,
    PlatformType,
    CrawlTaskDocument
)
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
    selectors: Dict[str, str]  # CSS selectors for content extraction
    wait_selectors: List[str]  # Selectors to wait for before crawling
    scroll_config: Optional[Dict[str, Any]] = None  # Scroll configuration
    custom_scripts: List[str] = []  # Custom JavaScript to execute
    timeout_ms: int = 30000  # Page load timeout
    
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
        
        # Platform-specific crawl configurations
        self.platform_configs = {
            PlatformType.WEIBO: CrawlConfig(
                platform=PlatformType.WEIBO,
                selectors={
                    "title": ".WB_detail .WB_text",
                    "content": ".WB_detail .WB_text",
                    "author": ".WB_info .W_f14 .W_fb",
                    "publish_time": ".WB_from .S_txt2",
                    "images": ".WB_media_wrap img",
                    "video": ".WB_media_wrap video",
                    "comments": ".list_con .WB_text",
                    "likes": ".WB_row_line .W_btn_c .W_btn_txt",
                    "reposts": ".WB_row_line .W_btn_b .W_btn_txt"
                },
                wait_selectors=[".WB_detail", ".WB_text"],
                scroll_config={"enabled": True, "max_scrolls": 3, "delay_ms": 1000},
                timeout_ms=15000
            ),
            PlatformType.XIAOHONGSHU: CrawlConfig(
                platform=PlatformType.XIAOHONGSHU,
                selectors={
                    "title": ".note-detail-mask .title",
                    "content": ".note-detail-mask .desc",
                    "author": ".note-detail-mask .author-wrapper .name",
                    "publish_time": ".note-detail-mask .date",
                    "images": ".note-detail-mask .carousel img",
                    "video": ".note-detail-mask video",
                    "tags": ".note-detail-mask .tag",
                    "likes": ".note-detail-mask .like-count",
                    "comments": ".note-detail-mask .comment-count"
                },
                wait_selectors=[".note-detail-mask", ".title"],
                scroll_config={"enabled": True, "max_scrolls": 2, "delay_ms": 1500},
                timeout_ms=20000
            ),
            PlatformType.DOUYIN: CrawlConfig(
                platform=PlatformType.DOUYIN,
                selectors={
                    "title": ".video-info-detail .video-info-title",
                    "content": ".video-info-detail .video-info-desc",
                    "author": ".video-info-detail .author-name",
                    "publish_time": ".video-info-detail .video-publish-time",
                    "video": ".xgplayer-video",
                    "cover": ".xgplayer-poster",
                    "likes": ".video-actions .like-count",
                    "comments": ".video-actions .comment-count",
                    "shares": ".video-actions .share-count"
                },
                wait_selectors=[".video-info-detail", ".video-info-title"],
                scroll_config={"enabled": False},
                timeout_ms=25000
            )
        }
    
    async def create_crawl_task(
        self,
        request: ManualCrawlRequest,
        user_id: str
    ) -> str:
        """Create a new crawl task"""
        try:
            # Validate session
            session = await self.session_manager.get_session(request.session_id)
            if not session or session.user_id != user_id:
                raise ValueError("Invalid session")
            
            # Create task document
            task_doc = CrawlTaskDocument(
                task_id=f"crawl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}",
                session_id=request.session_id,
                user_id=user_id,
                platform=request.platform,
                url=str(request.url),
                status=CrawlTaskStatus.PENDING,
                config=request.config or {},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
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
            
            # Get browser instance
            browser_instance = await self.browser_manager.get_instance(
                task_doc["session_id"]
            )
            if not browser_instance:
                raise ValueError("No browser instance available")
            
            # Execute crawl
            result = await self._crawl_page(
                browser_instance["page"],
                task_doc["url"],
                PlatformType(task_doc["platform"]),
                task_doc.get("config", {})
            )
            
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
        custom_config: Dict[str, Any]
    ) -> CrawlResult:
        """Crawl a single page"""
        try:
            # Get platform config
            config = self.platform_configs.get(platform)
            if not config:
                raise ValueError(f"Unsupported platform: {platform}")
            
            # Merge custom config
            if custom_config:
                config = config.copy()
                if "selectors" in custom_config:
                    config.selectors.update(custom_config["selectors"])
                if "timeout_ms" in custom_config:
                    config.timeout_ms = custom_config["timeout_ms"]
            
            # Navigate to page
            await page.goto(url, timeout=config.timeout_ms)
            
            # Wait for key selectors
            for selector in config.wait_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                except Exception:
                    logger.warning(f"Selector {selector} not found, continuing...")
            
            # Execute custom scripts
            for script in config.custom_scripts:
                try:
                    await page.evaluate(script)
                except Exception as e:
                    logger.warning(f"Custom script failed: {e}")
            
            # Handle scrolling
            if config.scroll_config and config.scroll_config.get("enabled"):
                await self._handle_scrolling(page, config.scroll_config)
            
            # Extract content
            content = await self._extract_content(page, config.selectors)
            
            # Extract metadata
            metadata = await self._extract_metadata(page, url)
            
            return CrawlResult(
                task_id="",  # Will be set by caller
                url=url,
                platform=platform,
                content=content,
                metadata=metadata,
                crawled_at=datetime.now(timezone.utc),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to crawl page {url}: {e}")
            return CrawlResult(
                task_id="",
                url=url,
                platform=platform,
                content={},
                metadata={"error": str(e)},
                crawled_at=datetime.now(timezone.utc),
                success=False
            )
    
    async def _handle_scrolling(self, page: Page, scroll_config: Dict[str, Any]):
        """Handle page scrolling"""
        max_scrolls = scroll_config.get("max_scrolls", 3)
        delay_ms = scroll_config.get("delay_ms", 1000)
        
        for i in range(max_scrolls):
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(delay_ms / 1000)
            
            # Check if more content loaded
            current_height = await page.evaluate("document.body.scrollHeight")
            await asyncio.sleep(0.5)
            new_height = await page.evaluate("document.body.scrollHeight")
            
            if current_height == new_height:
                break  # No more content to load
    
    async def _extract_content(self, page: Page, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Extract content using CSS selectors"""
        content = {}
        
        for field, selector in selectors.items():
            try:
                if field in ["images", "comments", "tags"]:
                    # Extract multiple elements
                    elements = await page.query_selector_all(selector)
                    values = []
                    for element in elements:
                        if field == "images":
                            src = await element.get_attribute("src")
                            if src:
                                values.append(src)
                        else:
                            text = await element.text_content()
                            if text and text.strip():
                                values.append(text.strip())
                    content[field] = values
                else:
                    # Extract single element
                    element = await page.query_selector(selector)
                    if element:
                        if field in ["video", "cover"]:
                            src = await element.get_attribute("src")
                            content[field] = src
                        else:
                            text = await element.text_content()
                            content[field] = text.strip() if text else ""
                    else:
                        content[field] = "" if field not in ["images", "comments", "tags"] else []
                        
            except Exception as e:
                logger.warning(f"Failed to extract {field} with selector {selector}: {e}")
                content[field] = "" if field not in ["images", "comments", "tags"] else []
        
        return content
    
    async def _extract_metadata(self, page: Page, url: str) -> Dict[str, Any]:
        """Extract page metadata"""
        metadata = {
            "url": url,
            "domain": urlparse(url).netloc,
            "extracted_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Page title
            title = await page.title()
            metadata["page_title"] = title
            
            # Meta tags
            meta_description = await page.get_attribute('meta[name="description"]', "content")
            if meta_description:
                metadata["meta_description"] = meta_description
            
            meta_keywords = await page.get_attribute('meta[name="keywords"]', "content")
            if meta_keywords:
                metadata["meta_keywords"] = meta_keywords
            
            # Open Graph tags
            og_title = await page.get_attribute('meta[property="og:title"]', "content")
            if og_title:
                metadata["og_title"] = og_title
            
            og_description = await page.get_attribute('meta[property="og:description"]', "content")
            if og_description:
                metadata["og_description"] = og_description
            
            og_image = await page.get_attribute('meta[property="og:image"]', "content")
            if og_image:
                metadata["og_image"] = og_image
            
            # Page stats
            metadata["page_load_time"] = await page.evaluate(
                "performance.timing.loadEventEnd - performance.timing.navigationStart"
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
        
        return metadata
    
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