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
        
        # Login detection configuration
        self.login_detection_enabled = True
        self.login_check_interval = 30  # seconds
        self.login_detection_selectors = {
            "weibo": {
                "logged_in_selectors": [".gn_name", ".WB_miniblog", ".gn_usercard"],
                "login_selectors": [".loginBtn", ".login", ".WB_login"]
            },
            "xiaohongshu": {
                "logged_in_selectors": [
                    ".user-info", ".avatar", ".username", ".user-name",
                    "[data-testid='user-avatar']", ".user-avatar", ".profile-avatar",
                    ".header-user", ".nav-user", ".user-menu", ".user-dropdown",
                    "img[alt*='头像']", "img[alt*='avatar']", ".user-profile",
                    ".login-user", ".current-user", ".user-info-name",
                    "[class*='user']", "[class*='avatar']", "[class*='profile']"
                ],
                "login_selectors": [
                    ".login-btn", ".sign-in", ".login-button", ".signin-btn",
                    "button[type='submit']", "[data-testid='login-btn']",
                    "a[href*='login']", "button:contains('登录')", "button:contains('登陆')",
                    ".auth-btn", ".login-link", ".signin-link"
                ]
            },
            "douyin": {
                "logged_in_selectors": [".user-info", ".avatar-wrap", ".user-name"],
                "login_selectors": [".login-button", ".login-text"]
            }
        }
        
        # Start login detection task
        asyncio.create_task(self._periodic_login_detection())
    
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
        browser = None
        page = None
        instance_id = None
        
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
            
            # Generate instance ID early for cleanup purposes
            instance_id = f"browser_{uuid.uuid4().hex[:12]}"
            
            # Launch browser with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to launch browser (attempt {attempt + 1}/{max_retries})")
                    
                    # Enhanced browser launch arguments for better stability
                    launch_args = [
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding"
                    ]
                    
                    browser = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=config.get("headless", True),  # Default to headless for stability
                        viewport=config.get("viewport"),
                        user_agent=config.get("user_agent"),
                        locale=config.get("locale"),
                        timezone_id=config.get("timezone_id"),
                        args=launch_args,
                        ignore_default_args=["--enable-automation"],
                        slow_mo=100  # Add small delay between actions for stability
                    )
                    
                    logger.info(f"Browser launched successfully on attempt {attempt + 1}")
                    break
                    
                except Exception as launch_error:
                    logger.warning(f"Browser launch attempt {attempt + 1} failed: {launch_error}")
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed to launch browser after {max_retries} attempts: {launch_error}")
                    
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Create initial page with error handling
            try:
                page = await browser.new_page()
                logger.info(f"Initial page created for instance {instance_id}")
            except Exception as page_error:
                logger.error(f"Failed to create initial page: {page_error}")
                if browser:
                    await browser.close()
                raise Exception(f"Failed to create initial page: {page_error}")
            
            # Navigate to platform homepage or default page
            platform_urls = {
                "weibo": "https://weibo.com",
                "xiaohongshu": "https://www.xiaohongshu.com",
                "douyin": "https://www.douyin.com"
            }
            
            default_url = platform_urls.get(platform, "https://www.baidu.com")
            page_url = "about:blank"  # Default to blank page
            
            # Navigation with timeout and error handling
            try:
                logger.info(f"Attempting to navigate to {default_url} for platform {platform}")
                await page.goto(default_url, wait_until="domcontentloaded", timeout=15000)  # Reduced timeout
                page_url = page.url
                logger.info(f"Successfully navigated to {page_url} for platform {platform}")
            except Exception as nav_error:
                logger.warning(f"Failed to navigate to {default_url}: {nav_error}, keeping blank page")
                # Keep the blank page, don't fail the entire operation
                try:
                    await page.goto("about:blank", timeout=5000)
                    page_url = "about:blank"
                except Exception:
                    page_url = "about:blank"
            
            # Store instances
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
                "headless": config.get("headless", True),
                "user_data_dir": user_data_dir,
                "page_url": page_url,
                "created_at": instance_data["created_at"],
                "expires_at": instance_data["expires_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to create browser instance for session {session_id}: {e}")
            
            # Cleanup on failure
            try:
                if browser:
                    await browser.close()
                    logger.info(f"Cleaned up browser instance after failure")
                if instance_id and instance_id in self.browsers:
                    del self.browsers[instance_id]
                if instance_id:
                    pages_to_remove = [key for key in self.pages.keys() if key.startswith(f"{instance_id}_")]
                    for page_key in pages_to_remove:
                        del self.pages[page_key]
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
            
            raise Exception(f"Failed to create browser instance: {str(e)}")
    
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
    
    async def check_login_status(self, instance_id: str) -> dict:
        """Check login status for a browser instance with enhanced detection"""
        try:
            if instance_id not in self.browsers:
                return {"is_logged_in": False, "error": "Instance not found"}
            
            # Get instance data from database
            instance_data = await self.db.browser_instances.find_one({
                "instance_id": instance_id,
                "is_active": True
            })
            
            if not instance_data:
                return {"is_logged_in": False, "error": "Instance data not found"}
            
            platform = instance_data["platform"]
            main_page_key = f"{instance_id}_main"
            
            if main_page_key not in self.pages:
                return {"is_logged_in": False, "error": "No main page found"}
            
            page = self.pages[main_page_key]
            
            # Get platform-specific selectors
            selectors = self.login_detection_selectors.get(platform, {})
            logged_in_selectors = selectors.get("logged_in_selectors", [])
            login_selectors = selectors.get("login_selectors", [])
            
            # Enhanced login detection for xiaohongshu
            if platform == "xiaohongshu":
                return await self._check_xiaohongshu_login_status(page, logged_in_selectors, login_selectors)
            
            # Default login detection for other platforms
            return await self._check_default_login_status(page, logged_in_selectors, login_selectors, platform)
            
        except Exception as e:
            logger.error(f"Failed to check login status for instance {instance_id}: {e}")
            return {"is_logged_in": False, "error": str(e)}
    
    async def _check_xiaohongshu_login_status(self, page, logged_in_selectors: list, login_selectors: list) -> dict:
        """Enhanced login status detection specifically for xiaohongshu"""
        try:
            is_logged_in = False
            login_user = None
            detection_method = None
            
            # Method 1: Check for user avatar or profile elements
            avatar_selectors = [
                "img[alt*='头像']", "img[alt*='avatar']", ".user-avatar img", ".profile-avatar img",
                "[data-testid='user-avatar'] img", ".header-user img", ".nav-user img"
            ]
            
            for selector in avatar_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        src = await element.get_attribute('src')
                        if src and 'avatar' in src.lower() and 'default' not in src.lower():
                            is_logged_in = True
                            detection_method = f"avatar_detected:{selector}"
                            break
                except Exception:
                    continue
            
            # Method 2: Check for username or user info text
            if not is_logged_in:
                username_selectors = [
                    ".user-name", ".username", ".user-info-name", ".profile-name",
                    "[data-testid='username']", ".header-user-name", ".nav-username"
                ]
                
                for selector in username_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            if text and text.strip() and len(text.strip()) > 0:
                                is_logged_in = True
                                login_user = text.strip()
                                detection_method = f"username_detected:{selector}"
                                break
                    except Exception:
                        continue
            
            # Method 3: Check for user dropdown or menu
            if not is_logged_in:
                menu_selectors = [
                    ".user-menu", ".user-dropdown", ".profile-menu", ".header-user-menu",
                    "[data-testid='user-menu']", ".user-actions", ".account-menu"
                ]
                
                for selector in menu_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            is_logged_in = True
                            detection_method = f"menu_detected:{selector}"
                            break
                    except Exception:
                        continue
            
            # Method 4: Check URL patterns for logged-in state
            if not is_logged_in:
                current_url = page.url
                logged_in_url_patterns = ['/user/', '/profile/', '/settings/', '/account/']
                if any(pattern in current_url for pattern in logged_in_url_patterns):
                    is_logged_in = True
                    detection_method = f"url_pattern_detected:{current_url}"
            
            # Method 5: Execute JavaScript to check for login state
            if not is_logged_in:
                try:
                    js_result = await page.evaluate("""
                        () => {
                            // Check for common login indicators in xiaohongshu
                            const indicators = [
                                () => document.querySelector('.user-avatar'),
                                () => document.querySelector('[class*="user"][class*="info"]'),
                                () => document.querySelector('img[src*="avatar"]'),
                                () => document.cookie.includes('session') || document.cookie.includes('token'),
                                () => localStorage.getItem('user') || sessionStorage.getItem('user'),
                                () => window.location.href.includes('/user/') || window.location.href.includes('/profile/')
                            ];
                            
                            for (let i = 0; i < indicators.length; i++) {
                                try {
                                    if (indicators[i]()) {
                                        return { detected: true, method: `js_indicator_${i}` };
                                    }
                                } catch (e) {
                                    continue;
                                }
                            }
                            
                            return { detected: false, method: null };
                        }
                    """)
                    
                    if js_result and js_result.get('detected'):
                        is_logged_in = True
                        detection_method = f"javascript:{js_result.get('method')}"
                        
                except Exception as js_error:
                    logger.debug(f"JavaScript detection failed: {js_error}")
            
            # Fallback: Check for login buttons (indicates not logged in)
            has_login_button = False
            if not is_logged_in:
                for selector in login_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            has_login_button = True
                            break
                    except Exception:
                        continue
            
            current_url = page.url
            
            result = {
                "is_logged_in": is_logged_in,
                "login_user": login_user,
                "has_login_button": has_login_button,
                "current_url": current_url,
                "platform": "xiaohongshu",
                "detection_method": detection_method,
                "timestamp": datetime.utcnow()
            }
            
            logger.info(f"Xiaohongshu login status check: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to check xiaohongshu login status: {e}")
            return {"is_logged_in": False, "error": str(e), "platform": "xiaohongshu"}
    
    async def _check_default_login_status(self, page, logged_in_selectors: list, login_selectors: list, platform: str) -> dict:
        """Default login status detection for other platforms"""
        try:
            # Check for logged-in indicators
            is_logged_in = False
            login_user = None
            
            for selector in logged_in_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_logged_in = True
                        # Try to extract username if possible
                        if selector in [".gn_name", ".username", ".user-name"]:
                            login_user = await element.text_content()
                        break
                except Exception:
                    continue
            
            # If not logged in, check for login buttons
            has_login_button = False
            if not is_logged_in:
                for selector in login_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            has_login_button = True
                            break
                    except Exception:
                        continue
            
            # Get current URL for context
            current_url = page.url
            
            return {
                "is_logged_in": is_logged_in,
                "login_user": login_user,
                "has_login_button": has_login_button,
                "current_url": current_url,
                "platform": platform,
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Failed default login status check for {platform}: {e}")
            return {"is_logged_in": False, "error": str(e), "platform": platform}
    
    async def _periodic_login_detection(self):
        """Periodic login status detection for all active instances"""
        while True:
            try:
                if not self.login_detection_enabled:
                    await asyncio.sleep(self.login_check_interval)
                    continue
                
                # Check login status for all active instances
                for instance_id in list(self.browsers.keys()):
                    try:
                        login_status = await self.check_login_status(instance_id)
                        
                        if "error" not in login_status:
                            # Update session login status if changed
                            instance_data = await self.db.browser_instances.find_one({
                                "instance_id": instance_id,
                                "is_active": True
                            })
                            
                            if instance_data:
                                session_id = instance_data["session_id"]
                                
                                # Update session manager with login status
                                from .session_manager import SessionManager
                                # Note: This would need proper dependency injection in production
                                # For now, we'll update the database directly
                                
                                # Check if login status changed
                                current_session = await self.db.sessions.find_one({"session_id": session_id})
                                previous_login_status = current_session.get("is_logged_in", False) if current_session else False
                                
                                await self.db.sessions.update_one(
                                    {"session_id": session_id},
                                    {
                                        "$set": {
                                            "is_logged_in": login_status["is_logged_in"],
                                            "login_user": login_status.get("login_user"),
                                            "last_activity": datetime.utcnow(),
                                            "login_detection_timestamp": login_status["timestamp"]
                                        }
                                    }
                                )
                                
                                # Send notification if login status changed
                                if login_status["is_logged_in"] != previous_login_status:
                                    await self._send_login_status_notification(
                                        session_id, 
                                        login_status["is_logged_in"], 
                                        login_status.get("login_user"),
                                        login_status["platform"]
                                    )
                                
                                logger.debug(f"Updated login status for session {session_id}: {login_status['is_logged_in']}")
                    
                    except Exception as e:
                        logger.error(f"Error checking login status for instance {instance_id}: {e}")
                
                await asyncio.sleep(self.login_check_interval)
                
            except Exception as e:
                logger.error(f"Error in periodic login detection: {e}")
                await asyncio.sleep(self.login_check_interval)
    
    async def _send_login_status_notification(self, session_id: str, is_logged_in: bool, login_user: str = None, platform: str = None):
        """Send notification when login status changes"""
        try:
            # Create notification record in database
            notification = {
                "session_id": session_id,
                "type": "login_status_change",
                "is_logged_in": is_logged_in,
                "login_user": login_user,
                "platform": platform,
                "timestamp": datetime.utcnow(),
                "message": f"登录状态变更: {'已登录' if is_logged_in else '已退出'}" + (f" (用户: {login_user})" if login_user else "")
            }
            
            # Store notification in database
            await self.db.notifications.insert_one(notification)
            
            # Log the notification
            logger.info(f"Login status notification sent for session {session_id}: {'logged in' if is_logged_in else 'logged out'}")
            
        except Exception as e:
            logger.error(f"Failed to send login status notification for session {session_id}: {e}")
    
    async def shutdown(self):
        """Shutdown browser manager and close all instances"""
        try:
            # Disable login detection
            self.login_detection_enabled = False
            
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