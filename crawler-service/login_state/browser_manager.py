# Browser Instance Manager for Login State Management
# Manages Playwright browser instances with session persistence

import asyncio
import uuid
import json
import os
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import aiofiles
import psutil
import logging

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

class BrowserInstanceManager:
    """Browser instance management service with Playwright"""
    
    def __init__(self, db: AsyncIOMotorDatabase, data_dir: str = "./browser_data"):
        self.db = db
        self.data_dir = data_dir
        self.playwright = None
        self.browsers: Dict[str, Browser] = {}
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        
        # Browser configuration
        self.browser_configs = {
            "weibo": {
                "headless": False,
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai"
            },
            "xiaohongshu": {
                "headless": False,
                "viewport": {"width": 1366, "height": 768},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai"
            },
            "douyin": {
                "headless": False,
                "viewport": {"width": 1440, "height": 900},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai"
            }
        }
        
        # Instance limits
        self.max_instances_per_platform = 5
        self.max_total_instances = 20
        self.instance_timeout = timedelta(hours=2)
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def initialize(self):
        """Initialize Playwright"""
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
                logger.info("Playwright initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def create_browser_instance(self, session_id: str, platform: str, 
                                    headless: bool = None, custom_config: dict = None) -> dict:
        """Create a new browser instance for a session"""
        try:
            await self.initialize()
            
            # Check instance limits
            if len(self.browsers) >= self.max_total_instances:
                await self._cleanup_oldest_instances()
            
            platform_instances = await self._get_platform_instance_count(platform)
            if platform_instances >= self.max_instances_per_platform:
                await self._cleanup_platform_instances(platform)
            
            # Get browser configuration
            config = self.browser_configs.get(platform, self.browser_configs["weibo"]).copy()
            if custom_config:
                config.update(custom_config)
            
            if headless is not None:
                config["headless"] = headless
            
            # Create user data directory for session
            user_data_dir = os.path.join(self.data_dir, f"session_{session_id}")
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Launch browser
            browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=config.get("headless", False),
                viewport=config.get("viewport"),
                user_agent=config.get("user_agent"),
                locale=config.get("locale"),
                timezone_id=config.get("timezone_id"),
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor"
                ]
            )
            
            # Create initial page
            page = await browser.new_page()
            
            # Navigate to platform homepage or default page
            platform_urls = {
                "weibo": "https://weibo.com",
                "xiaohongshu": "https://www.xiaohongshu.com",
                "douyin": "https://www.douyin.com"
            }
            
            default_url = platform_urls.get(platform, "https://www.baidu.com")
            page_url = "about:blank"  # Default to blank page
            try:
                logger.info(f"Attempting to navigate to {default_url} for platform {platform}")
                await page.goto(default_url, wait_until="networkidle", timeout=30000)
                page_url = page.url
                logger.info(f"Successfully navigated to {page_url} for platform {platform}")
            except Exception as nav_error:
                logger.warning(f"Failed to navigate to {default_url}: {nav_error}, using blank page")
                # Keep the blank page, don't fail the entire operation
                page_url = "about:blank"
            
            # Store instances
            instance_id = f"browser_{uuid.uuid4().hex[:12]}"
            self.browsers[instance_id] = browser
            self.pages[f"{instance_id}_main"] = page
            
            # Save instance info to database
            instance_data = {
                "instance_id": instance_id,
                "session_id": session_id,
                "platform": platform,
                "user_data_dir": user_data_dir,
                "config": config,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "expires_at": datetime.utcnow() + self.instance_timeout,
                "page_count": 1,
                "memory_usage": await self._get_memory_usage()
            }
            
            await self.db.browser_instances.insert_one(instance_data)
            
            logger.info(f"Created browser instance {instance_id} for session {session_id} on platform {platform}")
            
            return {
                "instance_id": instance_id,
                "session_id": session_id,
                "platform": platform,
                "headless": config.get("headless", False),
                "user_data_dir": user_data_dir,
                "page_url": page_url,
                "created_at": instance_data["created_at"],
                "expires_at": instance_data["expires_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to create browser instance for session {session_id}: {e}")
            raise
    
    async def get_browser_instance(self, instance_id: str) -> Optional[dict]:
        """Get browser instance information"""
        try:
            # Check if instance exists in memory
            if instance_id not in self.browsers:
                return None
            
            # Get instance data from database
            instance_data = await self.db.browser_instances.find_one({
                "instance_id": instance_id,
                "is_active": True
            })
            
            if not instance_data:
                # Clean up orphaned instance
                await self._cleanup_instance(instance_id)
                return None
            
            # Convert ObjectId to string for JSON serialization
            instance_data = convert_objectid_to_str(instance_data)
            
            # Check if instance is expired
            if instance_data["expires_at"] < datetime.utcnow():
                await self.close_browser_instance(instance_id)
                return None
            
            # Update last activity
            await self._update_instance_activity(instance_id)
            
            browser = self.browsers[instance_id]
            main_page_key = f"{instance_id}_main"
            page = self.pages.get(main_page_key)
            
            return {
                "instance_id": instance_id,
                "session_id": instance_data["session_id"],
                "platform": instance_data["platform"],
                "is_active": True,
                "page_count": len(browser.contexts[0].pages) if browser.contexts else 0,
                "current_url": page.url if page else None,
                "created_at": instance_data["created_at"],
                "last_activity": instance_data["last_activity"],
                "expires_at": instance_data["expires_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get browser instance {instance_id}: {e}")
            return None
    
    async def navigate_to_url(self, instance_id: str, url: str, wait_for: str = "networkidle") -> dict:
        """Navigate browser instance to a URL"""
        try:
            if instance_id not in self.browsers:
                raise ValueError(f"Browser instance {instance_id} not found")
            
            browser = self.browsers[instance_id]
            main_page_key = f"{instance_id}_main"
            
            if main_page_key not in self.pages:
                # Create new page if main page doesn't exist
                page = await browser.contexts[0].new_page()
                self.pages[main_page_key] = page
            else:
                page = self.pages[main_page_key]
            
            # Navigate to URL
            response = await page.goto(url, wait_until=wait_for, timeout=30000)
            
            # Update instance activity
            await self._update_instance_activity(instance_id)
            
            # Get page info
            page_info = {
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None,
                "timestamp": datetime.utcnow()
            }
            
            logger.info(f"Navigated browser instance {instance_id} to {url}")
            return page_info
            
        except Exception as e:
            logger.error(f"Failed to navigate browser instance {instance_id} to {url}: {e}")
            raise
    
    async def execute_script(self, instance_id: str, script: str) -> Any:
        """Execute JavaScript in browser instance"""
        try:
            if instance_id not in self.browsers:
                raise ValueError(f"Browser instance {instance_id} not found")
            
            main_page_key = f"{instance_id}_main"
            if main_page_key not in self.pages:
                raise ValueError(f"No main page found for instance {instance_id}")
            
            page = self.pages[main_page_key]
            result = await page.evaluate(script)
            
            # Update instance activity
            await self._update_instance_activity(instance_id)
            
            logger.info(f"Executed script in browser instance {instance_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute script in browser instance {instance_id}: {e}")
            raise
    
    async def take_screenshot(self, instance_id: str, full_page: bool = False) -> str:
        """Take screenshot of browser instance"""
        try:
            if instance_id not in self.browsers:
                raise ValueError(f"Browser instance {instance_id} not found")
            
            main_page_key = f"{instance_id}_main"
            if main_page_key not in self.pages:
                raise ValueError(f"No main page found for instance {instance_id}")
            
            page = self.pages[main_page_key]
            
            # Create screenshots directory
            screenshot_dir = os.path.join(self.data_dir, "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Generate screenshot filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(screenshot_dir, f"{instance_id}_{timestamp}.png")
            
            # Take screenshot
            await page.screenshot(path=screenshot_path, full_page=full_page)
            
            # Update instance activity
            await self._update_instance_activity(instance_id)
            
            logger.info(f"Screenshot taken for browser instance {instance_id}: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Failed to take screenshot for browser instance {instance_id}: {e}")
            raise
    
    async def get_cookies(self, instance_id: str) -> List[dict]:
        """Get cookies from browser instance"""
        try:
            if instance_id not in self.browsers:
                raise ValueError(f"Browser instance {instance_id} not found")
            
            browser = self.browsers[instance_id]
            context = browser.contexts[0] if browser.contexts else None
            
            if not context:
                return []
            
            cookies = await context.cookies()
            
            # Update instance activity
            await self._update_instance_activity(instance_id)
            
            return cookies
            
        except Exception as e:
            logger.error(f"Failed to get cookies from browser instance {instance_id}: {e}")
            return []
    
    async def set_cookies(self, instance_id: str, cookies: List[dict]) -> bool:
        """Set cookies in browser instance"""
        try:
            if instance_id not in self.browsers:
                raise ValueError(f"Browser instance {instance_id} not found")
            
            browser = self.browsers[instance_id]
            context = browser.contexts[0] if browser.contexts else None
            
            if not context:
                return False
            
            await context.add_cookies(cookies)
            
            # Update instance activity
            await self._update_instance_activity(instance_id)
            
            logger.info(f"Set {len(cookies)} cookies in browser instance {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cookies in browser instance {instance_id}: {e}")
            return False
    
    async def close_browser_instance(self, instance_id: str) -> bool:
        """Close a browser instance"""
        try:
            # Close browser if exists
            if instance_id in self.browsers:
                browser = self.browsers[instance_id]
                await browser.close()
                del self.browsers[instance_id]
            
            # Remove pages
            pages_to_remove = [key for key in self.pages.keys() if key.startswith(f"{instance_id}_")]
            for page_key in pages_to_remove:
                del self.pages[page_key]
            
            # Update database
            await self.db.browser_instances.update_one(
                {"instance_id": instance_id},
                {"$set": {"is_active": False, "closed_at": datetime.utcnow()}}
            )
            
            logger.info(f"Closed browser instance {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close browser instance {instance_id}: {e}")
            return False
    
    async def get_session_instances(self, session_id: str) -> List[dict]:
        """Get all browser instances for a session"""
        try:
            cursor = self.db.browser_instances.find({
                "session_id": session_id,
                "is_active": True
            })
            
            instances = await cursor.to_list(length=None)
            
            # Filter out expired instances and convert ObjectId
            valid_instances = []
            for instance in instances:
                # Convert ObjectId to string for JSON serialization
                instance = convert_objectid_to_str(instance)
                if instance["expires_at"] > datetime.utcnow():
                    valid_instances.append(instance)
                else:
                    # Clean up expired instance
                    await self.close_browser_instance(instance["instance_id"])
            
            return valid_instances
            
        except Exception as e:
            logger.error(f"Failed to get session instances for {session_id}: {e}")
            return []
    
    async def extend_instance_timeout(self, instance_id: str, hours: int = 2) -> bool:
        """Extend browser instance timeout"""
        try:
            new_expires_at = datetime.utcnow() + timedelta(hours=hours)
            
            result = await self.db.browser_instances.update_one(
                {"instance_id": instance_id},
                {"$set": {"expires_at": new_expires_at}}
            )
            
            logger.info(f"Extended browser instance {instance_id} timeout until {new_expires_at}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to extend browser instance {instance_id} timeout: {e}")
            return False
    
    async def cleanup_expired_instances(self) -> int:
        """Clean up expired browser instances"""
        try:
            current_time = datetime.utcnow()
            
            # Find expired instances
            cursor = self.db.browser_instances.find({
                "is_active": True,
                "expires_at": {"$lt": current_time}
            })
            
            expired_instances = await cursor.to_list(length=None)
            
            # Close expired instances
            closed_count = 0
            for instance in expired_instances:
                if await self.close_browser_instance(instance["instance_id"]):
                    closed_count += 1
            
            logger.info(f"Cleaned up {closed_count} expired browser instances")
            return closed_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired browser instances: {e}")
            return 0
    
    async def _cleanup_instance(self, instance_id: str):
        """Clean up orphaned instance"""
        try:
            if instance_id in self.browsers:
                await self.browsers[instance_id].close()
                del self.browsers[instance_id]
            
            # Remove pages
            pages_to_remove = [key for key in self.pages.keys() if key.startswith(f"{instance_id}_")]
            for page_key in pages_to_remove:
                del self.pages[page_key]
                
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned instance {instance_id}: {e}")
    
    async def _update_instance_activity(self, instance_id: str):
        """Update instance last activity timestamp"""
        try:
            await self.db.browser_instances.update_one(
                {"instance_id": instance_id},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Failed to update instance activity for {instance_id}: {e}")
    
    async def _get_platform_instance_count(self, platform: str) -> int:
        """Get number of active instances for a platform"""
        try:
            count = await self.db.browser_instances.count_documents({
                "platform": platform,
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            return count
        except Exception as e:
            logger.error(f"Failed to get platform instance count for {platform}: {e}")
            return 0
    
    async def _cleanup_oldest_instances(self, count: int = 1):
        """Clean up oldest instances to make room for new ones"""
        try:
            cursor = self.db.browser_instances.find({
                "is_active": True
            }).sort("last_activity", 1).limit(count)
            
            oldest_instances = await cursor.to_list(length=None)
            
            for instance in oldest_instances:
                await self.close_browser_instance(instance["instance_id"])
                
        except Exception as e:
            logger.error(f"Failed to cleanup oldest instances: {e}")
    
    async def _cleanup_platform_instances(self, platform: str, count: int = 1):
        """Clean up oldest instances for a specific platform"""
        try:
            cursor = self.db.browser_instances.find({
                "platform": platform,
                "is_active": True
            }).sort("last_activity", 1).limit(count)
            
            oldest_instances = await cursor.to_list(length=None)
            
            for instance in oldest_instances:
                await self.close_browser_instance(instance["instance_id"])
                
        except Exception as e:
            logger.error(f"Failed to cleanup platform instances for {platform}: {e}")
    
    async def _get_memory_usage(self) -> dict:
        """Get current memory usage"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {}
    
    async def _periodic_cleanup(self):
        """Periodic cleanup task for expired instances"""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                await self.cleanup_expired_instances()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def get_instance_stats(self) -> Dict:
        """Get browser instance statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$platform",
                        "total_instances": {"$sum": 1},
                        "active_instances": {
                            "$sum": {
                                "$cond": [
                                    {"$and": [
                                        {"$eq": ["$is_active", True]},
                                        {"$gt": ["$expires_at", datetime.utcnow()]}
                                    ]},
                                    1,
                                    0
                                ]
                            }
                        }
                    }
                }
            ]
            
            cursor = self.db.browser_instances.aggregate(pipeline)
            platform_stats = await cursor.to_list(length=None)
            
            # Get total counts
            total_instances = await self.db.browser_instances.count_documents({})
            active_instances = await self.db.browser_instances.count_documents({
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return {
                "total_instances": total_instances,
                "active_instances": active_instances,
                "memory_cached_instances": len(self.browsers),
                "platform_stats": {stat["_id"]: {
                    "total": stat["total_instances"],
                    "active": stat["active_instances"]
                } for stat in platform_stats}
            }
            
        except Exception as e:
            logger.error(f"Failed to get instance stats: {e}")
            return {}
    
    async def shutdown(self):
        """Shutdown browser manager and close all instances"""
        try:
            # Close all browser instances
            for instance_id in list(self.browsers.keys()):
                await self.close_browser_instance(instance_id)
            
            # Stop Playwright
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            
            logger.info("Browser manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during browser manager shutdown: {e}")