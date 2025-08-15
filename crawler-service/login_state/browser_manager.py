# Browser Instance Manager for Login State Management
# Manages Playwright browser instances with session persistence

import asyncio
import uuid
import json
import os
import re
import time
import shutil
import sys
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import aiofiles
import psutil
import logging

# 添加父目录到路径以导入日志配置
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from logging_config import get_logger, LoggerMixin, log_async_function_call

# Worker管理器将通过依赖注入设置，避免循环导入

logger = get_logger('login_state.browser_manager')

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

class BrowserInstanceManager(LoggerMixin):
    """Browser instance management service with Playwright"""
    
    def __init__(self, db: AsyncIOMotorDatabase, session_manager=None, cookie_store=None, data_dir: str = "./browser_data"):
        self.db = db
        self.session_manager = session_manager
        self.cookie_store = cookie_store
        self.data_dir = data_dir
        self.playwright = None
        self.browsers: Dict[str, BrowserContext] = {}
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        
        # Enhanced tab management
        self.page_listeners: Dict[str, Dict] = {}  # instance_id -> {page_id: listeners}
        self.tab_states: Dict[str, Dict] = {}  # instance_id -> {page_id: state}
        self.session_storage: Dict[str, Dict] = {}  # instance_id -> session data
        self.cross_tab_sync_enabled = True
        
        # Navigation crawling management
        self.crawled_urls = {}  # Track crawled URLs with timestamp and status: {url: {"success": bool, "timestamp": float, "task_id": str}}
        
        # Synchronization locks to prevent race conditions
        self._creation_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self._instance_locks = {}  # instance_id -> lock
        
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
        
        # Platform configuration including login detection
        self.login_detection_enabled = True
        self.login_check_interval = 30  # seconds
        self.platform_configs = {
            "weibo": {
                "logged_in_selectors": [".gn_name", ".WB_miniblog", ".gn_usercard"],
                "login_selectors": [".loginBtn", ".login", ".WB_login"]
            },
            "xiaohongshu": {
                "logged_in_selectors": [
                    # 小红书2024年最新登录状态选择器 - 按检测准确性排序
                    ".user-info", ".user-card", ".profile-info",  # 高优先级：用户信息区域
                    ".avatar", "[class*='avatar']", ".user-avatar",  # 高优先级：头像相关
                    ".username", ".user-name", "[class*='username']", ".nickname",  # 高优先级：用户名相关
                    ".reds-icon-user", ".icon-user", "[class*='icon-user']",  # 小红书特定图标
                    ".header-user", ".nav-user", ".navbar-user",  # 导航栏用户区域
                    ".user-menu", ".user-dropdown", ".profile-dropdown", ".account-dropdown",  # 用户菜单
                    ".login-user", ".current-user", ".logged-user",  # 当前用户状态
                    "[data-testid='user-avatar']", "[data-testid='user-info']", "[data-testid='profile']",  # 测试ID
                    "[class*='user'][class*='info']", "[class*='user'][class*='card']",  # 组合类名
                    "[class*='profile']", "[aria-label*='用户']", "[aria-label*='个人']",  # 通用模式
                    ".account-info", ".member-info", ".profile-section",  # 账户信息
                    "button[class*='user']", "div[class*='user-panel']", ".user-container",  # 用户面板
                    ".user-status", ".login-status[data-logged='true']", "[data-login='true']",  # 状态指示器
                    "[data-user-id]", "[data-user-name]", "[data-uid]",  # 数据属性
                    ".personal-center", ".my-profile", ".profile-page",  # 个人中心
                    ".user-badge", ".vip-badge", ".level-badge",  # 用户徽章（登录用户特有）
                    ".message-center", ".notification-center",  # 消息中心（登录用户可见）
                    ".follow-btn", ".following-btn", "[class*='follow']",  # 关注按钮（登录后可见）
                    ".publish-btn", ".create-btn", "[class*='publish']",  # 发布按钮（登录后可见）
                    ".sidebar-user", ".left-nav-user", ".right-nav-user",  # 侧边栏用户信息
                    "[role='button'][aria-label*='用户']", "[role='button'][aria-label*='头像']",  # 无障碍属性
                    ".user-settings", ".account-settings", ".profile-settings"  # 设置相关（登录后可见）
                ],
                "login_selectors": [
                    # 小红书2024年最新登录按钮选择器 - 按检测准确性排序
                    ".login-btn", ".login-button", ".signin-btn", ".sign-btn",  # 标准登录按钮
                    ".sign-in", ".signin", ".log-in", ".login",  # 登录文本
                    "[data-testid='login-button']", "[data-testid='signin']", "[data-testid='login']",  # 测试ID
                    ".auth-btn", ".auth-button", ".authentication-btn",  # 认证按钮
                    ".login-link", "a[href*='login']", "a[href*='signin']",  # 登录链接
                    "button[type='submit']", ".submit-btn", ".form-submit",  # 提交按钮
                    ".login-form button", "form[class*='login'] button", ".auth-form button",  # 表单按钮
                    "[class*='login'][class*='btn']", "[class*='login'][class*='button']",  # 组合类名
                    "[class*='signin'][class*='btn']", "[class*='signin'][class*='button']",
                    "[class*='auth'][class*='btn']", "[class*='auth'][class*='button']",
                    "button[class*='primary']", "button[class*='main']",  # 主要按钮（可能是登录）
                    ".register-btn", ".signup-btn", ".register-button",  # 注册按钮（表示未登录）
                    "[aria-label*='登录']", "[aria-label*='sign']", "[aria-label*='Sign']",  # 无障碍标签
                    ".guest-login", ".visitor-login", ".anonymous-login",  # 访客登录
                    ".phone-login", ".mobile-login", ".sms-login",  # 手机登录
                    ".wechat-login", ".weixin-login", ".qq-login",  # 第三方登录
                    ".login-modal button", ".login-popup button", ".auth-modal button",  # 模态框登录
                    "[role='button'][aria-label*='登录']", "[role='button'][aria-label*='sign']",  # 无障碍按钮
                    ".login-entrance", ".signin-entrance", ".auth-entrance",  # 登录入口
                    ".header-login", ".nav-login", ".toolbar-login"  # 导航栏登录
                ]
            },
            "douyin": {
                "logged_in_selectors": [".user-info", ".avatar-wrap", ".user-name"],
                "login_selectors": [".login-button", ".login-text"]
            }
        }
        
        # Keep backward compatibility
        self.login_detection_selectors = self.platform_configs
        
        # Start login detection task
        asyncio.create_task(self._periodic_login_detection())
        
        # Start tab synchronization task
        asyncio.create_task(self._periodic_tab_sync())
        
        # Start browser session management task
        asyncio.create_task(self._manage_browser_sessions())
        
        # Start crawled URLs cleanup task
        asyncio.create_task(self._periodic_crawled_urls_cleanup())
        
        # Initialize continuous crawl service
        from .manual_crawl import ContinuousCrawlService, ContinuousTaskStatus
        self.continuous_crawl_service = ContinuousCrawlService(
            db=self.db,
            session_manager=self.session_manager,
            browser_manager=self,
            cookie_store=self.cookie_store
        )
        
        # Store ContinuousTaskStatus for use in other methods
        self.ContinuousTaskStatus = ContinuousTaskStatus
        
        # Worker manager reference for idle detection
        self.worker_manager = None  # Will be set by external service
        
    def set_worker_manager(self, worker_manager):
        """设置WorkerManager引用
        
        Args:
            worker_manager: WorkerManager实例
        """
        self.worker_manager = worker_manager
        logger.info("WorkerManager reference set for BrowserInstanceManager")
        
    def get_worker_manager(self):
        """获取WorkerManager引用
        
        Returns:
            WorkerManager实例或None
        """
        return self.worker_manager
    
    async def initialize(self):
        """Initialize Playwright"""
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
                logger.info("Playwright initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    @log_async_function_call
    async def create_browser_instance(self, session_id: str, platform: str, 
                                    headless: bool = None, custom_config: dict = None) -> dict:
        """Create a new browser instance for a session"""
        async with self._creation_lock:
            try:
                logger.info(f"Starting browser instance creation for session {session_id}, platform {platform}")
                
                # Check system resources before attempting to create browser
                try:
                    memory_info = psutil.virtual_memory()
                    disk_info = psutil.disk_usage('.')
                    logger.info(f"System resources - Memory: {memory_info.percent}% used, Disk: {disk_info.percent}% used")
                    
                    if memory_info.percent > 90:
                        logger.warning(f"High memory usage detected: {memory_info.percent}%")
                    if disk_info.percent > 95:
                        logger.warning(f"Low disk space detected: {disk_info.free / (1024**3):.1f}GB free")
                        
                except Exception as resource_error:
                    logger.warning(f"Failed to check system resources: {resource_error}")
                
                await self.initialize()
                logger.info(f"Browser manager initialized successfully")
                
                # Check instance limits with proper locking
                current_instances = len(self.browsers)
                logger.info(f"Current browser instances: {current_instances}/{self.max_total_instances}")
                
                if current_instances >= self.max_total_instances:
                    logger.info(f"Maximum instances reached, cleaning up oldest instances")
                    async with self._cleanup_lock:
                        await self._cleanup_oldest_instances()
                
                platform_instances = await self._get_platform_instance_count(platform)
                logger.info(f"Platform {platform} instances: {platform_instances}/{self.max_instances_per_platform}")
                
                if platform_instances >= self.max_instances_per_platform:
                    logger.info(f"Maximum platform instances reached, cleaning up oldest {platform} instances")
                    async with self._cleanup_lock:
                        await self._cleanup_platform_instances(platform)
                
                # Get browser configuration
                config = self.browser_configs.get(platform, self.browser_configs["weibo"]).copy()
                if custom_config:
                    config.update(custom_config)
                
                if headless is not None:
                    config["headless"] = headless
                
                # Create unique user data directory with timestamp to avoid conflicts
                import time
                timestamp = int(time.time() * 1000)  # milliseconds
                user_data_dir = os.path.join(self.data_dir, f"session_{session_id}_{timestamp}")
                
                # Ensure clean directory creation
                try:
                    if os.path.exists(user_data_dir):
                        import shutil
                        shutil.rmtree(user_data_dir, ignore_errors=True)
                        logger.info(f"Removed existing user data directory: {user_data_dir}")
                    
                    os.makedirs(user_data_dir, exist_ok=True)
                    logger.info(f"Created user data directory: {user_data_dir}")
                except Exception as dir_error:
                    logger.error(f"Failed to create user data directory {user_data_dir}: {dir_error}")
                    raise Exception(f"Failed to create user data directory: {dir_error}")
                
                # Launch browser with persistent context with retry logic
                max_retries = 3
                browser = None
                
                for attempt in range(max_retries):
                    try:
                        # Add delay between retries
                        if attempt > 0:
                            delay = 2 ** attempt  # Exponential backoff: 2s, 4s
                            logger.info(f"Waiting {delay}s before retry attempt {attempt + 1}")
                            await asyncio.sleep(delay)
                        
                        # Clean up any existing user data directory if this is a retry
                        if attempt > 0 and os.path.exists(user_data_dir):
                            try:
                                import shutil
                                shutil.rmtree(user_data_dir, ignore_errors=True)
                                logger.info(f"Cleaned up user data directory for retry: {user_data_dir}")
                                # Recreate the directory
                                os.makedirs(user_data_dir, exist_ok=True)
                            except Exception as cleanup_error:
                                logger.warning(f"Failed to cleanup user data directory: {cleanup_error}")
                        
                        logger.info(f"Launching browser attempt {attempt + 1}/{max_retries} with user_data_dir: {user_data_dir}")
                        
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
                                "--disable-features=VizDisplayCompositor",
                                "--disable-dev-shm-usage",
                                "--no-first-run",
                                "--disable-default-apps",
                                "--disable-extensions",
                                "--disable-background-timer-throttling",
                                "--disable-backgrounding-occluded-windows",
                                "--disable-renderer-backgrounding",
                                "--disable-field-trial-config",
                                "--disable-ipc-flooding-protection"
                            ]
                        )
                        
                        logger.info(f"Browser launched successfully on attempt {attempt + 1}")
                        break
                        
                    except Exception as launch_error:
                        error_msg = str(launch_error)
                        logger.error(f"Browser launch attempt {attempt + 1}/{max_retries} failed: {error_msg}")
                        
                        # Log more details about the error
                        if "Target page, context or browser has been closed" in error_msg:
                            logger.error("Browser closed during launch - possible user data directory conflict")
                        elif "Failed to launch browser" in error_msg:
                            logger.error("Browser process failed to start - checking system resources")
                        
                        if attempt == max_retries - 1:
                            # Final cleanup attempt before giving up
                            if os.path.exists(user_data_dir):
                                try:
                                    import shutil
                                    shutil.rmtree(user_data_dir, ignore_errors=True)
                                    logger.info(f"Final cleanup of user data directory: {user_data_dir}")
                                except Exception as cleanup_error:
                                    logger.warning(f"Final cleanup failed: {cleanup_error}")
                            
                            raise Exception(f"Failed to launch browser after {max_retries} attempts: {error_msg}")
                
                if not browser:
                    raise Exception("Browser instance is None after launch attempts")
                
                # Verify browser context is not closed immediately after creation
                try:
                    # Check if context is still valid by accessing pages
                    _ = browser.pages
                except Exception:
                    raise Exception("Browser context was closed immediately after creation")
                
                # Create initial page
                try:
                    page = await browser.new_page()
                    # Enable screenshot capabilities
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                except Exception as page_error:
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
                try:
                    logger.info(f"Attempting to navigate to {default_url} for platform {platform}")
                    await page.goto(default_url, wait_until="networkidle", timeout=30000)
                    page_url = page.url
                    logger.info(f"Successfully navigated to {page_url} for platform {platform}")
                except Exception as nav_error:
                    logger.warning(f"Failed to navigate to {default_url}: {nav_error}, using blank page")
                    # Keep the blank page, don't fail the entire operation
                    page_url = "about:blank"
                
                # Generate unique instance_id with retry logic to avoid duplicates
                max_id_retries = 5
                instance_id = None
                
                for id_attempt in range(max_id_retries):
                    temp_instance_id = f"browser_{uuid.uuid4().hex[:12]}"
                    
                    # Check if instance_id already exists in database
                    existing_instance = await self.db.browser_instances.find_one({"instance_id": temp_instance_id})
                    
                    if not existing_instance:
                        instance_id = temp_instance_id
                        logger.info(f"Generated unique instance_id: {instance_id} on attempt {id_attempt + 1}")
                        break
                    else:
                        logger.warning(f"Instance ID {temp_instance_id} already exists, retrying... (attempt {id_attempt + 1}/{max_id_retries})")
                        
                        # If this is an inactive instance, try to clean it up
                        if not existing_instance.get("is_active", False):
                            try:
                                await self.db.browser_instances.delete_one({"instance_id": temp_instance_id})
                                logger.info(f"Cleaned up inactive instance: {temp_instance_id}")
                                instance_id = temp_instance_id
                                break
                            except Exception as cleanup_error:
                                logger.warning(f"Failed to cleanup inactive instance {temp_instance_id}: {cleanup_error}")
                
                if not instance_id:
                    raise Exception(f"Failed to generate unique instance_id after {max_id_retries} attempts")
                
                self._instance_locks[instance_id] = asyncio.Lock()
                
                # Store browser and page references
                self.browsers[instance_id] = browser
                self.pages[f"{instance_id}_main"] = page
                
                # Setup enhanced tab management
                await self._setup_page_listeners(instance_id, browser, page)
                
                # Attempt to restore previous login session
                await self._restore_login_session(instance_id, session_id, platform, page)
                
                # Save instance info to database with duplicate key error handling
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
                
                try:
                    # First, try to delete any existing record with the same instance_id
                    existing_result = await self.db.browser_instances.delete_one({"instance_id": instance_id})
                    if existing_result.deleted_count > 0:
                        logger.info(f"Deleted existing instance record for {instance_id}")
                    
                    # Now insert the new record
                    await self.db.browser_instances.insert_one(instance_data)
                    logger.info(f"Successfully saved instance data for {instance_id}")
                except Exception as db_error:
                    # If we still get a duplicate key error, clean up and raise
                    if "duplicate key error" in str(db_error).lower():
                        logger.error(f"Duplicate key error persists for {instance_id}, cleaning up browser")
                        try:
                            await browser.close()
                            if instance_id in self.browsers:
                                del self.browsers[instance_id]
                            if f"{instance_id}_main" in self.pages:
                                del self.pages[f"{instance_id}_main"]
                            if instance_id in self._instance_locks:
                                del self._instance_locks[instance_id]
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to cleanup browser after duplicate key error: {cleanup_error}")
                    raise db_error
                
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
                "page_count": len(browser.pages),
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
                # browser is actually a BrowserContext object from launch_persistent_context
                page = await browser.new_page()
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
            # browser is actually a BrowserContext object from launch_persistent_context
            context = browser
            
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
            # browser is actually a BrowserContext object from launch_persistent_context
            context = browser
            
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
        # Use instance-specific lock if available, otherwise use cleanup lock
        lock = self._instance_locks.get(instance_id, self._cleanup_lock)
        
        async with lock:
            try:
                # Close browser if exists
                if instance_id in self.browsers:
                    browser = self.browsers[instance_id]
                    try:
                        # Check if browser context is still valid before closing
                        try:
                            # Test if context is still accessible
                            _ = browser.pages
                            await browser.close()
                        except Exception as context_error:
                            logger.warning(f"Browser context already closed for {instance_id}: {context_error}")
                    except Exception as close_error:
                        logger.warning(f"Error closing browser {instance_id}: {close_error}")
                    finally:
                        del self.browsers[instance_id]
                
                # Remove pages
                pages_to_remove = [key for key in self.pages.keys() if key.startswith(f"{instance_id}_")]
                for page_key in pages_to_remove:
                    del self.pages[page_key]
                
                # Remove instance lock
                if instance_id in self._instance_locks:
                    del self._instance_locks[instance_id]
                
                # Stop any continuous crawl tasks for this instance
                await self._stop_continuous_crawl_for_instance(instance_id)
                
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
        async with self._cleanup_lock:
            try:
                if instance_id in self.browsers:
                    try:
                        # Check if context is still valid before closing
                        _ = self.browsers[instance_id].pages
                        await self.browsers[instance_id].close()
                    except Exception as context_error:
                        logger.warning(f"Browser context already closed for {instance_id}: {context_error}")
                    finally:
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
    
    async def _cleanup_oldest_instances(self, count: int = 1, max_retries: int = 3):
        """Clean up oldest instances to make room for new ones with enhanced error handling"""
        logger.info(f"Starting cleanup of {count} oldest instances globally")
        
        for retry in range(max_retries):
            try:
                # Get current total instance count
                total_count = await self.db.browser_instances.count_documents({"is_active": True})
                logger.info(f"Total active instances before cleanup: {total_count} (attempt {retry + 1}/{max_retries})")
                
                cursor = self.db.browser_instances.find({
                    "is_active": True,
                    "expires_at": {"$gt": datetime.utcnow()}  # Only get non-expired instances
                }).sort("last_activity", 1).limit(count)
                
                oldest_instances = await cursor.to_list(length=None)
                logger.info(f"Found {len(oldest_instances)} oldest instances to cleanup")
                
                if not oldest_instances:
                    logger.warning("No valid instances found for global cleanup")
                    # Clean up any expired instances
                    await self.cleanup_expired_instances()
                    return True
                
                cleanup_success = 0
                for instance in oldest_instances:
                    instance_id = instance["instance_id"]
                    platform = instance.get("platform", "unknown")
                    logger.info(f"Cleaning up oldest instance {instance_id} from platform {platform}")
                    
                    try:
                        if await self.close_browser_instance(instance_id):
                            cleanup_success += 1
                            logger.info(f"Successfully cleaned up oldest instance {instance_id}")
                        else:
                            logger.error(f"Failed to close oldest instance {instance_id}")
                    except Exception as instance_error:
                        logger.error(f"Error cleaning up oldest instance {instance_id}: {instance_error}")
                
                if cleanup_success > 0:
                    new_total = await self.db.browser_instances.count_documents({"is_active": True})
                    logger.info(f"Global cleanup completed: {cleanup_success}/{len(oldest_instances)} successful, new total: {new_total}")
                    return True
                elif retry < max_retries - 1:
                    logger.warning(f"Global cleanup attempt {retry + 1} failed, retrying...")
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Failed to cleanup oldest instances (attempt {retry + 1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    await asyncio.sleep(2)
        
        logger.error("All global cleanup attempts failed")
        return False
    
    async def _cleanup_platform_instances(self, platform: str, count: int = 1, max_retries: int = 3):
        """Clean up oldest instances for a specific platform with enhanced error handling"""
        logger.info(f"Starting cleanup of {count} oldest instances for platform {platform}")
        
        for retry in range(max_retries):
            try:
                # Get current platform instance count before cleanup
                current_count = await self._get_platform_instance_count(platform)
                logger.info(f"Platform {platform} has {current_count} active instances before cleanup (attempt {retry + 1}/{max_retries})")
                
                if current_count == 0:
                    logger.info(f"No active instances found for platform {platform}")
                    return True
                
                # Find oldest instances with detailed logging
                cursor = self.db.browser_instances.find({
                    "platform": platform,
                    "is_active": True,
                    "expires_at": {"$gt": datetime.utcnow()}  # Only get non-expired instances
                }).sort("last_activity", 1).limit(count)
                
                oldest_instances = await cursor.to_list(length=None)
                logger.info(f"Found {len(oldest_instances)} instances to cleanup for platform {platform}")
                
                if not oldest_instances:
                    logger.warning(f"No valid instances found for cleanup on platform {platform}")
                    # Check for expired instances that might be causing the issue
                    await self._force_cleanup_expired_instances(platform)
                    return True
                
                # Track cleanup success
                cleanup_success = 0
                cleanup_errors = []
                
                for instance in oldest_instances:
                    instance_id = instance["instance_id"]
                    last_activity = instance.get("last_activity", "unknown")
                    logger.info(f"Attempting to cleanup instance {instance_id} (last_activity: {last_activity})")
                    
                    try:
                        # Validate instance state before cleanup
                        if await self._validate_instance_state(instance_id):
                            success = await self.close_browser_instance(instance_id)
                            if success:
                                cleanup_success += 1
                                logger.info(f"Successfully cleaned up instance {instance_id}")
                            else:
                                error_msg = f"Failed to close instance {instance_id}"
                                cleanup_errors.append(error_msg)
                                logger.error(error_msg)
                        else:
                            # Force cleanup invalid instance
                            await self._force_cleanup_invalid_instance(instance_id)
                            cleanup_success += 1
                            logger.info(f"Force cleaned up invalid instance {instance_id}")
                            
                    except Exception as instance_error:
                        error_msg = f"Error cleaning up instance {instance_id}: {str(instance_error)}"
                        cleanup_errors.append(error_msg)
                        logger.error(error_msg)
                        # Try force cleanup as fallback
                        try:
                            await self._force_cleanup_invalid_instance(instance_id)
                            cleanup_success += 1
                            logger.info(f"Force cleanup succeeded for instance {instance_id}")
                        except Exception as force_error:
                            logger.error(f"Force cleanup also failed for instance {instance_id}: {force_error}")
                
                # Verify cleanup results
                new_count = await self._get_platform_instance_count(platform)
                logger.info(f"Platform {platform} cleanup results: {cleanup_success}/{len(oldest_instances)} successful, new count: {new_count}")
                
                if cleanup_success > 0:
                    logger.info(f"Successfully cleaned up {cleanup_success} instances for platform {platform}")
                    return True
                elif retry < max_retries - 1:
                    logger.warning(f"Cleanup attempt {retry + 1} failed, retrying in 1 second...")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"All cleanup attempts failed for platform {platform}. Errors: {cleanup_errors}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to cleanup platform instances for {platform} (attempt {retry + 1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    logger.info(f"Retrying cleanup in 2 seconds...")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"All cleanup attempts exhausted for platform {platform}")
                    return False
        
        return False
    
    async def _validate_instance_state(self, instance_id: str) -> bool:
        """Validate if an instance is in a consistent state"""
        try:
            # Check if instance exists in database
            db_instance = await self.db.browser_instances.find_one({"instance_id": instance_id})
            if not db_instance:
                logger.warning(f"Instance {instance_id} not found in database")
                return False
            
            # Check if instance is marked as active but expired
            if db_instance.get("is_active", False) and db_instance.get("expires_at", datetime.utcnow()) <= datetime.utcnow():
                logger.warning(f"Instance {instance_id} is active but expired")
                return False
            
            # Check if instance exists in memory but not in database or vice versa
            in_memory = instance_id in self.browser_instances
            in_db_active = db_instance.get("is_active", False)
            
            if in_memory != in_db_active:
                logger.warning(f"Instance {instance_id} state mismatch - in_memory: {in_memory}, db_active: {in_db_active}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating instance state for {instance_id}: {e}")
            return False
    
    async def _force_cleanup_invalid_instance(self, instance_id: str):
        """Force cleanup of an invalid instance"""
        try:
            logger.info(f"Force cleaning up invalid instance {instance_id}")
            
            # Remove from memory if exists
            if instance_id in self.browser_instances:
                try:
                    context = self.browser_instances[instance_id]
                    if context and not context.is_closed():
                        await context.close()
                except Exception as e:
                    logger.warning(f"Error closing browser context for {instance_id}: {e}")
                
                del self.browser_instances[instance_id]
                logger.info(f"Removed instance {instance_id} from memory")
            
            # Remove associated pages
            if instance_id in self.instance_pages:
                del self.instance_pages[instance_id]
                logger.info(f"Removed pages for instance {instance_id}")
            
            # Remove instance lock
            if instance_id in self.instance_locks:
                del self.instance_locks[instance_id]
                logger.info(f"Removed lock for instance {instance_id}")
            
            # Force update database status
            result = await self.db.browser_instances.update_one(
                {"instance_id": instance_id},
                {
                    "$set": {
                        "is_active": False,
                        "closed_at": datetime.utcnow(),
                        "force_cleaned": True
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Force updated database status for instance {instance_id}")
            else:
                logger.warning(f"No database record updated for instance {instance_id}")
                
        except Exception as e:
            logger.error(f"Error in force cleanup for instance {instance_id}: {e}")
            raise
    
    async def _force_cleanup_expired_instances(self, platform: str = None):
        """Force cleanup of expired instances for a specific platform or all platforms"""
        try:
            query = {
                "is_active": True,
                "expires_at": {"$lte": datetime.utcnow()}
            }
            
            if platform:
                query["platform"] = platform
                logger.info(f"Force cleaning up expired instances for platform {platform}")
            else:
                logger.info("Force cleaning up all expired instances")
            
            expired_instances = await self.db.browser_instances.find(query).to_list(length=None)
            
            if not expired_instances:
                logger.info(f"No expired instances found{' for platform ' + platform if platform else ''}")
                return
            
            logger.info(f"Found {len(expired_instances)} expired instances to force cleanup")
            
            for instance in expired_instances:
                instance_id = instance["instance_id"]
                try:
                    await self._force_cleanup_invalid_instance(instance_id)
                    logger.info(f"Force cleaned up expired instance {instance_id}")
                except Exception as e:
                    logger.error(f"Failed to force cleanup expired instance {instance_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in force cleanup of expired instances: {e}")
    
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
    
    @log_async_function_call
    async def check_login_status(self, instance_id: str) -> dict:
        """Check login status for a browser instance with enhanced reliability"""
        try:
            logger.info(f"开始检查实例 {instance_id} 的登录状态")
            
            if instance_id not in self.browsers:
                logger.warning(f"实例 {instance_id} 未找到")
                return {"is_logged_in": False, "error": "Instance not found"}
            
            # Get instance data from database with auto-repair
            instance_data = await self.db.browser_instances.find_one({
                "instance_id": instance_id,
                "is_active": True
            })
            
            if not instance_data:
                logger.warning(f"实例 {instance_id} 的数据库记录未找到，尝试自动修复")
                # Try to repair missing database record
                try:
                    browser = self.browsers[instance_id]
                    # Extract platform from instance_id or use default
                    platform = "xiaohongshu"  # Default platform
                    if "_" in instance_id:
                        platform_part = instance_id.split("_")[0]
                        if platform_part in ["xiaohongshu", "weibo", "douyin", "bilibili"]:
                            platform = platform_part
                    
                    # Create missing database record
                    current_time = datetime.now()
                    repair_data = {
                        "instance_id": instance_id,
                        "platform": platform,
                        "is_active": True,
                        "created_at": current_time,
                        "updated_at": current_time,
                        "current_url": "unknown",
                        "page_count": 1,
                        "is_logged_in": False,
                        "login_user": None,
                        "last_login_check": current_time,
                        "status": "active"
                    }
                    
                    # Try to get current page URL if available
                    try:
                        context = browser
                        if context.pages and len(context.pages) > 0:
                            page = context.pages[-1]
                            if not page.is_closed():
                                repair_data["current_url"] = page.url
                                repair_data["page_count"] = len(context.pages)
                    except Exception as url_error:
                        logger.debug(f"无法获取页面URL进行修复: {url_error}")
                    
                    await self.db.browser_instances.insert_one(repair_data)
                    logger.info(f"已自动修复实例 {instance_id} 的数据库记录")
                    instance_data = repair_data
                    
                except Exception as repair_error:
                    logger.error(f"自动修复数据库记录失败: {repair_error}")
                    return {"is_logged_in": False, "error": "Instance data not found and repair failed"}
            
            platform = instance_data["platform"]
            browser = self.browsers[instance_id]
            logger.info(f"检查平台 {platform} 的登录状态")
            
            # Get the current active page with better error handling
            page = None
            try:
                # browser is actually a BrowserContext object from launch_persistent_context
                context = browser
                if context.pages and len(context.pages) > 0:
                    # Try to find the most suitable page for login detection
                    suitable_page = None
                    for p in reversed(context.pages):  # Start from most recent
                        try:
                            # Check if page is accessible and not closed
                            if not p.is_closed():
                                url = p.url
                                # Prefer pages that are not login/register pages
                                if not any(keyword in url.lower() for keyword in ['login', 'signin', 'register', 'signup', 'auth']):
                                    suitable_page = p
                                    break
                                elif suitable_page is None:  # Fallback to any accessible page
                                    suitable_page = p
                        except Exception:
                            continue
                    
                    page = suitable_page or context.pages[-1]  # Final fallback
                    logger.info(f"使用页面进行登录检测: {page.url}")
                else:
                    logger.warning(f"实例 {instance_id} 没有找到可用页面")
                    return {"is_logged_in": False, "error": "No pages found in browser context"}
            except Exception as page_error:
                logger.error(f"获取实例 {instance_id} 当前页面时出错: {page_error}")
                # Fallback to main page if available
                main_page_key = f"{instance_id}_main"
                if main_page_key in self.pages:
                    page = self.pages[main_page_key]
                    logger.info(f"回退到主页面: {page.url}")
                else:
                    return {"is_logged_in": False, "error": "No accessible page found"}
            
            if not page or page.is_closed():
                logger.error(f"实例 {instance_id} 没有可用于登录检测的页面")
                return {"is_logged_in": False, "error": "No page available for login detection"}
            
            # Get current page URL for context with error handling
            try:
                current_url = page.url
                logger.info(f"在页面 {current_url} 上检查 {platform} 的登录状态")
            except Exception as url_error:
                logger.warning(f"无法获取页面URL: {url_error}")
                current_url = "unknown"
            
            # Wait for page to be ready
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.debug("页面加载状态等待超时，继续检测")
            
            # Get platform-specific selectors with fallback
            selectors = self.platform_configs.get(platform, {})
            logged_in_selectors = selectors.get("logged_in_selectors", [])
            login_selectors = selectors.get("login_selectors", [])
            
            # Enhanced login detection with multiple strategies
            is_logged_in = False
            login_user = None
            detection_method = "none"
            detection_confidence = 0  # 0-100, higher means more confident
            
            # Strategy 1: Check for logged-in indicators (highest confidence)
            logger.info(f"策略1: 检查已登录指示器，共 {len(logged_in_selectors)} 个选择器")
            strategy1_results = []
            
            for i, selector in enumerate(logged_in_selectors):
                try:
                    logger.debug(f"  检查选择器 {i+1}/{len(logged_in_selectors)}: {selector}")
                    element = await page.query_selector(selector)
                    
                    if element:
                        # Verify element is visible and has meaningful content
                        is_visible = await element.is_visible()
                        bounding_box = await element.bounding_box()
                        
                        logger.debug(f"    元素找到: 可见={is_visible}, 边界框={bounding_box is not None}")
                        
                        if is_visible and bounding_box:
                            # Enhanced confidence calculation based on selector specificity
                            base_confidence = 95
                            if "reds-icon-user" in selector or "xiaohongshu" in selector.lower():
                                base_confidence = 98  # Platform-specific selectors get higher confidence
                            elif "data-testid" in selector or "aria-label" in selector:
                                base_confidence = 92  # Semantic selectors are reliable
                            elif "[class*=" in selector:
                                base_confidence = 85  # Wildcard selectors are less specific
                            
                            is_logged_in = True
                            detection_method = f"logged_in_selector: {selector}"
                            detection_confidence = base_confidence
                            
                            # Enhanced username extraction with better validation
                            username_keywords = ["username", "user-name", "user_name", "gn_name", "nickname", "user-info", "display-name", "current-user"]
                            if any(keyword in selector.lower() for keyword in username_keywords):
                                try:
                                    text_content = await element.text_content()
                                    inner_text = await element.inner_text()
                                    
                                    # Use inner_text if available as it's more reliable
                                    username_text = (inner_text or text_content or "").strip()
                                    
                                    if username_text and len(username_text) > 0 and len(username_text) <= 100:
                                        # Validate username format (avoid generic text)
                                        if not any(generic in username_text.lower() for generic in ["登录", "login", "用户", "user", "头像", "avatar", "菜单", "menu"]):
                                            login_user = username_text[:50]  # Reasonable length limit
                                            logger.info(f"    ✓ 通过选择器检测到登录: {selector}, 用户: {login_user}")
                                        else:
                                            logger.debug(f"    跳过通用文本: {username_text}")
                                except Exception as text_error:
                                    logger.debug(f"    提取用户名失败: {text_error}")
                            else:
                                logger.info(f"    ✓ 通过选择器检测到登录: {selector}")
                            
                            strategy1_results.append({
                                "selector": selector,
                                "confidence": base_confidence,
                                "username": login_user
                            })
                            break
                        else:
                            logger.debug(f"    元素不可见或无边界框")
                    else:
                        logger.debug(f"    元素未找到")
                        
                except Exception as e:
                    logger.debug(f"    检查选择器时出错: {e}")
                    continue
            
            if strategy1_results:
                logger.info(f"策略1成功: 找到 {len(strategy1_results)} 个匹配的登录指示器")
            else:
                logger.info("策略1失败: 未找到登录指示器")
            
            # Strategy 2: Check for login buttons (indicates not logged in)
            has_login_button = False
            strategy2_results = []
            
            if not is_logged_in:
                logger.info(f"策略2: 检查登录按钮，共 {len(login_selectors)} 个选择器")
                
                for i, selector in enumerate(login_selectors):
                    try:
                        logger.debug(f"  检查登录按钮 {i+1}/{len(login_selectors)}: {selector}")
                        element = await page.query_selector(selector)
                        
                        if element:
                            # Verify element is visible and clickable
                            is_visible = await element.is_visible()
                            bounding_box = await element.bounding_box()
                            
                            logger.debug(f"    登录按钮找到: 可见={is_visible}, 边界框={bounding_box is not None}")
                            
                            if is_visible and bounding_box:
                                # Enhanced confidence for login button detection
                                base_confidence = 85
                                if "登录" in selector or "login" in selector.lower():
                                    base_confidence = 90  # Explicit login text gets higher confidence
                                elif "sign-in" in selector.lower() or "signin" in selector.lower():
                                    base_confidence = 88
                                elif "data-testid" in selector:
                                    base_confidence = 87  # Test IDs are reliable
                                
                                has_login_button = True
                                detection_method = f"login_button_found: {selector}"
                                detection_confidence = base_confidence
                                
                                # Try to get button text for validation
                                try:
                                    button_text = await element.inner_text()
                                    if button_text and button_text.strip():
                                        logger.info(f"    ✓ 发现登录按钮: {selector}, 文本: '{button_text.strip()}' - 用户未登录")
                                    else:
                                        logger.info(f"    ✓ 发现登录按钮: {selector} - 用户未登录")
                                except:
                                    logger.info(f"    ✓ 发现登录按钮: {selector} - 用户未登录")
                                
                                strategy2_results.append({
                                    "selector": selector,
                                    "confidence": base_confidence,
                                    "text": button_text.strip() if 'button_text' in locals() and button_text else None
                                })
                                break
                            else:
                                logger.debug(f"    登录按钮不可见或无边界框")
                        else:
                            logger.debug(f"    登录按钮未找到")
                            
                    except Exception as e:
                        logger.debug(f"    检查登录按钮时出错: {e}")
                        continue
                
                if strategy2_results:
                    logger.info(f"策略2成功: 找到 {len(strategy2_results)} 个登录按钮，判断为未登录")
                else:
                    logger.info("策略2: 未找到登录按钮")
            else:
                logger.info("策略2跳过: 已通过策略1确认登录状态")
            
            # Strategy 3: Enhanced detection using common patterns
            strategy3_results = []
            
            if not is_logged_in and not has_login_button:
                logger.info("策略3: 使用通用模式检测登录状态")
                
                # Enhanced common logged-in indicators with platform-specific patterns
                common_logged_in_patterns = [
                    # High-confidence patterns
                    '[data-testid*="user"]',
                    '[data-testid*="profile"]',
                    '[data-testid*="account"]',
                    # User avatar and info patterns
                    '[class*="user"][class*="avatar"]',
                    '[class*="profile"][class*="menu"]',
                    '[class*="account"][class*="dropdown"]',
                    '[class*="user"][class*="info"]',
                    # Navigation and menu patterns
                    'button[class*="user"]',
                    '.user-menu, .profile-menu, .account-menu',
                    '.user-dropdown, .profile-dropdown',
                    # Accessibility patterns
                    '[aria-label*="用户"], [aria-label*="账户"], [aria-label*="个人"]',
                    '[aria-label*="user"], [aria-label*="account"], [aria-label*="profile"]',
                    '[title*="用户"], [title*="账户"], [title*="个人"]',
                    '[title*="user"], [title*="account"], [title*="profile"]',
                    # Platform-specific patterns
                    '.reds-icon-user, .user-icon, .avatar-wrapper',
                    '[class*="current-user"], [class*="logged-user"]',
                    '.header-user, .nav-user, .top-user'
                ]
                
                for i, pattern in enumerate(common_logged_in_patterns):
                    try:
                        logger.debug(f"  检查通用模式 {i+1}/{len(common_logged_in_patterns)}: {pattern}")
                        element = await page.query_selector(pattern)
                        
                        if element:
                            is_visible = await element.is_visible()
                            bounding_box = await element.bounding_box()
                            
                            logger.debug(f"    通用模式元素找到: 可见={is_visible}, 边界框={bounding_box is not None}")
                            
                            if is_visible and bounding_box:
                                # Enhanced validation for user elements
                                element_text = await element.text_content()
                                inner_text = await element.inner_text()
                                
                                # Use inner_text if available as it's more reliable
                                text_content = (inner_text or element_text or "").strip()
                                
                                # Enhanced confidence calculation
                                base_confidence = 70
                                if "data-testid" in pattern:
                                    base_confidence = 80  # Test IDs are more reliable
                                elif "aria-label" in pattern or "title" in pattern:
                                    base_confidence = 75  # Accessibility attributes are good
                                elif "reds-icon-user" in pattern or "user-icon" in pattern:
                                    base_confidence = 85  # Platform-specific icons are highly reliable
                                
                                # Validate that it's actually a user element
                                if text_content and len(text_content) > 0:
                                    # Avoid generic text that doesn't indicate login
                                    generic_texts = ["登录", "login", "注册", "register", "菜单", "menu", "更多", "more", "设置", "settings"]
                                    if not any(generic in text_content.lower() for generic in generic_texts):
                                        is_logged_in = True
                                        detection_method = f"common_pattern: {pattern}"
                                        detection_confidence = base_confidence
                                        login_user = text_content[:50]  # Reasonable length limit
                                        
                                        logger.info(f"    ✓ 通过通用模式检测到登录: {pattern}, 用户: {login_user}")
                                        
                                        strategy3_results.append({
                                            "pattern": pattern,
                                            "confidence": base_confidence,
                                            "username": login_user
                                        })
                                        break
                                    else:
                                        logger.debug(f"    跳过通用文本: {text_content}")
                                else:
                                    # Element exists but no meaningful text - still might indicate login
                                    # Lower confidence for elements without text
                                    is_logged_in = True
                                    detection_method = f"common_pattern: {pattern}"
                                    detection_confidence = base_confidence - 15
                                    
                                    logger.info(f"    ✓ 通过通用模式检测到登录: {pattern} (无文本内容)")
                                    
                                    strategy3_results.append({
                                        "pattern": pattern,
                                        "confidence": base_confidence - 15,
                                        "username": None
                                    })
                                    break
                            else:
                                logger.debug(f"    通用模式元素不可见或无边界框")
                        else:
                            logger.debug(f"    通用模式元素未找到")
                            
                    except Exception as e:
                        logger.debug(f"    检查通用模式时出错: {e}")
                        continue
                
                if strategy3_results:
                    logger.info(f"策略3成功: 通过 {len(strategy3_results)} 个通用模式检测到登录")
                else:
                    logger.info("策略3失败: 未通过通用模式检测到登录")
            else:
                if is_logged_in:
                    logger.info("策略3跳过: 已确认登录状态")
                else:
                    logger.info("策略3跳过: 已发现登录按钮，确认未登录状态")
            
            # Strategy 4: Cookie-based detection (medium confidence)
            strategy4_results = []
            
            if not is_logged_in and not has_login_button:
                logger.info("策略4: 使用Cookie检测登录状态")
                try:
                    cookies = await page.context.cookies()
                    logger.debug(f"  获取到 {len(cookies)} 个Cookie")
                    
                    login_cookies = []
                    
                    # Enhanced cookie patterns with platform-specific ones and priorities
                    cookie_patterns = {
                        'high_confidence': {
                            'weibo': ['SUB', 'SUBP', 'SSOLoginState', 'login_sid_t', 'weibouid'],
                            'xiaohongshu': ['web_session', 'xsecappid', 'a1', 'webId', 'customer-sso-sid'],
                            'douyin': ['sessionid', 'sid_guard', 'uid_tt', 'passport_csrf_token'],
                            'generic': ['access_token', 'refresh_token', 'authtoken', 'jwt']
                        },
                        'medium_confidence': {
                            'platform_specific': ['weibo', 'wb_', 'sina', 'xhs', 'xiaohongshu', 'dy_', 'douyin', 'ttwid'],
                            'generic': ['session', 'auth', 'token', 'login', 'user', 'uid', 'userid', 'logged_in', 'signin', 'passport', 'account', 'sso']
                        }
                    }
                    
                    # Check high-confidence patterns first
                    platform_high_confidence = cookie_patterns['high_confidence'].get(platform, [])
                    generic_high_confidence = cookie_patterns['high_confidence']['generic']
                    
                    logger.debug(f"  检查高置信度Cookie模式: 平台特定={platform_high_confidence}, 通用={generic_high_confidence}")
                    
                    for cookie in cookies:
                        cookie_name = cookie['name']
                        cookie_name_lower = cookie_name.lower()
                        cookie_value = cookie['value']
                        
                        # Check high-confidence platform-specific patterns
                        for pattern in platform_high_confidence:
                            if pattern.lower() in cookie_name_lower:
                                if (cookie_value and len(cookie_value) > 10 and
                                    cookie_value not in ['null', 'undefined', 'false', '0', 'guest', 'anonymous'] and
                                    not cookie_value.startswith('deleted')):
                                    
                                    login_cookies.append(cookie_name)
                                    is_logged_in = True
                                    detection_method = f"cookie_detection: {cookie_name}"
                                    detection_confidence = 85  # High confidence for platform-specific
                                    
                                    logger.info(f"    ✓ 通过高置信度平台Cookie检测到登录: {cookie_name}")
                                    logger.debug(f"      Cookie值长度: {len(cookie_value)}")
                                    
                                    strategy4_results.append({
                                        "cookie_name": cookie_name,
                                        "pattern": pattern,
                                        "confidence": 85,
                                        "type": "platform_high_confidence"
                                    })
                                    break
                                else:
                                    logger.debug(f"    跳过无效高置信度Cookie: {cookie_name}={cookie_value[:20] if cookie_value else 'None'}...")
                        
                        if is_logged_in:
                            break
                        
                        # Check high-confidence generic patterns
                        for pattern in generic_high_confidence:
                            if pattern.lower() in cookie_name_lower:
                                if (cookie_value and len(cookie_value) > 15 and  # Higher threshold for generic
                                    cookie_value not in ['null', 'undefined', 'false', '0', 'guest', 'anonymous'] and
                                    not cookie_value.startswith('deleted')):
                                    
                                    login_cookies.append(cookie_name)
                                    is_logged_in = True
                                    detection_method = f"cookie_detection: {cookie_name}"
                                    detection_confidence = 80  # High confidence for auth tokens
                                    
                                    logger.info(f"    ✓ 通过高置信度通用Cookie检测到登录: {cookie_name}")
                                    logger.debug(f"      Cookie值长度: {len(cookie_value)}")
                                    
                                    strategy4_results.append({
                                        "cookie_name": cookie_name,
                                        "pattern": pattern,
                                        "confidence": 80,
                                        "type": "generic_high_confidence"
                                    })
                                    break
                        
                        if is_logged_in:
                            break
                    
                    # If no high-confidence cookies found, check medium-confidence patterns
                    if not is_logged_in:
                        logger.debug("  检查中等置信度Cookie模式")
                        
                        all_medium_patterns = (cookie_patterns['medium_confidence']['platform_specific'] + 
                                             cookie_patterns['medium_confidence']['generic'])
                        
                        for cookie in cookies:
                            cookie_name = cookie['name']
                            cookie_name_lower = cookie_name.lower()
                            cookie_value = cookie['value']
                            
                            for pattern in all_medium_patterns:
                                if pattern in cookie_name_lower:
                                    if (cookie_value and len(cookie_value) > 8 and
                                        cookie_value not in ['null', 'undefined', 'false', '0', 'guest', 'anonymous'] and
                                        not cookie_value.startswith('deleted')):
                                        
                                        # Calculate confidence based on pattern type
                                        base_confidence = 70
                                        if pattern in cookie_patterns['medium_confidence']['platform_specific']:
                                            base_confidence = 75  # Platform-specific gets higher confidence
                                        
                                        login_cookies.append(cookie_name)
                                        is_logged_in = True
                                        detection_method = f"cookie_detection: {cookie_name}"
                                        detection_confidence = base_confidence
                                        
                                        logger.info(f"    ✓ 通过中等置信度Cookie检测到登录: {cookie_name}")
                                        logger.debug(f"      Cookie值长度: {len(cookie_value)}, 置信度: {base_confidence}")
                                        
                                        strategy4_results.append({
                                            "cookie_name": cookie_name,
                                            "pattern": pattern,
                                            "confidence": base_confidence,
                                            "type": "medium_confidence"
                                        })
                                        break
                            
                            if is_logged_in:
                                break
                    
                    if strategy4_results:
                        logger.info(f"策略4成功: 通过 {len(strategy4_results)} 个Cookie检测到登录")
                        logger.info(f"检测到的Cookie: {', '.join([r['cookie_name'] for r in strategy4_results[:3]])}")
                    else:
                        logger.info("策略4失败: 未通过Cookie检测到登录")
                        
                except Exception as e:
                    logger.debug(f"策略4出错: 检查Cookie时发生异常: {e}")
            else:
                if is_logged_in:
                    logger.info("策略4跳过: 已确认登录状态")
                else:
                    logger.info("策略4跳过: 已发现登录按钮，确认未登录状态")
            
            # Strategy 5: localStorage/sessionStorage detection (medium confidence)
            if not is_logged_in and not has_login_button:
                logger.debug("策略5: 基于本地存储的检测")
                strategy5_results = []
                try:
                    # Enhanced storage scripts with better error handling
                    local_storage_script = """
                    () => {
                        try {
                            const storage = {};
                            for (let i = 0; i < localStorage.length; i++) {
                                const key = localStorage.key(i);
                                if (key) {
                                    try {
                                        const value = localStorage.getItem(key);
                                        if (value && value !== 'null' && value !== 'undefined') {
                                            storage[key] = value;
                                        }
                                    } catch (e) {
                                        // Skip problematic keys
                                    }
                                }
                            }
                            return storage;
                        } catch (e) {
                            return {};
                        }
                    }
                    """
                    
                    session_storage_script = """
                    () => {
                        try {
                            const storage = {};
                            for (let i = 0; i < sessionStorage.length; i++) {
                                const key = sessionStorage.key(i);
                                if (key) {
                                    try {
                                        const value = sessionStorage.getItem(key);
                                        if (value && value !== 'null' && value !== 'undefined') {
                                            storage[key] = value;
                                        }
                                    } catch (e) {
                                        // Skip problematic keys
                                    }
                                }
                            }
                            return storage;
                        } catch (e) {
                            return {};
                        }
                    }
                    """
                    
                    local_storage = await page.evaluate(local_storage_script)
                    session_storage = await page.evaluate(session_storage_script)
                    
                    logger.debug(f"策略5: 获取到 {len(local_storage)} 个localStorage项, {len(session_storage)} 个sessionStorage项")
                    
                    # Tiered storage patterns with confidence levels
                    high_confidence_patterns = [
                        # Platform-specific high confidence patterns
                        'weibo_uid', 'wb_uid', 'xhs_user', 'dy_user', 'douyin_user',
                        'current_user_id', 'user_session', 'auth_token', 'access_token',
                        'login_token', 'passport_token', 'xiaohongshu_user'
                    ]
                    
                    medium_confidence_patterns = [
                        'user', 'auth', 'token', 'login', 'session', 'account',
                        'userid', 'username', 'isloggedin', 'logged_in', 'signin',
                        'refresh_token', 'authtoken', 'passport', 'current_user',
                        'user_info', 'profile', 'member', 'weibo_', 'wb_', 'xhs_', 
                        'dy_', 'douyin_'
                    ]
                    
                    # Check localStorage with tiered confidence
                    for key, value in local_storage.items():
                        key_lower = key.lower()
                        value_str = str(value).lower() if value else ''
                        
                        logger.debug(f"策略5: 检查localStorage键 '{key}', 值长度: {len(value_str)}")
                        
                        if (value and len(value_str) > 3 and 
                            value_str not in ['null', 'undefined', 'false', '', '0', 'guest', 'anonymous']):
                            
                            confidence = 0
                            storage_type = 'localStorage'
                            
                            # Check high confidence patterns first
                            for pattern in high_confidence_patterns:
                                if pattern in key_lower:
                                    confidence = 85
                                    logger.debug(f"策略5: 高置信度匹配 - {storage_type}.{key} (模式: {pattern})")
                                    break
                            
                            # Check medium confidence patterns if no high confidence match
                            if confidence == 0:
                                for pattern in medium_confidence_patterns:
                                    if pattern in key_lower:
                                        confidence = 65
                                        logger.debug(f"策略5: 中等置信度匹配 - {storage_type}.{key} (模式: {pattern})")
                                        break
                            
                            if confidence > 0:
                                strategy5_results.append({
                                    'storage_type': storage_type,
                                    'key': key,
                                    'confidence': confidence,
                                    'value_length': len(value_str)
                                })
                    
                    # Check sessionStorage with tiered confidence
                    for key, value in session_storage.items():
                        key_lower = key.lower()
                        value_str = str(value).lower() if value else ''
                        
                        logger.debug(f"策略5: 检查sessionStorage键 '{key}', 值长度: {len(value_str)}")
                        
                        if (value and len(value_str) > 3 and 
                            value_str not in ['null', 'undefined', 'false', '', '0', 'guest', 'anonymous']):
                            
                            confidence = 0
                            storage_type = 'sessionStorage'
                            
                            # Check high confidence patterns first
                            for pattern in high_confidence_patterns:
                                if pattern in key_lower:
                                    confidence = 85
                                    logger.debug(f"策略5: 高置信度匹配 - {storage_type}.{key} (模式: {pattern})")
                                    break
                            
                            # Check medium confidence patterns if no high confidence match
                            if confidence == 0:
                                for pattern in medium_confidence_patterns:
                                    if pattern in key_lower:
                                        confidence = 65
                                        logger.debug(f"策略5: 中等置信度匹配 - {storage_type}.{key} (模式: {pattern})")
                                        break
                            
                            if confidence > 0:
                                strategy5_results.append({
                                    'storage_type': storage_type,
                                    'key': key,
                                    'confidence': confidence,
                                    'value_length': len(value_str)
                                })
                    
                    if strategy5_results:
                        # Use highest confidence from found storage items
                        max_confidence = max(result['confidence'] for result in strategy5_results)
                        is_logged_in = True
                        detection_method = f"storage_detection: {', '.join([f"{r['storage_type']}.{r['key']}" for r in strategy5_results[:3]])}"
                        detection_confidence = max_confidence
                        
                        logger.info(f"策略5成功: 通过 {len(strategy5_results)} 个存储项检测到登录")
                        logger.info(f"检测到的存储项: {', '.join([f"{r['storage_type']}.{r['key']}" for r in strategy5_results[:3]])}")
                        logger.info(f"最高置信度: {max_confidence}%")
                        
                        # Enhanced username extraction
                        if not login_user:
                            username_patterns = ['username', 'user_name', 'nickname', 'displayname', 'display_name', 'real_name', 'screen_name']
                            for key, value in {**local_storage, **session_storage}.items():
                                if any(pattern in key.lower() for pattern in username_patterns):
                                    if value and isinstance(value, str) and len(value.strip()) > 0:
                                        # Try to parse JSON if it looks like JSON
                                        try:
                                            if value.strip().startswith(('{', '[')):
                                                import json
                                                parsed = json.loads(value)
                                                if isinstance(parsed, dict):
                                                    for user_key in ['name', 'username', 'nickname', 'display_name']:
                                                        if user_key in parsed and parsed[user_key]:
                                                            login_user = str(parsed[user_key]).strip()[:100]
                                                            logger.debug(f"策略5: 从JSON中提取用户名: {login_user}")
                                                            break
                                                elif isinstance(parsed, str):
                                                    login_user = parsed.strip()[:100]
                                                    logger.debug(f"策略5: 从JSON字符串中提取用户名: {login_user}")
                                            else:
                                                login_user = str(value).strip()[:100]
                                                logger.debug(f"策略5: 直接提取用户名: {login_user}")
                                            break
                                        except:
                                            login_user = str(value).strip()[:100]
                                            logger.debug(f"策略5: 解析失败，直接提取用户名: {login_user}")
                                            break
                    else:
                        logger.info("策略5失败: 未通过存储检测到登录")
                        
                except Exception as e:
                    logger.debug(f"策略5出错: 检查存储时发生异常: {e}")
            else:
                if is_logged_in:
                    logger.info("策略5跳过: 已确认登录状态")
                else:
                    logger.info("策略5跳过: 已发现登录按钮，确认未登录状态")
            
            # Strategy 6: API-based validation
            if not is_logged_in and not has_login_button:
                logger.debug("策略6: 基于API的验证")
                strategy6_results = []
                try:
                    # Platform-specific API endpoints to check login status
                    api_endpoints = {
                        'weibo': ['/api/config/list', '/api/statuses/home_timeline', '/api/account/settings'],
                        'xiaohongshu': ['/api/sns/web/v1/user/selfinfo', '/api/sns/web/v1/feed', '/api/sns/web/v1/user/otherinfo'],
                        'douyin': ['/aweme/v1/web/aweme/personal/', '/aweme/v1/web/general/search/single/', '/aweme/v1/web/commit/user/info/']
                    }
                    
                    platform_apis = api_endpoints.get(platform, [])
                    logger.debug(f"策略6: 平台 {platform} 有 {len(platform_apis)} 个API端点可检查")
                    
                    for api_path in platform_apis:
                        try:
                            logger.debug(f"策略6: 检查API端点 {api_path}")
                            
                            # Make a simple request to check if we get authenticated response
                            response = await page.evaluate(f"""
                            async () => {{
                                try {{
                                    const response = await fetch('{api_path}', {{
                                        method: 'GET',
                                        credentials: 'include',
                                        headers: {{
                                            'Accept': 'application/json',
                                            'X-Requested-With': 'XMLHttpRequest'
                                        }}
                                    }});
                                    return {{
                                        status: response.status,
                                        ok: response.ok,
                                        url: response.url,
                                        statusText: response.statusText
                                    }};
                                }} catch (error) {{
                                    return {{ error: error.message }};
                                }}
                            }}
                            """)
                            
                            logger.debug(f"策略6: API {api_path} 响应状态: {response.get('status')}, OK: {response.get('ok')}")
                            
                            # Determine confidence based on response
                            confidence = 0
                            result_type = 'unknown'
                            
                            if response.get('error'):
                                logger.debug(f"策略6: API {api_path} 请求失败: {response.get('error')}")
                                continue
                            
                            status = response.get('status')
                            if status == 200 and response.get('ok'):
                                # 200 OK suggests user is logged in
                                confidence = 80
                                result_type = 'logged_in'
                                logger.debug(f"策略6: API {api_path} 返回200，推断已登录")
                            elif status in [401, 403]:
                                # 401/403 suggests user is not logged in
                                confidence = 85
                                result_type = 'not_logged_in'
                                logger.debug(f"策略6: API {api_path} 返回{status}，推断未登录")
                            elif status == 302:
                                # Redirect might indicate need to login
                                confidence = 70
                                result_type = 'redirect_to_login'
                                logger.debug(f"策略6: API {api_path} 返回302重定向，可能需要登录")
                            elif status in [404, 500]:
                                # Server errors, can't determine login status
                                logger.debug(f"策略6: API {api_path} 返回{status}，无法确定登录状态")
                                continue
                            
                            if confidence > 0:
                                strategy6_results.append({
                                    'api_path': api_path,
                                    'status': status,
                                    'result_type': result_type,
                                    'confidence': confidence
                                })
                                
                                # Act on the result
                                if result_type == 'logged_in':
                                    is_logged_in = True
                                    detection_method = f"api_validation: {api_path}"
                                    detection_confidence = confidence
                                    logger.info(f"策略6成功: 通过API {api_path} 检测到登录 (状态: {status})")
                                    break
                                elif result_type in ['not_logged_in', 'redirect_to_login']:
                                    # Confirmed not logged in
                                    logger.info(f"策略6确认: 通过API {api_path} 确认未登录 (状态: {status})")
                                    break
                                
                        except Exception as api_error:
                            logger.debug(f"策略6出错: 检查API {api_path} 时发生异常: {api_error}")
                            continue
                    
                    if strategy6_results:
                        if is_logged_in:
                            logger.info(f"策略6成功: 通过API验证检测到登录")
                        else:
                            logger.info(f"策略6完成: 通过API验证确认未登录")
                        logger.info(f"检查的API: {', '.join([r['api_path'] for r in strategy6_results])}")
                    else:
                        logger.info("策略6失败: 无法通过API验证确定登录状态")
                            
                except Exception as e:
                    logger.debug(f"策略6出错: API验证时发生异常: {e}")
            else:
                if is_logged_in:
                    logger.info("策略6跳过: 已确认登录状态")
                else:
                    logger.info("策略6跳过: 已发现登录按钮，确认未登录状态")
            
            # Strategy 7: URL-based detection for some platforms
            # Strategy 7: URL-based detection for some platforms
            if not is_logged_in and not has_login_button:
                logger.debug("策略7: 基于URL的检测")
                try:
                    logger.debug(f"策略7: 当前URL: {current_url}")
                    
                    # Platform-specific URL patterns that indicate logged-in state
                    platform_logged_in_patterns = {
                        'xiaohongshu': ['/user/', '/explore', '/creator', '/note/', '/notes'],
                        'weibo': ['/home', '/profile/', '/u/', '/mygroups', '/messages'],
                        'douyin': ['/recommend', '/follow', '/user/', '/video/']
                    }
                    
                    # General URL patterns that indicate logged-in state
                    general_logged_in_patterns = [
                        '/home', '/dashboard', '/feed', '/timeline',
                        '/profile', '/settings', '/messages', '/notifications',
                        '/account', '/user/', '/my'
                    ]
                    
                    # URL patterns that indicate login/registration pages
                    login_url_patterns = [
                        '/login', '/signin', '/register', '/signup', '/auth',
                        '/passport', '/sso', '/oauth', '/welcome'
                    ]
                    
                    # Get platform-specific patterns
                    platform_patterns = platform_logged_in_patterns.get(platform, [])
                    all_logged_in_patterns = platform_patterns + general_logged_in_patterns
                    
                    logger.debug(f"策略7: 平台 {platform} 特定模式: {platform_patterns}")
                    logger.debug(f"策略7: 总共检查 {len(all_logged_in_patterns)} 个登录URL模式")
                    
                    # Check if current URL suggests logged-in state
                    url_lower = current_url.lower()
                    is_login_page = any(pattern in url_lower for pattern in login_url_patterns)
                    matched_login_patterns = [pattern for pattern in all_logged_in_patterns if pattern in url_lower]
                    
                    logger.debug(f"策略7: 是否为登录页面: {is_login_page}")
                    logger.debug(f"策略7: 匹配的登录状态URL模式: {matched_login_patterns}")
                    
                    if matched_login_patterns and not is_login_page:
                        # Calculate confidence based on pattern specificity
                        confidence = 60  # Base confidence
                        
                        # Higher confidence for platform-specific patterns
                        if any(pattern in platform_patterns for pattern in matched_login_patterns):
                            confidence = 75
                            logger.debug("策略7: 匹配到平台特定URL模式，提高置信度")
                        
                        # Higher confidence for more specific patterns
                        specific_patterns = ['/user/', '/profile/', '/account/', '/my']
                        if any(pattern in matched_login_patterns for pattern in specific_patterns):
                            confidence = min(confidence + 10, 85)
                            logger.debug("策略7: 匹配到特定URL模式，进一步提高置信度")
                        
                        is_logged_in = True
                        detection_method = f"url_pattern: {', '.join(matched_login_patterns)}"
                        detection_confidence = confidence
                        logger.info(f"策略7成功: 通过URL模式检测到登录 (URL: {current_url}, 模式: {matched_login_patterns}, 置信度: {confidence}%)")
                    elif is_login_page:
                        logger.info(f"策略7确认: 当前为登录页面，确认未登录 (URL: {current_url})")
                    else:
                        logger.info(f"策略7失败: URL未匹配任何登录状态模式 (URL: {current_url})")
                        
                except Exception as e:
                    logger.debug(f"策略7出错: URL检测时发生异常: {e}")
            else:
                if is_logged_in:
                    logger.info("策略7跳过: 已确认登录状态")
                else:
                    logger.info("策略7跳过: 已发现登录按钮，确认未登录状态")
            
            # Final validation and confidence adjustment
            if is_logged_in and detection_confidence < 40:
                detection_confidence = 40  # Minimum confidence for positive detection
            
            # Additional validation: if we detected login but confidence is very low, 
            # still accept it if we have meaningful indicators
            if (is_logged_in and detection_confidence < 60 and 
                (login_user and len(login_user.strip()) > 0)):
                detection_confidence = max(detection_confidence, 55)  # Boost confidence if we have user info
            
            # Log comprehensive detection result
            logger.info(f"登录检测结果 - 平台: {platform}, 已登录: {is_logged_in}, 方法: {detection_method}, 置信度: {detection_confidence}%, 用户: {login_user}")
            
            # Prepare enhanced login status result
            login_status_result = {
                "is_logged_in": is_logged_in,
                "login_user": login_user,
                "has_login_button": has_login_button,
                "current_url": current_url,
                "platform": platform,
                "detection_method": detection_method,
                "detection_confidence": detection_confidence,
                "timestamp": datetime.utcnow(),
                "instance_id": instance_id
            }
            
            # Sync login status across all tabs in this instance
            try:
                await self._sync_login_status_across_tabs(instance_id, login_status_result)
            except Exception as sync_error:
                logger.warning(f"同步登录状态失败: {sync_error}")
            
            # If user is logged in with reasonable confidence, save current session for future restoration
            if is_logged_in and detection_confidence >= 50:
                try:
                    logger.info(f"保存当前登录会话 (置信度: {detection_confidence}%)")
                    await self._save_current_login_session(instance_id, platform, page)
                except Exception as save_error:
                    logger.warning(f"保存登录会话失败: {save_error}")
            elif is_logged_in:
                logger.info(f"登录检测置信度较低 ({detection_confidence}%)，跳过会话保存")
            
            return login_status_result
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"检查实例 {instance_id} 登录状态失败: {e}\n{error_trace}")
            return {
                "is_logged_in": False, 
                "error": str(e),
                "detection_method": "error",
                "detection_confidence": 0,
                "timestamp": datetime.utcnow(),
                "instance_id": instance_id
            }
    
    async def _setup_page_listeners(self, instance_id: str, browser: BrowserContext, main_page: Page):
        """Setup event listeners for enhanced tab management"""
        try:
            # Initialize tab states for this instance
            self.tab_states[instance_id] = {}
            self.page_listeners[instance_id] = {}
            self.session_storage[instance_id] = {}
            
            # Listen for new page creation
            def on_page_created(page: Page):
                asyncio.create_task(self._handle_page_created(instance_id, page))
            
            browser.on("page", on_page_created)
            
            # Setup main page listeners
            await self._setup_single_page_listeners(instance_id, main_page, is_main=True)
            
            logger.info(f"Enhanced tab management setup completed for instance {instance_id}")
            
        except Exception as e:
            logger.error(f"Error setting up page listeners for {instance_id}: {e}")
    
    async def _sync_login_status_across_tabs(self, instance_id: str, login_status: dict):
        """Sync login status across all tabs in an instance"""
        try:
            if instance_id not in self.tab_states:
                return
            
            # Update login status for all tabs in this instance
            for page_id in self.tab_states[instance_id]:
                self.tab_states[instance_id][page_id]['login_status'] = login_status
            
            # Store in session storage for cross-tab access
            self.session_storage[instance_id]['login_status'] = login_status
            self.session_storage[instance_id]['last_login_check'] = datetime.utcnow().isoformat()
            
            # Sync to all active pages in the browser context
            if instance_id in self.browsers:
                browser = self.browsers[instance_id]
                try:
                    for page in browser.pages:
                        if not page.is_closed():
                            # Inject login status into page's sessionStorage
                            await page.evaluate(f"""
                            () => {{
                                try {{
                                    sessionStorage.setItem('__crawler_login_status', JSON.stringify({login_status}));
                                    sessionStorage.setItem('__crawler_last_check', '{datetime.utcnow().isoformat()}');
                                }} catch (e) {{
                                    console.warn('Failed to sync login status to sessionStorage:', e);
                                }}
                            }}
                            """)
                except Exception as e:
                    logger.debug(f"Error syncing login status to pages: {e}")
            
            logger.debug(f"Login status synced across all tabs for instance {instance_id}")
            
        except Exception as e:
             logger.error(f"Error syncing login status across tabs for {instance_id}: {e}")
    
    @log_async_function_call
    async def _restore_login_session(self, instance_id: str, session_id: str, platform: str, page: Page):
         """Restore previous login session when browser reopens"""
         try:
             logger.info(f"开始恢复登录会话 - 平台: {platform}, 会话ID: {session_id}, 实例ID: {instance_id}")
             
             # 1. Check for saved session data in database
             saved_session = await self.db.login_sessions.find_one({
                 "session_id": session_id,
                 "platform": platform,
                 "is_active": True
             })
             
             if saved_session:
                 logger.info(f"找到保存的会话数据 - 平台: {platform}, 保存时间: {saved_session.get('saved_at')}")
                 
                 # 2. Restore cookies if available
                 if "cookies" in saved_session and saved_session["cookies"]:
                     try:
                         # Filter valid cookies
                         valid_cookies = []
                         for cookie in saved_session["cookies"]:
                             if cookie.get('name') and cookie.get('value'):
                                 valid_cookies.append(cookie)
                         
                         if valid_cookies:
                             await page.context.add_cookies(valid_cookies)
                             logger.info(f"成功恢复 {len(valid_cookies)} 个cookies - 平台: {platform}")
                         else:
                             logger.warning(f"没有有效的cookies可恢复 - 平台: {platform}")
                     except Exception as cookie_error:
                         logger.error(f"恢复cookies失败 - 平台: {platform}, 错误: {cookie_error}")
                 
                 # 3. Restore localStorage data
                 if "local_storage" in saved_session and saved_session["local_storage"]:
                     try:
                         import json
                         local_storage_json = json.dumps(saved_session['local_storage'])
                         local_storage_script = f"""
                         () => {{
                             try {{
                                 const data = {local_storage_json};
                                 let restored = 0;
                                 for (const [key, value] of Object.entries(data)) {{
                                     try {{
                                         localStorage.setItem(key, value);
                                         restored++;
                                     }} catch (e) {{
                                         console.warn('Failed to restore localStorage item:', key, e);
                                     }}
                                 }}
                                 return restored;
                             }} catch (e) {{
                                 console.error('localStorage restoration error:', e);
                                 return 0;
                             }}
                         }}
                         """
                         restored_count = await page.evaluate(local_storage_script)
                         logger.info(f"成功恢复 {restored_count} 个localStorage项 - 平台: {platform}")
                     except Exception as storage_error:
                         logger.error(f"恢复localStorage失败 - 平台: {platform}, 错误: {storage_error}")
                 
                 # 4. Restore sessionStorage data
                 if "session_storage" in saved_session and saved_session["session_storage"]:
                     try:
                         import json
                         session_storage_json = json.dumps(saved_session['session_storage'])
                         session_storage_script = f"""
                         () => {{
                             try {{
                                 const data = {session_storage_json};
                                 let restored = 0;
                                 for (const [key, value] of Object.entries(data)) {{
                                     try {{
                                         sessionStorage.setItem(key, value);
                                         restored++;
                                     }} catch (e) {{
                                         console.warn('Failed to restore sessionStorage item:', key, e);
                                     }}
                                 }}
                                 return restored;
                             }} catch (e) {{
                                 console.error('sessionStorage restoration error:', e);
                                 return 0;
                             }}
                         }}
                         """
                         restored_count = await page.evaluate(session_storage_script)
                         logger.info(f"成功恢复 {restored_count} 个sessionStorage项 - 平台: {platform}")
                     except Exception as storage_error:
                         logger.error(f"恢复sessionStorage失败 - 平台: {platform}, 错误: {storage_error}")
                 
                 # 5. Navigate to the last known logged-in URL if available
                 if "last_url" in saved_session and saved_session["last_url"]:
                     try:
                         last_url = saved_session["last_url"]
                         # Clean URL again to ensure no invalid characters
                         cleaned_last_url = last_url.rstrip(',').rstrip().split('#')[0] if last_url else ""
                         
                         # Only navigate if it's not a login/register page
                         login_keywords = ['/login', '/signin', '/register', '/signup', '/auth', '/passport']
                         if cleaned_last_url and not any(keyword in cleaned_last_url.lower() for keyword in login_keywords):
                             logger.info(f"导航到最后已知URL: {cleaned_last_url}")
                             
                             # Retry navigation with different strategies
                             navigation_success = False
                             for attempt in range(3):
                                 try:
                                     if attempt == 0:
                                         # First attempt: standard navigation
                                         await page.goto(cleaned_last_url, wait_until="networkidle", timeout=15000)
                                     elif attempt == 1:
                                         # Second attempt: domcontentloaded
                                         await page.goto(cleaned_last_url, wait_until="domcontentloaded", timeout=10000)
                                     else:
                                         # Third attempt: load only
                                         await page.goto(cleaned_last_url, wait_until="load", timeout=8000)
                                     
                                     navigation_success = True
                                     logger.info(f"成功导航到: {cleaned_last_url} (尝试 {attempt + 1})")
                                     break
                                 except Exception as retry_error:
                                     logger.warning(f"导航尝试 {attempt + 1} 失败: {retry_error}")
                                     if attempt < 2:
                                         await asyncio.sleep(2)  # Wait before retry
                             
                             if not navigation_success:
                                 logger.error(f"所有导航尝试都失败，使用平台默认页面")
                                 # Fallback to platform default page
                                 platform_defaults = {
                                     'xiaohongshu': 'https://www.xiaohongshu.com/explore',
                                     'weibo': 'https://weibo.com',
                                     'douyin': 'https://www.douyin.com'
                                 }
                                 default_url = platform_defaults.get(platform)
                                 if default_url:
                                     try:
                                         await page.goto(default_url, wait_until="domcontentloaded", timeout=10000)
                                         logger.info(f"成功导航到默认页面: {default_url}")
                                     except Exception as default_error:
                                         logger.error(f"导航到默认页面也失败: {default_error}")
                         else:
                             logger.info(f"跳过无效或登录页面URL: {cleaned_last_url}")
                     except Exception as nav_error:
                         logger.error(f"导航处理失败 - URL: {last_url}, 错误: {nav_error}")
                 
                 # 6. Wait for page stabilization
                 await asyncio.sleep(3)
                 
                 # 7. Enhanced login status verification with multiple attempts
                 logger.info(f"验证登录状态恢复结果 - 平台: {platform}")
                 
                 # Multiple verification attempts with different strategies
                 login_verified = False
                 final_login_status = None
                 
                 for attempt in range(3):
                     try:
                         logger.info(f"登录状态验证尝试 {attempt + 1}/3 - 平台: {platform}")
                         
                         # Wait longer for page to stabilize on first attempt
                         if attempt == 0:
                             await asyncio.sleep(5)
                         elif attempt == 1:
                             await asyncio.sleep(3)
                         else:
                             await asyncio.sleep(2)
                         
                         # Ensure page is ready
                         try:
                             await page.wait_for_load_state("networkidle", timeout=8000)
                         except Exception:
                             logger.debug(f"页面加载状态等待超时 - 尝试 {attempt + 1}")
                         
                         # Check login status
                         login_status = await self.check_login_status(instance_id)
                         
                         if login_status.get("is_logged_in"):
                             # Additional verification: check if we have meaningful user info
                             login_user = login_status.get('login_user')
                             detection_confidence = login_status.get('detection_confidence', 0)
                             
                             logger.info(f"登录状态检测结果 - 尝试 {attempt + 1}: 已登录={login_status.get('is_logged_in')}, 用户={login_user}, 置信度={detection_confidence}")
                             
                             # Accept login with very lenient criteria for session restoration
                             # Since we're restoring a saved session, lower the bar significantly
                             detection_method = login_status.get('detection_method', '')
                              
                             # Accept if any of these conditions are met:
                             # 1. Reasonable confidence (>=40)
                             # 2. Any user info detected
                             # 3. Any positive detection method (not error)
                             # 4. Any cookie/storage/selector detection regardless of confidence
                             if (detection_confidence >= 40 or 
                                 (login_user and len(login_user.strip()) > 0) or
                                 (detection_confidence > 0 and detection_method and detection_method != 'error') or
                                 any(method in detection_method for method in ['cookie', 'storage', 'selector']) or
                                 login_status.get('is_logged_in') == True):
                                 
                                 login_verified = True
                                 final_login_status = login_status
                                 
                                 # Boost confidence for session restoration context if it's too low
                                 if detection_confidence < 50:
                                     final_login_status['detection_confidence'] = 60
                                     final_login_status['session_restoration_boost'] = True
                                     logger.info(f"🔧 提升会话恢复置信度: {detection_confidence} -> 60")
                                 
                                 logger.info(f"✅ 登录状态验证成功 - 尝试 {attempt + 1}, 平台: {platform}, 用户: {login_user}, 置信度: {final_login_status.get('detection_confidence')}")
                                 break
                             else:
                                 logger.warning(f"登录检测置信度较低 - 尝试 {attempt + 1}, 置信度: {detection_confidence}, 用户: {login_user}, 方法: {detection_method}")
                                 
                                 # Last resort: if this is the final attempt and we have ANY indication of login
                                 # (even with very low confidence), accept it for session restoration
                                 if attempt == 2 and (detection_confidence > 0 or login_user):
                                     logger.info(f"⚠️ 最后尝试：基于会话恢复上下文接受低置信度登录 - 置信度: {detection_confidence}")
                                     login_verified = True
                                     final_login_status = login_status
                                     final_login_status['detection_confidence'] = 50  # Set minimum acceptable confidence
                                     final_login_status['last_resort_acceptance'] = True
                                     break
                         else:
                             error_msg = login_status.get('error', 'unknown')
                             logger.warning(f"登录状态检测失败 - 尝试 {attempt + 1}, 错误: {error_msg}")
                         
                         # If not verified and not the last attempt, try refreshing the page
                         if not login_verified and attempt < 2:
                             try:
                                 logger.info(f"刷新页面后重试 - 尝试 {attempt + 1}")
                                 await page.reload(wait_until="domcontentloaded", timeout=10000)
                                 await asyncio.sleep(2)
                             except Exception as refresh_error:
                                 logger.warning(f"页面刷新失败: {refresh_error}")
                     
                     except Exception as verify_error:
                         logger.error(f"登录状态验证出错 - 尝试 {attempt + 1}: {verify_error}")
                         if attempt == 2:  # Last attempt
                             final_login_status = {"is_logged_in": False, "error": str(verify_error)}
                 
                 if login_verified and final_login_status and final_login_status.get("is_logged_in"):
                     logger.info(f"✅ 登录会话恢复成功 - 平台: {platform}, 用户: {final_login_status.get('login_user', 'unknown')}")
                     
                     # Update session data with current timestamp
                     await self.db.login_sessions.update_one(
                         {"session_id": session_id, "platform": platform},
                         {"$set": {
                             "last_restored": datetime.utcnow(),
                             "restore_count": saved_session.get("restore_count", 0) + 1,
                             "last_successful_restore": datetime.utcnow(),
                             "last_verification_confidence": final_login_status.get('detection_confidence', 0)
                         }}
                     )
                     
                     # Update browser instance with login info
                     await self.db.browser_instances.update_one(
                         {"instance_id": instance_id},
                         {"$set": {
                             "is_logged_in": True,
                             "login_user": final_login_status.get('login_user'),
                             "last_login_check": datetime.utcnow(),
                             "login_verification_confidence": final_login_status.get('detection_confidence', 0)
                         }}
                     )
                     
                     # Save current session state
                     await self._save_current_login_session(instance_id, platform, page)
                     
                     # Trigger auto crawl after successful login
                     await self._trigger_auto_crawl_after_login(instance_id, platform, session_id)
                     
                     return True
                 else:
                     # Login restoration failed after all attempts
                     logger.error(f"❌ 登录会话恢复失败 - 平台: {platform}, 所有验证尝试都失败")
                     return await self._handle_login_restore_failure(session_id, platform, saved_session)
             
             else:
                 # No saved session found
                 return await self._handle_no_saved_session(instance_id, platform, session_id, page)
         
         except Exception as e:
             logger.error(f"恢复登录会话时发生错误 - 平台: {platform}, 错误: {e}")
             import traceback
             logger.error(f"错误堆栈: {traceback.format_exc()}")
             return False
    
    @log_async_function_call
    async def _trigger_auto_crawl_after_login(self, instance_id: str, platform: str, session_id: str):
        """Trigger automatic crawling after successful login"""
        try:
            logger.info(f"🚀 触发自动爬取 - 平台: {platform}, 实例ID: {instance_id}, 会话ID: {session_id}")
            
            # Check if auto crawl is enabled for this platform
            instance_data = await self.db.browser_instances.find_one({"instance_id": instance_id})
            if not instance_data:
                logger.warning(f"未找到实例数据 - 实例ID: {instance_id}")
                return
            
            auto_crawl_enabled = instance_data.get("auto_crawl_enabled", True)
            if not auto_crawl_enabled:
                logger.info(f"自动爬取已禁用 - 平台: {platform}, 实例ID: {instance_id}")
                return
            
            # Import crawl service
            try:
                from .manual_crawl import ManualCrawlService
                # Initialize ManualCrawlService with required parameters
                crawl_service = ManualCrawlService(
                    db=self.db,
                    session_manager=self.session_manager,
                    browser_manager=self,
                    cookie_store=self.cookie_store
                )
                
                # Get platform default URL for auto crawl
                platform_defaults = {
                    'xiaohongshu': 'https://www.xiaohongshu.com/explore',
                    'weibo': 'https://weibo.com',
                    'douyin': 'https://www.douyin.com',
                    'bilibili': 'https://www.bilibili.com'
                }
                default_url = platform_defaults.get(platform, 'https://www.baidu.com')
                
                # Validate URL format
                if not default_url or not default_url.startswith(('http://', 'https://')):
                    logger.error(f"无效的默认URL - 平台: {platform}, URL: {default_url}")
                    default_url = 'https://www.baidu.com'  # 使用备用URL
                
                logger.info(f"为自动爬取任务设置URL - 平台: {platform}, URL: {default_url}")
                
                # Create auto crawl task
                crawl_task = {
                    "task_id": f"auto_{platform}_{session_id}_{int(datetime.utcnow().timestamp())}",
                    "platform": platform,
                    "instance_id": instance_id,
                    "session_id": session_id,
                    "task_type": "auto_crawl_after_login",
                    "url": default_url,  # 添加url字段
                    "created_at": datetime.utcnow(),
                    "status": "pending",
                    "auto_triggered": True,
                    "trigger_reason": "successful_login_restoration"
                }
                
                # Save crawl task to database
                await self.db.crawl_tasks.insert_one(crawl_task)
                logger.info(f"✅ 创建自动爬取任务 - 任务ID: {crawl_task['task_id']}, 平台: {platform}")
                
                # Execute crawl task asynchronously
                asyncio.create_task(self._execute_auto_crawl_task(crawl_task, crawl_service))
                
                # Update instance with last auto crawl info
                await self.db.browser_instances.update_one(
                    {"instance_id": instance_id},
                    {"$set": {
                        "last_auto_crawl_triggered": datetime.utcnow(),
                        "last_auto_crawl_task_id": crawl_task["task_id"]
                    }}
                )
                
            except ImportError as import_error:
                logger.error(f"导入爬取服务失败: {import_error}")
            except Exception as crawl_error:
                logger.error(f"创建爬取任务失败 - 平台: {platform}, 错误: {crawl_error}")
                
        except Exception as e:
            logger.error(f"触发自动爬取失败 - 平台: {platform}, 错误: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _execute_auto_crawl_task(self, crawl_task: dict, crawl_service):
        """Execute auto crawl task in background"""
        try:
            task_id = crawl_task["task_id"]
            platform = crawl_task["platform"]
            instance_id = crawl_task["instance_id"]
            
            logger.info(f"🔄 开始执行自动爬取任务 - 任务ID: {task_id}, 平台: {platform}")
            
            # Update task status to running
            await self.db.crawl_tasks.update_one(
                {"task_id": task_id},
                {"$set": {
                    "status": "running",
                    "started_at": datetime.utcnow()
                }}
            )
            
            # Wait a moment for login to stabilize
            await asyncio.sleep(5)
            
            # Get platform-specific crawl configuration
            crawl_config = self._get_platform_crawl_config(platform)
            
            # Execute the crawl
            result = await crawl_service.execute_crawl_task(task_id)
            
            # Update task status based on result
            if result and hasattr(result, 'status') and result.status == "completed":
                result_dict = result.dict() if hasattr(result, 'dict') else result
                await self.db.crawl_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "result": result_dict,
                        "items_crawled": 1 if result.content else 0
                    }}
                )
                logger.info(f"✅ 自动爬取任务完成 - 任务ID: {task_id}, 内容长度: {len(result.content) if result.content else 0}")
            else:
                error_msg = result.error_message if result and hasattr(result, 'error_message') and result.error_message else "Unknown error"
                result_dict = result.dict() if result and hasattr(result, 'dict') else None
                await self.db.crawl_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {
                        "status": "failed",
                        "completed_at": datetime.utcnow(),
                        "error": error_msg,
                        "result": result_dict
                    }}
                )
                logger.error(f"❌ 自动爬取任务失败 - 任务ID: {task_id}, 错误: {error_msg}")
                
        except Exception as e:
            logger.error(f"执行自动爬取任务时发生错误 - 任务ID: {crawl_task.get('task_id')}, 错误: {e}")
            
            # Update task status to failed
            await self.db.crawl_tasks.update_one(
                {"task_id": crawl_task.get("task_id")},
                {"$set": {
                    "status": "failed",
                    "completed_at": datetime.utcnow(),
                    "error": str(e)
                }}
            )
    
    def _get_platform_crawl_config(self, platform: str) -> dict:
        """Get platform-specific crawl configuration"""
        configs = {
            "weibo": {
                "max_pages": 3,
                "delay_between_pages": 2,
                "target_sections": ["timeline", "hot_topics"],
                "scroll_count": 5
            },
            "xiaohongshu": {
                "max_pages": 2,
                "delay_between_pages": 3,
                "target_sections": ["explore", "following"],
                "scroll_count": 3
            },
            "douyin": {
                "max_pages": 2,
                "delay_between_pages": 4,
                "target_sections": ["recommend", "following"],
                "scroll_count": 4
            },
            "default": {
                "max_pages": 2,
                "delay_between_pages": 3,
                "target_sections": ["main"],
                "scroll_count": 3
            }
        }
        
        return configs.get(platform, configs["default"])
    
    async def _handle_login_restore_failure(self, session_id: str, platform: str, saved_session: dict):
        """Handle login restoration failure"""
        logger.warning(f"❌ 登录会话恢复失败 - 平台: {platform}, 未检测到登录状态")
        
        # Mark session as potentially invalid
        await self.db.login_sessions.update_one(
            {"session_id": session_id, "platform": platform},
            {"$set": {
                "last_failed_restore": datetime.utcnow(),
                "failed_restore_count": saved_session.get("failed_restore_count", 0) + 1
            }}
        )
        return False
    
    async def _handle_no_saved_session(self, instance_id: str, platform: str, session_id: str, page: Page):
        """Handle case when no saved session is found"""
        logger.info(f"未找到保存的会话数据 - 平台: {platform}, 会话ID: {session_id}")
        
        # Try to detect if there's any existing login state in the user data directory
        detected = await self._detect_existing_login_state(instance_id, platform, page)
        return detected
    
    async def _detect_existing_login_state(self, instance_id: str, platform: str, page: Page):
         """Detect existing login state from browser's persistent data"""
         try:
             logger.info(f"Detecting existing login state for {platform}")
             
             # Wait for page to load
             await asyncio.sleep(1)
             
             # Check current cookies for login indicators
             cookies = await page.context.cookies()
             login_cookies = []
             
             login_cookie_patterns = [
                 'session', 'auth', 'token', 'login', 'user', 'uid', 'userid',
                 'sessionid', 'authtoken', 'access_token', 'logged_in', 'passport'
             ]
             
             for cookie in cookies:
                 if any(pattern in cookie['name'].lower() for pattern in login_cookie_patterns):
                     if cookie['value'] and len(cookie['value']) > 5:
                         login_cookies.append(cookie['name'])
             
             if login_cookies:
                 logger.info(f"Found existing login cookies for {platform}: {login_cookies}")
                 
                 # Save current state as a new session
                 await self._save_current_login_session(instance_id, platform, page)
             else:
                 logger.info(f"No existing login state detected for {platform}")
                 
         except Exception as e:
             logger.error(f"Error detecting existing login state for {platform}: {e}")
    
    async def _save_current_login_session(self, instance_id: str, platform: str, page: Page):
         """Save current login session data for future restoration"""
         try:
             # Get instance data to find session_id
             instance_data = await self.db.browser_instances.find_one({
                 "instance_id": instance_id,
                 "is_active": True
             })
             
             if not instance_data:
                 logger.warning(f"Cannot save session - instance data not found for {instance_id}")
                 return
             
             # Check if session_id exists and is valid
             session_id = instance_data.get("session_id")
             if not session_id:
                 logger.error(f"Cannot save session - session_id not found or empty in instance data for {instance_id}")
                 logger.debug(f"Instance data keys: {list(instance_data.keys()) if instance_data else 'None'}")
                 logger.debug(f"Full instance data: {instance_data}")
                 return
             
             # Get current cookies
             cookies = await page.context.cookies()
             
             # Get localStorage data
             local_storage = await page.evaluate("""
             () => {
                 const storage = {};
                 for (let i = 0; i < localStorage.length; i++) {
                     const key = localStorage.key(i);
                     const value = localStorage.getItem(key);
                     if (key && value) {
                         storage[key] = value;
                     }
                 }
                 return storage;
             }
             """)
             
             # Get sessionStorage data
             session_storage = await page.evaluate("""
             () => {
                 const storage = {};
                 for (let i = 0; i < sessionStorage.length; i++) {
                     const key = sessionStorage.key(i);
                     const value = sessionStorage.getItem(key);
                     if (key && value) {
                         storage[key] = value;
                     }
                 }
                 return storage;
             }
             """)
             
             # Clean and validate URL before saving
             current_url = page.url
             # Remove trailing commas, spaces, and other invalid characters
             cleaned_url = current_url.rstrip(',').rstrip().split('#')[0].split('?')[0] if current_url else ""
             
             # Validate URL format
             if cleaned_url and not cleaned_url.startswith(('http://', 'https://')):
                 logger.warning(f"Invalid URL format detected: {current_url}, using platform default")
                 # Use platform-specific default URLs
                 platform_defaults = {
                     'xiaohongshu': 'https://www.xiaohongshu.com/explore',
                     'weibo': 'https://weibo.com',
                     'douyin': 'https://www.douyin.com'
                 }
                 cleaned_url = platform_defaults.get(platform, cleaned_url)
             
             logger.info(f"保存会话URL - 原始: {current_url}, 清理后: {cleaned_url}")
             
             # Prepare session data
             session_data = {
                 "session_id": session_id,
                 "platform": platform,
                 "cookies": cookies,
                 "local_storage": local_storage,
                 "session_storage": session_storage,
                 "last_url": cleaned_url,
                 "saved_at": datetime.utcnow(),
                 "is_active": True,
                 "restore_count": 0
             }
             
             # Save or update session data
             await self.db.login_sessions.update_one(
                 {"session_id": session_id, "platform": platform},
                 {"$set": session_data},
                 upsert=True
             )
             
             logger.info(f"Saved login session data for {platform} (session: {session_id})")
             
         except Exception as e:
             logger.error(f"Error saving login session for {platform}: {e}")
    
    async def _manage_browser_sessions(self):
         """Browser-level session management with real-time notifications"""
         try:
             while True:
                 await asyncio.sleep(30)  # Check every 30 seconds
                 
                 # Get all active instances
                 active_instances = await self.db.browser_instances.find({
                     "is_active": True,
                     "expires_at": {"$gt": datetime.utcnow()}
                 }).to_list(None)
                 
                 for instance in active_instances:
                     instance_id = instance["instance_id"]
                     platform = instance["platform"]
                     
                     # Check if browser is still alive
                     if instance_id in self.browsers:
                         browser = self.browsers[instance_id]
                         try:
                             # Test browser connectivity
                             pages = browser.pages
                             if not pages or all(page.is_closed() for page in pages):
                                 logger.warning(f"Browser {instance_id} has no active pages, cleaning up")
                                 await self._cleanup_dead_browser(instance_id)
                                 continue
                             
                             # Check login status and send notifications if changed
                             current_status = await self.check_login_status(instance_id)
                             await self._check_and_notify_status_change(instance_id, platform, current_status)
                             
                         except Exception as browser_error:
                             logger.warning(f"Browser {instance_id} appears to be dead: {browser_error}")
                             await self._cleanup_dead_browser(instance_id)
                     else:
                         # Browser not in memory, mark as inactive
                         await self.db.browser_instances.update_one(
                             {"instance_id": instance_id},
                             {"$set": {"is_active": False, "ended_at": datetime.utcnow()}}
                         )
                 
         except Exception as e:
             logger.error(f"Error in browser session management: {e}")
    
    async def _cleanup_dead_browser(self, instance_id: str):
         """Clean up dead browser instances"""
         try:
             # Remove from memory
             if instance_id in self.browsers:
                 try:
                     await self.browsers[instance_id].close()
                 except:
                     pass
                 del self.browsers[instance_id]
             
             if instance_id in self.pages:
                 del self.pages[instance_id]
             
             if instance_id in self.tab_states:
                 del self.tab_states[instance_id]
             
             if instance_id in self.page_listeners:
                 del self.page_listeners[instance_id]
             
             if instance_id in self.session_storage:
                 del self.session_storage[instance_id]
             
             # Update database
             await self.db.browser_instances.update_one(
                 {"instance_id": instance_id},
                 {"$set": {"is_active": False, "ended_at": datetime.utcnow()}}
             )
             
             logger.info(f"Cleaned up dead browser instance: {instance_id}")
             
         except Exception as e:
             logger.error(f"Error cleaning up dead browser {instance_id}: {e}")
    
    async def _check_and_notify_status_change(self, instance_id: str, platform: str, current_status: dict):
         """Check for login status changes and send real-time notifications"""
         try:
             # Get previous status from database
             instance_data = await self.db.browser_instances.find_one({"instance_id": instance_id})
             if not instance_data:
                 return
             
             previous_status = instance_data.get("last_login_status", {})
             current_logged_in = current_status.get("is_logged_in", False)
             previous_logged_in = previous_status.get("is_logged_in", False)
             
             # Check if status changed
             if current_logged_in != previous_logged_in:
                 # Status changed, send notification
                 notification = {
                     "type": "login_status_change",
                     "instance_id": instance_id,
                     "platform": platform,
                     "previous_status": previous_logged_in,
                     "current_status": current_logged_in,
                     "timestamp": datetime.utcnow(),
                     "user": current_status.get("login_user", "unknown")
                 }
                 
                 # Save notification to database
                 await self.db.notifications.insert_one(notification)
                 
                 # Log the change
                 status_text = "logged in" if current_logged_in else "logged out"
                 logger.info(f"Login status changed for {platform} ({instance_id}): User {status_text}")
                 
                 # Update instance with new status
                 await self.db.browser_instances.update_one(
                     {"instance_id": instance_id},
                     {"$set": {
                         "last_login_status": current_status,
                         "last_status_check": datetime.utcnow()
                     }}
                 )
             
         except Exception as e:
             logger.error(f"Error checking status change for {instance_id}: {e}")
    
    async def get_multi_account_sessions(self, platform: str) -> list:
         """Get all active sessions for a platform (multi-account support)"""
         try:
             # Find all active sessions for the platform
             sessions = await self.db.login_sessions.find({
                 "platform": platform,
                 "is_active": True
             }).to_list(None)
             
             result = []
             for session in sessions:
                 # Get corresponding browser instance
                 instance = await self.db.browser_instances.find_one({
                     "session_id": session["session_id"],
                     "is_active": True
                 })
                 
                 if instance:
                     # Check current login status
                     current_status = await self.check_login_status(instance["instance_id"])
                     
                     result.append({
                         "session_id": session["session_id"],
                         "instance_id": instance["instance_id"],
                         "platform": platform,
                         "username": current_status.get("login_user", "unknown"),
                         "is_logged_in": current_status.get("is_logged_in", False),
                         "last_activity": instance.get("last_activity"),
                         "created_at": session.get("saved_at"),
                         "restore_count": session.get("restore_count", 0)
                     })
             
             return result
             
         except Exception as e:
             logger.error(f"Error getting multi-account sessions for {platform}: {e}")
             return []
    
    async def switch_account_session(self, platform: str, target_session_id: str) -> dict:
         """Switch to a different account session for the same platform"""
         try:
             # Find the target session
             target_session = await self.db.login_sessions.find_one({
                 "session_id": target_session_id,
                 "platform": platform,
                 "is_active": True
             })
             
             if not target_session:
                 return {"success": False, "error": "Target session not found"}
             
             # Create new browser instance with the target session
             new_instance = await self.create_browser_instance(
                 session_id=target_session_id,
                 platform=platform,
                 config=self.platform_configs.get(platform, {})
             )
             
             if new_instance["success"]:
                 logger.info(f"Successfully switched to account session {target_session_id} for {platform}")
                 return {
                     "success": True,
                     "instance_id": new_instance["instance_id"],
                     "session_id": target_session_id,
                     "platform": platform
                 }
             else:
                 return {"success": False, "error": new_instance.get("error", "Failed to create instance")}
             
         except Exception as e:
             logger.error(f"Error switching account session: {e}")
             return {"success": False, "error": str(e)}
    
    async def get_session_notifications(self, limit: int = 50) -> list:
         """Get recent session notifications"""
         try:
             notifications = await self.db.notifications.find().sort(
                 "timestamp", -1
             ).limit(limit).to_list(None)
             
             return notifications
             
         except Exception as e:
             logger.error(f"Error getting session notifications: {e}")
             return []
    
    async def _setup_single_page_listeners(self, instance_id: str, page: Page, is_main: bool = False):
        """Setup listeners for a single page"""
        try:
            page_id = f"{instance_id}_{page.url or 'unknown'}_{id(page)}"
            
            # Initialize page state
            self.tab_states[instance_id][page_id] = {
                "url": page.url,
                "title": await page.title() if page.url else "New Tab",
                "login_status": None,
                "last_activity": datetime.utcnow(),
                "is_main": is_main,
                "cookies": [],
                "local_storage": {},
                "session_storage": {}
            }
            
            # Listen for page events
            page.on("close", lambda: asyncio.create_task(self._handle_page_closed(instance_id, page_id)))
            page.on("load", lambda: asyncio.create_task(self._handle_page_loaded(instance_id, page_id, page)))
            page.on("domcontentloaded", lambda: asyncio.create_task(self._sync_page_state(instance_id, page_id, page)))
            page.on("framenavigated", lambda frame: asyncio.create_task(self._handle_page_navigation(instance_id, page_id, page, frame)))
            
            # Store page reference
            if page_id not in self.pages:
                self.pages[page_id] = page
            
            logger.debug(f"Page listeners setup for {page_id}")
            
        except Exception as e:
            logger.error(f"Error setting up single page listeners: {e}")
    
    async def _handle_page_navigation(self, instance_id: str, page_id: str, page: Page, frame):
        """Handle page navigation events and trigger auto-crawling for target pages"""
        import uuid
        import time
        
        # Generate unique navigation ID for tracking
        nav_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Initialize timing metrics
        timings = {
            'total_start': start_time,
            'target_check': 0,
            'stability_wait': 0,
            'login_check': 0,
            'crawl_decision': 0,
            'crawl_execution': 0
        }
        
        try:
            # Only handle main frame navigation
            if frame != page.main_frame:
                return
            
            current_url = frame.url
            logger.info(f"[NAV-{nav_id}] Page navigation started | Instance: {instance_id} | URL: {current_url}")
            
            # Get platform from instance data
            instance_data = await self.db.browser_instances.find_one({"instance_id": instance_id})
            if not instance_data:
                logger.warning(f"[NAV-{nav_id}] Instance data not found for {instance_id}")
                return
            
            platform = instance_data.get("platform", "unknown")
            session_id = instance_data.get("session_id")
            
            logger.info(f"[NAV-{nav_id}] Navigation context | Platform: {platform} | Session: {session_id}")
            
            # Check if URL is a target content page first (before expensive checks)
            target_check_start = time.time()
            is_target = await self._is_target_content_page(current_url, platform)
            timings['target_check'] = time.time() - target_check_start
            
            logger.info(f"[NAV-{nav_id}] Target page check | Result: {is_target} | Duration: {timings['target_check']:.3f}s")
            
            if not is_target:
                logger.debug(f"[NAV-{nav_id}] URL not a target content page, stopping continuous crawl: {current_url}")
                # Stop any existing continuous crawl if user navigated away from target page
                await self._stop_continuous_crawl_for_instance(instance_id)
                return
            
            # Wait for page stability before proceeding with crawl
            stability_start = time.time()
            is_stable = await self._wait_for_page_stability(page, current_url)
            timings['stability_wait'] = time.time() - stability_start
            
            logger.info(f"[NAV-{nav_id}] Page stability check | Result: {is_stable} | Duration: {timings['stability_wait']:.3f}s")
            
            if not is_stable:
                logger.warning(f"[NAV-{nav_id}] Page not stable after navigation, skipping crawl: {current_url}")
                return
            
            # Check if user is logged in after page is stable
            login_check_start = time.time()
            login_status = await self._check_login_status_for_navigation(instance_id, page_id, page, platform)
            timings['login_check'] = time.time() - login_check_start
            
            logger.info(f"[NAV-{nav_id}] Login status check | Result: {login_status} | Duration: {timings['login_check']:.3f}s")
            
            if not login_status:
                logger.debug(f"[NAV-{nav_id}] User not logged in for instance {instance_id}, skipping auto-crawl")
                return
            
            # Check for duplicate crawl prevention (user-initiated navigation)
            crawl_decision_start = time.time()
            should_crawl = await self._should_trigger_crawl(current_url, platform, "user")
            timings['crawl_decision'] = time.time() - crawl_decision_start
            
            logger.info(f"[NAV-{nav_id}] Crawl trigger decision | Result: {should_crawl} | Duration: {timings['crawl_decision']:.3f}s")
            
            if should_crawl:
                logger.info(f"[NAV-{nav_id}] Triggering real-time user-navigation crawl for target page: {current_url}")
                
                # Execute crawl task with immediate queue processing
                crawl_exec_start = time.time()
                crawl_result = await self._trigger_realtime_navigation_crawl(current_url, platform, session_id, instance_id, "user")
                timings['crawl_execution'] = time.time() - crawl_exec_start
                
                logger.info(f"[NAV-{nav_id}] Real-time crawl task execution | Success: {crawl_result if isinstance(crawl_result, bool) else crawl_result.get('success', False)} | Duration: {timings['crawl_execution']:.3f}s")
                
                # Start continuous crawl for this page
                continuous_start = time.time()
                await self._start_continuous_crawl_for_page(current_url, platform, session_id, instance_id, page)
                continuous_duration = time.time() - continuous_start
                
                logger.info(f"[NAV-{nav_id}] Continuous crawl setup | Duration: {continuous_duration:.3f}s")
            else:
                logger.debug(f"[NAV-{nav_id}] Skipping duplicate crawl for URL: {current_url}")
            
            # Log final summary
            total_duration = time.time() - start_time
            logger.info(f"[NAV-{nav_id}] Navigation processing completed | Total duration: {total_duration:.3f}s | "
                       f"Breakdown - Target: {timings['target_check']:.3f}s, Stability: {timings['stability_wait']:.3f}s, "
                       f"Login: {timings['login_check']:.3f}s, Decision: {timings['crawl_decision']:.3f}s, "
                       f"Execution: {timings['crawl_execution']:.3f}s")
                
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[NAV-{nav_id}] Error handling page navigation | Duration: {total_duration:.3f}s | Error: {e}", exc_info=True)
    
    async def _start_continuous_crawl_for_page(self, url: str, platform: str, session_id: str, instance_id: str, page: Page):
        """Start continuous crawl for a target page"""
        import uuid
        import time
        
        # Generate unique continuous crawl ID for tracking
        continuous_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"[CONTINUOUS-{continuous_id}] Starting continuous crawl | "
                   f"URL: {url} | Platform: {platform} | Instance: {instance_id} | "
                   f"Session: {session_id}")
        
        try:
            # Create continuous crawl configuration
            config_creation_start = time.time()
            config = {
                "crawl_interval": 30,  # 30 seconds interval
                "max_crawls": 100,  # Maximum number of crawls
                "content_change_threshold": 0.1,  # 10% content change threshold
                "max_duration": 3600,  # 1 hour maximum duration
                "stop_on_navigation": True,  # Stop when user navigates away
                "require_login": True  # Require user to be logged in
            }
            config_creation_duration = time.time() - config_creation_start
            
            logger.debug(f"[CONTINUOUS-{continuous_id}] Configuration created | "
                        f"Interval: {config['crawl_interval']}s | Max crawls: {config['max_crawls']} | "
                        f"Duration: {config_creation_duration:.3f}s")
            
            # Start continuous crawl task
            task_start_time = time.time()
            task_result = await self.continuous_crawl_service.start_continuous_crawl(
                url=url,
                platform=platform,
                session_id=session_id,
                instance_id=instance_id,
                config=config
            )
            task_duration = time.time() - task_start_time
            
            if task_result and task_result.get("success"):
                task_id = task_result.get("task_id")
                total_duration = time.time() - start_time
                
                logger.info(f"[CONTINUOUS-{continuous_id}] Continuous crawl task started successfully | "
                           f"Task ID: {task_id} | Task creation: {task_duration:.3f}s | "
                           f"Total: {total_duration:.3f}s | Config: interval={config['crawl_interval']}s, "
                           f"max_crawls={config['max_crawls']}, max_duration={config['max_duration']}s")
            else:
                error_msg = task_result.get('error', 'Unknown error') if task_result else 'No task result'
                total_duration = time.time() - start_time
                
                logger.warning(f"[CONTINUOUS-{continuous_id}] Failed to start continuous crawl | "
                              f"Instance: {instance_id} | Task creation: {task_duration:.3f}s | "
                              f"Total: {total_duration:.3f}s | Error: {error_msg} | "
                              f"Task result: {task_result}")
                
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[CONTINUOUS-{continuous_id}] Exception in continuous crawl startup | "
                        f"Duration: {total_duration:.3f}s | Error: {e}", exc_info=True)
    
    async def _stop_continuous_crawl_for_instance(self, instance_id: str):
        """Stop any existing continuous crawl for an instance"""
        import uuid
        import time
        
        # Generate unique stop operation ID for tracking
        stop_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"[STOP-{stop_id}] Stopping continuous crawl tasks | Instance: {instance_id}")
        
        try:
            # Get all continuous tasks for this instance
            list_start_time = time.time()
            # Note: list_continuous_tasks doesn't support filters parameter
            # We need to get all tasks and filter them manually
            all_tasks = await self.continuous_crawl_service.list_continuous_tasks(
                user_id="system",  # Use system user for instance-level operations
                status=self.ContinuousTaskStatus.RUNNING,
                limit=1000  # Get a large number to ensure we get all running tasks
            )
            
            # Filter tasks by instance_id manually
            tasks = []
            if all_tasks:
                for task in all_tasks:
                    # Check if task belongs to this instance
                    task_instance_id = task.get("instance_id")
                    if task_instance_id == instance_id:
                        tasks.append(task)
            
            list_duration = time.time() - list_start_time
            
            task_count = len(tasks) if tasks else 0
            logger.debug(f"[STOP-{stop_id}] Found {task_count} running continuous tasks | "
                        f"List duration: {list_duration:.3f}s")
            
            if not tasks:
                total_duration = time.time() - start_time
                logger.info(f"[STOP-{stop_id}] No running continuous tasks found | "
                           f"Total: {total_duration:.3f}s")
                return
            
            stopped_count = 0
            failed_count = 0
            
            for i, task in enumerate(tasks, 1):
                task_id = task.get("task_id")
                if task_id:
                    task_stop_start = time.time()
                    result = await self.continuous_crawl_service.stop_continuous_crawl(task_id)
                    task_stop_duration = time.time() - task_stop_start
                    
                    if result and result.get("success"):
                        stopped_count += 1
                        logger.info(f"[STOP-{stop_id}] Stopped continuous crawl task ({i}/{task_count}) | "
                                   f"Task ID: {task_id} | Duration: {task_stop_duration:.3f}s")
                    else:
                        failed_count += 1
                        error_msg = result.get('error', 'Unknown error') if result else 'No result'
                        logger.warning(f"[STOP-{stop_id}] Failed to stop continuous crawl task ({i}/{task_count}) | "
                                      f"Task ID: {task_id} | Duration: {task_stop_duration:.3f}s | "
                                      f"Error: {error_msg}")
                else:
                    failed_count += 1
                    logger.warning(f"[STOP-{stop_id}] Task ({i}/{task_count}) has no task_id | Task: {task}")
            
            total_duration = time.time() - start_time
            logger.info(f"[STOP-{stop_id}] Continuous crawl stop operation completed | "
                       f"Instance: {instance_id} | Total tasks: {task_count} | "
                       f"Stopped: {stopped_count} | Failed: {failed_count} | "
                       f"Total duration: {total_duration:.3f}s")
                        
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[STOP-{stop_id}] Exception stopping continuous crawl | "
                        f"Instance: {instance_id} | Duration: {total_duration:.3f}s | "
                        f"Error: {e}", exc_info=True)
    
    async def _is_target_content_page(self, url: str, platform: str, page: Page = None) -> bool:
        """Enhanced intelligent check if URL is a target content page that should trigger crawling
        
        Features:
        - Real-time URL comparison and pattern matching
        - Multi-phase analysis with confidence scoring
        - Platform-specific content detection
        - Dynamic page content analysis
        - Intelligent filtering to avoid non-content pages
        
        Args:
            url: The URL to check
            platform: The platform name
            page: Optional Playwright page object for dynamic content analysis
        """
        import uuid
        import time
        import hashlib
        
        # Generate unique check ID for tracking
        check_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"[CONTENT-{check_id}] Starting enhanced intelligent content page detection | "
                   f"Platform: {platform} | URL: {url[:100]}{'...' if len(url) > 100 else ''}")
        
        try:
            if not url:
                logger.debug(f"[CONTENT-{check_id}] Empty URL provided")
                return False
            
            # Normalize URL for better matching
            url_lower = url.lower().strip()
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            
            # Quick blacklist check for known non-content patterns
            if await self._is_blacklisted_url(url, platform, check_id):
                logger.info(f"[CONTENT-{check_id}] URL blacklisted, skipping analysis")
                return False
            
            # Real-time URL comparison with recent crawls
            if await self._check_recent_url_analysis(url_hash, check_id):
                logger.debug(f"[CONTENT-{check_id}] Using cached URL analysis result")
                return await self._get_cached_url_result(url_hash)
            
            # Phase 1: Enhanced URL pattern matching with confidence scoring
            pattern_start = time.time()
            pattern_result, pattern_confidence = await self._analyze_url_patterns(url, platform, check_id)
            pattern_duration = time.time() - pattern_start
            
            logger.debug(f"[CONTENT-{check_id}] URL pattern analysis | "
                        f"Result: {pattern_result} | Confidence: {pattern_confidence:.2f} | "
                        f"Duration: {pattern_duration:.3f}s")
            
            # Phase 2: URL structure intelligence analysis
            structure_start = time.time()
            structure_result, structure_confidence = await self._analyze_url_structure(url, platform, check_id)
            structure_duration = time.time() - structure_start
            
            logger.debug(f"[CONTENT-{check_id}] URL structure analysis | "
                        f"Result: {structure_result} | Confidence: {structure_confidence:.2f} | "
                        f"Duration: {structure_duration:.3f}s")
            
            # Phase 3: Dynamic page content analysis (if page object available)
            content_result, content_confidence = False, 0.0
            content_duration = 0.0
            
            if page:
                content_start = time.time()
                content_result, content_confidence = await self._analyze_page_content(page, url, platform, check_id)
                content_duration = time.time() - content_start
                
                logger.debug(f"[CONTENT-{check_id}] Page content analysis | "
                            f"Result: {content_result} | Confidence: {content_confidence:.2f} | "
                            f"Duration: {content_duration:.3f}s")
            
            # Phase 4: Intelligent decision making with weighted scoring
            decision_start = time.time()
            final_decision, final_confidence = await self._make_intelligent_decision(
                pattern_result, pattern_confidence,
                structure_result, structure_confidence,
                content_result, content_confidence,
                platform, check_id
            )
            decision_duration = time.time() - decision_start
            
            # Cache the analysis result for future use
            await self._cache_url_analysis(url_hash, final_decision, final_confidence)
            
            total_duration = time.time() - start_time
            
            logger.info(f"[CONTENT-{check_id}] Enhanced intelligent content page detection completed | "
                       f"Decision: {final_decision} | Confidence: {final_confidence:.2f} | "
                       f"Pattern: {pattern_duration:.3f}s | Structure: {structure_duration:.3f}s | "
                       f"Content: {content_duration:.3f}s | Decision: {decision_duration:.3f}s | "
                       f"Total: {total_duration:.3f}s | Hash: {url_hash}")
            
            return final_decision
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[CONTENT-{check_id}] Exception in enhanced intelligent content page detection | "
                        f"Platform: {platform} | Duration: {total_duration:.3f}s | "
                        f"Error: {e} | URL: {url[:100]}{'...' if len(url) > 100 else ''}", exc_info=True)
            return False
    
    async def _analyze_url_patterns(self, url: str, platform: str, check_id: str) -> tuple[bool, float]:
        """Enhanced URL pattern analysis with confidence scoring
        
        Returns:
            tuple: (is_match, confidence_score)
        """
        import re
        
        try:
            # Enhanced platform-specific URL patterns with confidence weights
            target_patterns = {
                "xiaohongshu": [
                    (r"https?://www\.xiaohongshu\.com/explore/[a-f0-9]{24}", 0.95),  # 笔记详情页（精确ID长度）
                    (r"https?://www\.xiaohongshu\.com/explore/[a-f0-9]+", 0.90),  # 笔记详情页
                    (r"https?://www\.xiaohongshu\.com/discovery/item/[a-f0-9]+", 0.85),  # 发现页面
                    (r"https?://www\.xiaohongshu\.com/user/profile/[a-f0-9]+", 0.80),  # 用户主页
                    (r"https?://xhslink\.com/[A-Za-z0-9]+", 0.75),  # 短链接
                    (r"https?://www\.xiaohongshu\.com/search_result\?.*keyword=.+", 0.70),  # 搜索结果页
                ],
                "weibo": [
                    (r"https?://weibo\.com/\d+/[A-Za-z0-9]{9,}", 0.95),  # 微博详情页（长ID）
                    (r"https?://m\.weibo\.cn/detail/[A-Za-z0-9]{9,}", 0.95),  # 手机版详情页
                    (r"https?://weibo\.com/u/\d+\?.*", 0.85),  # 用户主页（带参数）
                    (r"https?://weibo\.com/u/\d+", 0.80),  # 用户主页
                    (r"https?://weibo\.com/[A-Za-z0-9_]{3,}", 0.75),  # 用户主页（用户名）
                    (r"https?://m\.weibo\.cn/u/\d+", 0.80),  # 手机版用户主页
                    (r"https?://weibo\.com/status/[A-Za-z0-9]+", 0.90),  # 状态页面
                    (r"https?://weibo\.cn/[A-Za-z0-9]+", 0.70),  # 短域名
                ],
                "douyin": [
                    (r"https?://www\.douyin\.com/video/\d{19}", 0.95),  # 视频详情页（19位ID）
                    (r"https?://www\.douyin\.com/video/\d+", 0.90),  # 视频详情页
                    (r"https?://www\.douyin\.com/user/[^/?]+(?:\?.*)?$", 0.85),  # 用户主页（带参数检测）
                    (r"https?://www\.iesdouyin\.com/share/video/\d+", 0.90),  # 分享链接
                    (r"https?://v\.douyin\.com/[A-Za-z0-9]{7,}", 0.85),  # 短链接
                    (r"https?://www\.douyin\.com/search/[^/?]+", 0.75),  # 搜索结果
                    (r"https?://www\.douyin\.com/discover(?:\?.*)?$", 0.70),  # 发现页面
                ],
                "bilibili": [
                    (r"https?://www\.bilibili\.com/video/[Bb][Vv][A-Za-z0-9]{10}", 0.95),  # BV号视频
                    (r"https?://www\.bilibili\.com/video/av\d+", 0.90),  # AV号视频
                    (r"https?://space\.bilibili\.com/\d+(?:/.*)?$", 0.85),  # 用户空间
                    (r"https?://www\.bilibili\.com/read/cv\d+", 0.90),  # 专栏文章
                    (r"https?://live\.bilibili\.com/\d+", 0.85),  # 直播间
                    (r"https?://www\.bilibili\.com/bangumi/play/[^/?]+", 0.80),  # 番剧
                    (r"https?://b23\.tv/[A-Za-z0-9]{7,}", 0.85),  # 短链接
                    (r"https?://www\.bilibili\.com/search\?.*keyword=.+", 0.70),  # 搜索结果
                ],
                "zhihu": [
                    (r"https?://www\.zhihu\.com/question/\d+(?:/answer/\d+)?", 0.95),  # 问题页面（含回答）
                    (r"https?://zhuanlan\.zhihu\.com/p/\d+", 0.95),  # 专栏文章
                    (r"https?://www\.zhihu\.com/people/[^/?]+(?:/.*)?$", 0.80),  # 用户主页
                    (r"https?://www\.zhihu\.com/answer/\d+", 0.90),  # 回答页面
                    (r"https?://www\.zhihu\.com/column/[^/?]+", 0.75),  # 专栏主页
                    (r"https?://www\.zhihu\.com/search\?.*q=.+", 0.70),  # 搜索结果
                    (r"https?://www\.zhihu\.com/topic/\d+", 0.75),  # 话题页面
                ],
                "tiktok": [
                    (r"https?://www\.tiktok\.com/@[^/?]+/video/\d{19}", 0.95),  # 视频页面（19位ID）
                    (r"https?://www\.tiktok\.com/@[^/?]+/video/\d+", 0.90),  # 视频页面
                    (r"https?://www\.tiktok\.com/@[^/?]+(?:\?.*)?$", 0.80),  # 用户主页
                    (r"https?://vm\.tiktok\.com/[A-Za-z0-9]{9,}", 0.85),  # 短链接
                    (r"https?://www\.tiktok\.com/search\?.*q=.+", 0.70),  # 搜索结果
                ],
                "youtube": [
                    (r"https?://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}", 0.95),  # 视频页面（11位ID）
                    (r"https?://youtu\.be/[A-Za-z0-9_-]{11}", 0.95),  # 短链接
                    (r"https?://www\.youtube\.com/channel/[^/?]+", 0.80),  # 频道页面
                    (r"https?://www\.youtube\.com/c/[^/?]+", 0.80),  # 频道页面
                    (r"https?://www\.youtube\.com/@[^/?]+", 0.85),  # 新版频道页面
                    (r"https?://www\.youtube\.com/results\?.*search_query=.+", 0.70),  # 搜索结果
                ],
                "twitter": [
                    (r"https?://(?:twitter|x)\.com/[^/?]+/status/\d{19}", 0.95),  # 推文页面（19位ID）
                    (r"https?://(?:twitter|x)\.com/[^/?]+/status/\d+", 0.90),  # 推文页面
                    (r"https?://(?:twitter|x)\.com/[^/?]+(?:\?.*)?$", 0.75),  # 用户主页
                    (r"https?://(?:twitter|x)\.com/search\?.*q=.+", 0.70),  # 搜索结果
                ],
                "instagram": [
                    (r"https?://www\.instagram\.com/p/[A-Za-z0-9_-]{11}", 0.95),  # 帖子页面（11位ID）
                    (r"https?://www\.instagram\.com/p/[A-Za-z0-9_-]+", 0.90),  # 帖子页面
                    (r"https?://www\.instagram\.com/[^/?]+(?:\?.*)?$", 0.75),  # 用户主页
                    (r"https?://www\.instagram\.com/stories/[^/?]+", 0.85),  # 故事页面
                    (r"https?://www\.instagram\.com/explore(?:/.*)?$", 0.70),  # 探索页面
                ]
            }
            
            patterns = target_patterns.get(platform, [])
            max_confidence = 0.0
            matched = False
            matched_pattern = None
            
            # Check platform-specific patterns
            for pattern, confidence in patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    if confidence > max_confidence:
                        max_confidence = confidence
                        matched = True
                        matched_pattern = pattern
            
            # If no platform-specific match, try generic content patterns
            if not matched:
                generic_patterns = [
                    (r"https?://[^/]+/[^/]+/\d{10,}", 0.60),  # 长数字ID模式
                    (r"https?://[^/]+/[^/]+/\d+", 0.50),  # 通用数字ID模式
                    (r"https?://[^/]+/post/[^/?]+", 0.55),  # 通用post模式
                    (r"https?://[^/]+/article/[^/?]+", 0.55),  # 通用article模式
                    (r"https?://[^/]+/content/[^/?]+", 0.50),  # 通用content模式
                    (r"https?://[^/]+/[^/]+/[A-Za-z0-9]{8,}", 0.45),  # 长字符串ID模式
                ]
                
                for pattern, confidence in generic_patterns:
                    if re.match(pattern, url, re.IGNORECASE):
                        if confidence > max_confidence:
                            max_confidence = confidence
                            matched = True
                            matched_pattern = pattern
            
            # Check for homepage/index patterns (negative indicators)
            negative_patterns = [
                (r"https?://[^/]+/?$", -0.8),  # 根域名
                (r"https?://[^/]+/index(?:\.\w+)?(?:\?.*)?$", -0.7),  # index页面
                (r"https?://[^/]+/home(?:\?.*)?$", -0.6),  # home页面
                (r"https?://[^/]+/#.*$", -0.5),  # 锚点首页
                (r"https?://[^/]+/login(?:\?.*)?$", -0.9),  # 登录页面
                (r"https?://[^/]+/register(?:\?.*)?$", -0.9),  # 注册页面
            ]
            
            for pattern, penalty in negative_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    max_confidence += penalty
                    logger.debug(f"[CONTENT-{check_id}] Negative pattern matched: {pattern} | Penalty: {penalty}")
            
            # Ensure confidence is within valid range
            max_confidence = max(0.0, min(1.0, max_confidence))
            
            if matched and matched_pattern:
                logger.debug(f"[CONTENT-{check_id}] URL pattern matched | Pattern: {matched_pattern[:50]}... | Confidence: {max_confidence:.2f}")
            else:
                logger.debug(f"[CONTENT-{check_id}] No URL pattern matched | Final confidence: {max_confidence:.2f}")
            
            return matched and max_confidence > 0.3, max_confidence
            
        except Exception as e:
             logger.error(f"[CONTENT-{check_id}] Error in URL pattern analysis: {e}", exc_info=True)
             return False, 0.0
    
    async def _is_blacklisted_url(self, url: str, platform: str, check_id: str) -> bool:
        """Check if URL matches known non-content patterns that should be avoided
        
        Args:
            url: The URL to check
            platform: The platform name
            check_id: Unique check identifier
            
        Returns:
            bool: True if URL should be blacklisted
        """
        import re
        
        try:
            url_lower = url.lower()
            
            # Universal blacklist patterns
            universal_blacklist = [
                r'https?://[^/]+/?$',  # Root domain
                r'https?://[^/]+/index(?:\.[^/?]+)?(?:\?.*)?$',  # Index pages
                r'https?://[^/]+/home(?:\?.*)?$',  # Home pages
                r'https?://[^/]+/login(?:\?.*)?$',  # Login pages
                r'https?://[^/]+/register(?:\?.*)?$',  # Register pages
                r'https?://[^/]+/signup(?:\?.*)?$',  # Signup pages
                r'https?://[^/]+/about(?:\?.*)?$',  # About pages
                r'https?://[^/]+/contact(?:\?.*)?$',  # Contact pages
                r'https?://[^/]+/help(?:\?.*)?$',  # Help pages
                r'https?://[^/]+/terms(?:\?.*)?$',  # Terms pages
                r'https?://[^/]+/privacy(?:\?.*)?$',  # Privacy pages
                r'https?://[^/]+/policy(?:\?.*)?$',  # Policy pages
                r'https?://[^/]+/search(?:\?.*)?$',  # Search pages without query
                r'https?://[^/]+/404(?:\?.*)?$',  # Error pages
                r'https?://[^/]+/error(?:\?.*)?$',  # Error pages
            ]
            
            # Platform-specific blacklist patterns
            platform_blacklist = {
                "xiaohongshu": [
                    r'https?://www\.xiaohongshu\.com/?$',  # Homepage
                    r'https?://www\.xiaohongshu\.com/explore/?$',  # Explore homepage
                    r'https?://www\.xiaohongshu\.com/search_result\?keyword=\s*$',  # Empty search
                ],
                "weibo": [
                    r'https?://weibo\.com/?$',  # Homepage
                    r'https?://m\.weibo\.cn/?$',  # Mobile homepage
                    r'https?://weibo\.com/hot(?:\?.*)?$',  # Hot topics
                    r'https?://weibo\.com/search(?:\?.*)?$',  # Search without query
                ],
                "douyin": [
                    r'https?://www\.douyin\.com/?$',  # Homepage
                    r'https?://www\.douyin\.com/discover/?$',  # Discover homepage
                    r'https?://www\.douyin\.com/search/?$',  # Search without query
                ],
                "bilibili": [
                    r'https?://www\.bilibili\.com/?$',  # Homepage
                    r'https?://www\.bilibili\.com/index\.html$',  # Index page
                    r'https?://www\.bilibili\.com/search(?:\?.*)?$',  # Search without query
                ],
                "zhihu": [
                    r'https?://www\.zhihu\.com/?$',  # Homepage
                    r'https?://www\.zhihu\.com/explore(?:\?.*)?$',  # Explore page
                    r'https?://www\.zhihu\.com/search(?:\?.*)?$',  # Search without query
                ]
            }
            
            # Check universal blacklist
            for pattern in universal_blacklist:
                if re.match(pattern, url, re.IGNORECASE):
                    logger.debug(f"[CONTENT-{check_id}] URL matched universal blacklist: {pattern}")
                    return True
            
            # Check platform-specific blacklist
            if platform in platform_blacklist:
                for pattern in platform_blacklist[platform]:
                    if re.match(pattern, url, re.IGNORECASE):
                        logger.debug(f"[CONTENT-{check_id}] URL matched {platform} blacklist: {pattern}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"[CONTENT-{check_id}] Error in blacklist check: {e}", exc_info=True)
            return False
    
    async def _check_recent_url_analysis(self, url_hash: str, check_id: str) -> bool:
        """Check if URL analysis result is cached and still valid
        
        Args:
            url_hash: MD5 hash of the URL
            check_id: Unique check identifier
            
        Returns:
            bool: True if cached result exists and is valid
        """
        try:
            # Simple in-memory cache with TTL (5 minutes)
            if not hasattr(self, '_url_analysis_cache'):
                self._url_analysis_cache = {}
            
            import time
            current_time = time.time()
            cache_ttl = 300  # 5 minutes
            
            if url_hash in self._url_analysis_cache:
                cached_data = self._url_analysis_cache[url_hash]
                if current_time - cached_data['timestamp'] < cache_ttl:
                    logger.debug(f"[CONTENT-{check_id}] Found valid cached result for URL hash: {url_hash}")
                    return True
                else:
                    # Remove expired cache entry
                    del self._url_analysis_cache[url_hash]
                    logger.debug(f"[CONTENT-{check_id}] Expired cache entry removed for URL hash: {url_hash}")
            
            return False
            
        except Exception as e:
            logger.error(f"[CONTENT-{check_id}] Error checking cached URL analysis: {e}", exc_info=True)
            return False
    
    async def _get_cached_url_result(self, url_hash: str) -> bool:
        """Get cached URL analysis result
        
        Args:
            url_hash: MD5 hash of the URL
            
        Returns:
            bool: Cached analysis result
        """
        try:
            if hasattr(self, '_url_analysis_cache') and url_hash in self._url_analysis_cache:
                return self._url_analysis_cache[url_hash]['result']
            return False
        except Exception as e:
            logger.error(f"Error getting cached URL result: {e}", exc_info=True)
            return False
    
    async def _cache_url_analysis(self, url_hash: str, result: bool, confidence: float) -> None:
        """Cache URL analysis result
        
        Args:
            url_hash: MD5 hash of the URL
            result: Analysis result
            confidence: Confidence score
        """
        try:
            if not hasattr(self, '_url_analysis_cache'):
                self._url_analysis_cache = {}
            
            import time
            self._url_analysis_cache[url_hash] = {
                'result': result,
                'confidence': confidence,
                'timestamp': time.time()
            }
            
            # Clean up old cache entries (keep only last 100)
            if len(self._url_analysis_cache) > 100:
                # Remove oldest entries
                sorted_items = sorted(self._url_analysis_cache.items(), 
                                    key=lambda x: x[1]['timestamp'])
                for old_hash, _ in sorted_items[:-80]:  # Keep 80 most recent
                    del self._url_analysis_cache[old_hash]
                    
        except Exception as e:
            logger.error(f"Error caching URL analysis: {e}", exc_info=True)
    
    async def _make_intelligent_decision(self, pattern_result: bool, pattern_confidence: float,
                                       structure_result: bool, structure_confidence: float,
                                       content_result: bool, content_confidence: float,
                                       platform: str, check_id: str) -> tuple[bool, float]:
        """Make intelligent decision based on multi-phase analysis results
        
        Args:
            pattern_result: URL pattern analysis result
            pattern_confidence: URL pattern confidence score
            structure_result: URL structure analysis result
            structure_confidence: URL structure confidence score
            content_result: Page content analysis result
            content_confidence: Page content confidence score
            platform: Platform name
            check_id: Unique check identifier
            
        Returns:
            tuple: (final_decision, final_confidence)
        """
        try:
            # Weighted scoring system
            weights = {
                'pattern': 0.4,    # URL pattern matching is most reliable
                'structure': 0.35, # URL structure analysis is second
                'content': 0.25    # Page content analysis (if available)
            }
            
            # Calculate weighted confidence score
            total_confidence = (
                pattern_confidence * weights['pattern'] +
                structure_confidence * weights['structure'] +
                content_confidence * weights['content']
            )
            
            # Adjust weights if content analysis is not available
            if content_confidence == 0.0:
                # Redistribute content weight to pattern and structure
                adjusted_pattern_weight = weights['pattern'] + (weights['content'] * 0.6)
                adjusted_structure_weight = weights['structure'] + (weights['content'] * 0.4)
                
                total_confidence = (
                    pattern_confidence * adjusted_pattern_weight +
                    structure_confidence * adjusted_structure_weight
                )
            
            # Platform-specific confidence adjustments
            platform_adjustments = {
                "xiaohongshu": 0.05,  # Slightly boost for xiaohongshu
                "weibo": 0.03,        # Small boost for weibo
                "douyin": 0.04,       # Small boost for douyin
                "bilibili": 0.03,     # Small boost for bilibili
            }
            
            if platform in platform_adjustments:
                total_confidence += platform_adjustments[platform]
            
            # Ensure confidence is within valid range
            total_confidence = max(0.0, min(1.0, total_confidence))
            
            # Decision thresholds
            high_confidence_threshold = 0.75
            medium_confidence_threshold = 0.50
            low_confidence_threshold = 0.30
            
            # Make final decision
            if total_confidence >= high_confidence_threshold:
                final_decision = True
                decision_reason = "high_confidence"
            elif total_confidence >= medium_confidence_threshold:
                # Require at least one positive result for medium confidence
                final_decision = pattern_result or structure_result or content_result
                decision_reason = "medium_confidence_with_positive_result"
            elif total_confidence >= low_confidence_threshold:
                # Require at least two positive results for low confidence
                positive_count = sum([pattern_result, structure_result, content_result])
                final_decision = positive_count >= 2
                decision_reason = "low_confidence_with_multiple_positive"
            else:
                final_decision = False
                decision_reason = "insufficient_confidence"
            
            logger.debug(f"[CONTENT-{check_id}] Intelligent decision | "
                        f"Pattern: {pattern_result}({pattern_confidence:.2f}) | "
                        f"Structure: {structure_result}({structure_confidence:.2f}) | "
                        f"Content: {content_result}({content_confidence:.2f}) | "
                        f"Final: {final_decision}({total_confidence:.2f}) | "
                        f"Reason: {decision_reason}")
            
            return final_decision, total_confidence
            
        except Exception as e:
            logger.error(f"[CONTENT-{check_id}] Error in intelligent decision making: {e}", exc_info=True)
            return False, 0.0
    
    async def _analyze_screenshot_url_patterns(self, url: str) -> dict:
        """Analyze URL patterns for screenshot content detection"""
        try:
            indicators = []
            confidence_boost = 0.0
            
            url_lower = url.lower()
            
            # Content page patterns
            content_patterns = [
                'article', 'post', 'detail', 'content', 'story', 'news',
                'blog', 'thread', 'topic', 'discussion', 'review'
            ]
            
            for pattern in content_patterns:
                if pattern in url_lower:
                    indicators.append(f"url_content_pattern_{pattern}")
                    confidence_boost += 0.1
            
            # Platform-specific content indicators
            platform_patterns = {
                'weibo.com': ['status', 'detail'],
                'douyin.com': ['video', 'share'],
                'xiaohongshu.com': ['explore', 'discovery'],
                'bilibili.com': ['video', 'av', 'BV'],
                'zhihu.com': ['question', 'answer'],
                'tiktok.com': ['video', '@'],
                'youtube.com': ['watch', 'video'],
                'twitter.com': ['status', 'tweet'],
                'instagram.com': ['p/', 'reel']
            }
            
            for platform, patterns in platform_patterns.items():
                if platform in url_lower:
                    for pattern in patterns:
                        if pattern in url_lower:
                            indicators.append(f"platform_content_{platform}_{pattern}")
                            confidence_boost += 0.15
                            break
            
            return {
                "indicators": indicators,
                "confidence_boost": min(confidence_boost, 0.4)  # Cap boost
            }
            
        except Exception as e:
            logger.error(f"Error analyzing screenshot URL patterns: {e}")
            return {"indicators": [], "confidence_boost": 0.0}
    
    async def _analyze_platform_screenshot_features(self, screenshot_bytes: bytes, url: str) -> dict:
        """Analyze platform-specific screenshot features"""
        try:
            indicators = []
            confidence_boost = 0.0
            features = {}
            
            # Basic image size analysis
            if len(screenshot_bytes) > 100000:  # > 100KB suggests rich content
                indicators.append("large_screenshot_size")
                confidence_boost += 0.1
                features["size_category"] = "large"
            elif len(screenshot_bytes) > 50000:  # > 50KB
                indicators.append("medium_screenshot_size")
                confidence_boost += 0.05
                features["size_category"] = "medium"
            else:
                features["size_category"] = "small"
            
            # Platform-specific analysis
            url_lower = url.lower()
            
            if 'weibo.com' in url_lower:
                features["platform"] = "weibo"
                if 'status' in url_lower or 'detail' in url_lower:
                    indicators.append("weibo_content_page")
                    confidence_boost += 0.2
            
            elif 'douyin.com' in url_lower:
                features["platform"] = "douyin"
                if 'video' in url_lower:
                    indicators.append("douyin_video_page")
                    confidence_boost += 0.2
            
            elif 'xiaohongshu.com' in url_lower:
                features["platform"] = "xiaohongshu"
                if 'explore' in url_lower or 'discovery' in url_lower:
                    indicators.append("xiaohongshu_content_page")
                    confidence_boost += 0.2
            
            elif 'bilibili.com' in url_lower:
                features["platform"] = "bilibili"
                if any(pattern in url_lower for pattern in ['video', 'av', 'BV']):
                    indicators.append("bilibili_video_page")
                    confidence_boost += 0.2
            
            return {
                "indicators": indicators,
                "confidence_boost": min(confidence_boost, 0.3),
                "features": features
            }
            
        except Exception as e:
            logger.error(f"Error analyzing platform screenshot features: {e}")
            return {"indicators": [], "confidence_boost": 0.0, "features": {}}
    
    async def _analyze_screenshot_image_properties(self, screenshot_bytes: bytes) -> dict:
        """Analyze basic image properties of screenshot"""
        try:
            indicators = []
            confidence_boost = 0.0
            features = {}
            
            # Image size analysis
            image_size = len(screenshot_bytes)
            features["byte_size"] = image_size
            
            # Size-based confidence
            if image_size > 500000:  # > 500KB - very detailed page
                indicators.append("very_large_image")
                confidence_boost += 0.15
                features["detail_level"] = "very_high"
            elif image_size > 200000:  # > 200KB - detailed page
                indicators.append("large_detailed_image")
                confidence_boost += 0.1
                features["detail_level"] = "high"
            elif image_size > 50000:  # > 50KB - normal content
                indicators.append("normal_content_image")
                confidence_boost += 0.05
                features["detail_level"] = "medium"
            else:
                features["detail_level"] = "low"
            
            # Basic format validation (PNG header check)
            if screenshot_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                indicators.append("valid_png_format")
                confidence_boost += 0.05
                features["format"] = "PNG"
            elif screenshot_bytes.startswith(b'\xff\xd8\xff'):
                indicators.append("valid_jpeg_format")
                confidence_boost += 0.05
                features["format"] = "JPEG"
            
            return {
                "indicators": indicators,
                "confidence_boost": min(confidence_boost, 0.2),
                "features": features
            }
            
        except Exception as e:
            logger.error(f"Error analyzing screenshot image properties: {e}")
            return {"indicators": [], "confidence_boost": 0.0, "features": {}}
    
    async def _get_platform_analysis_weight(self, url: str) -> dict:
        """Get platform-specific analysis weights for DOM vs Screenshot"""
        try:
            url_lower = url.lower()
            
            # Default weights
            weights = {"dom_weight": 0.7, "screenshot_weight": 0.3}
            
            # Platform-specific weight adjustments
            if 'douyin.com' in url_lower or 'tiktok.com' in url_lower:
                # Video platforms - screenshot more important
                weights = {"dom_weight": 0.4, "screenshot_weight": 0.6}
            elif 'xiaohongshu.com' in url_lower or 'instagram.com' in url_lower:
                # Image-heavy platforms - balanced approach
                weights = {"dom_weight": 0.5, "screenshot_weight": 0.5}
            elif 'bilibili.com' in url_lower or 'youtube.com' in url_lower:
                # Video platforms with rich DOM - slightly favor screenshot
                weights = {"dom_weight": 0.45, "screenshot_weight": 0.55}
            elif 'weibo.com' in url_lower or 'twitter.com' in url_lower:
                # Text-heavy platforms - favor DOM
                weights = {"dom_weight": 0.8, "screenshot_weight": 0.2}
            elif 'zhihu.com' in url_lower:
                # Text-heavy Q&A platform - heavily favor DOM
                weights = {"dom_weight": 0.85, "screenshot_weight": 0.15}
            
            return weights
            
        except Exception as e:
            logger.error(f"Error getting platform analysis weight: {e}")
            return {"dom_weight": 0.7, "screenshot_weight": 0.3}
    
    async def _extract_screenshot_content_data(self, screenshot_bytes: bytes, page: Page, url: str) -> dict:
        """Extract content data from screenshot and page combination"""
        try:
            content_data = {
                "screenshot_available": len(screenshot_bytes) > 0,
                "screenshot_size": len(screenshot_bytes),
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "content_indicators": []
            }
            
            if len(screenshot_bytes) > 0:
                # Basic screenshot metadata
                content_data["screenshot_metadata"] = {
                    "size_bytes": len(screenshot_bytes),
                    "format": "PNG" if screenshot_bytes.startswith(b'\x89PNG') else "Unknown",
                    "capture_time": datetime.utcnow().isoformat()
                }
                
                # Size-based content indicators
                if len(screenshot_bytes) > 300000:
                    content_data["content_indicators"].append("rich_visual_content")
                elif len(screenshot_bytes) > 100000:
                    content_data["content_indicators"].append("moderate_visual_content")
                else:
                    content_data["content_indicators"].append("minimal_visual_content")
                
                # Platform-specific content extraction hints
                url_lower = url.lower()
                if 'weibo.com' in url_lower:
                    content_data["platform_hints"] = {
                        "platform": "weibo",
                        "expected_elements": ["post_content", "user_info", "interaction_stats"]
                    }
                elif 'douyin.com' in url_lower:
                    content_data["platform_hints"] = {
                        "platform": "douyin",
                        "expected_elements": ["video_player", "description", "user_profile"]
                    }
                elif 'xiaohongshu.com' in url_lower:
                    content_data["platform_hints"] = {
                        "platform": "xiaohongshu",
                        "expected_elements": ["note_content", "images", "tags"]
                    }
                elif 'bilibili.com' in url_lower:
                    content_data["platform_hints"] = {
                        "platform": "bilibili",
                        "expected_elements": ["video_info", "description", "comments"]
                    }
            
            # Try to get basic page title for context
            try:
                page_title = await page.title()
                if page_title:
                    content_data["page_title"] = page_title
                    content_data["content_indicators"].append("has_page_title")
            except Exception:
                pass
            
            return content_data
            
        except Exception as e:
            logger.error(f"Error extracting screenshot content data: {e}")
            return {
                "screenshot_available": False,
                "error": str(e),
                "extraction_timestamp": datetime.utcnow().isoformat()
            }
    
    async def _analyze_url_structure(self, url: str, platform: str, check_id: str) -> tuple[bool, float]:
        """Intelligent URL structure analysis
        
        Analyzes URL components, path depth, parameters, and structural indicators
        to determine if it's likely a content page.
        
        Returns:
            tuple: (is_content_page, confidence_score)
        """
        from urllib.parse import urlparse, parse_qs
        import re
        
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            query_params = parse_qs(parsed.query)
            
            confidence_score = 0.0
            indicators = []
            
            # 1. Path depth analysis
            path_segments = [seg for seg in path.split('/') if seg]
            path_depth = len(path_segments)
            
            if path_depth >= 2:
                confidence_score += 0.3
                indicators.append(f"path_depth:{path_depth}")
            elif path_depth == 1:
                confidence_score += 0.1
                indicators.append(f"path_depth:{path_depth}")
            else:
                confidence_score -= 0.2
                indicators.append("shallow_path")
            
            # 2. Content-indicating path segments
            content_indicators = {
                'video': 0.4, 'post': 0.4, 'article': 0.4, 'content': 0.3,
                'detail': 0.3, 'view': 0.3, 'item': 0.3, 'story': 0.3,
                'explore': 0.25, 'discover': 0.25, 'watch': 0.4,
                'read': 0.3, 'show': 0.3, 'page': 0.2
            }
            
            for segment in path_segments:
                segment_lower = segment.lower()
                for indicator, score in content_indicators.items():
                    if indicator in segment_lower:
                        confidence_score += score
                        indicators.append(f"content_segment:{indicator}")
                        break
            
            # 3. ID pattern analysis in path
            id_patterns = [
                (r'^\d{10,}$', 0.4),  # 长数字ID
                (r'^\d{6,9}$', 0.3),  # 中等数字ID
                (r'^[a-f0-9]{20,}$', 0.4),  # 长十六进制ID
                (r'^[A-Za-z0-9]{8,}$', 0.3),  # 混合长ID
                (r'^[A-Z]{2}[A-Za-z0-9]{8,}$', 0.35),  # BV号等格式
            ]
            
            for segment in path_segments:
                for pattern, score in id_patterns:
                    if re.match(pattern, segment):
                        confidence_score += score
                        indicators.append(f"id_pattern:{pattern[:20]}")
                        break
            
            # 4. Query parameter analysis
            content_params = {
                'id': 0.3, 'vid': 0.3, 'pid': 0.3, 'post_id': 0.4,
                'article_id': 0.4, 'content_id': 0.4, 'item_id': 0.3,
                'v': 0.25, 'p': 0.2, 'share_id': 0.3
            }
            
            for param, values in query_params.items():
                param_lower = param.lower()
                if param_lower in content_params and values:
                    # Check if parameter value looks like an ID
                    value = values[0]
                    if re.match(r'^[A-Za-z0-9_-]{3,}$', value):
                        confidence_score += content_params[param_lower]
                        indicators.append(f"content_param:{param_lower}")
            
            # 5. Negative indicators (homepage/navigation patterns)
            negative_indicators = {
                'home': -0.3, 'index': -0.3, 'main': -0.2,
                'login': -0.5, 'register': -0.5, 'signup': -0.4,
                'about': -0.3, 'contact': -0.3, 'help': -0.2,
                'terms': -0.3, 'privacy': -0.3, 'policy': -0.3
            }
            
            for segment in path_segments:
                segment_lower = segment.lower()
                for neg_indicator, penalty in negative_indicators.items():
                    if neg_indicator in segment_lower:
                        confidence_score += penalty
                        indicators.append(f"negative:{neg_indicator}")
            
            # 6. Platform-specific structure analysis
            platform_bonus = 0.0
            if platform == "xiaohongshu":
                if 'explore' in path_segments or 'discovery' in path_segments:
                    platform_bonus += 0.2
            elif platform == "weibo":
                if len(path_segments) >= 2 and path_segments[0].isdigit():
                    platform_bonus += 0.3
            elif platform == "douyin":
                if 'video' in path_segments or 'user' in path_segments:
                    platform_bonus += 0.2
            elif platform == "bilibili":
                if 'video' in path_segments or 'space' in path_segments:
                    platform_bonus += 0.2
            
            confidence_score += platform_bonus
            if platform_bonus > 0:
                indicators.append(f"platform_bonus:{platform_bonus:.2f}")
            
            # 7. URL length and complexity analysis
            if len(url) > 50:
                confidence_score += 0.1
                indicators.append("complex_url")
            
            if len(parsed.query) > 10:
                confidence_score += 0.05
                indicators.append("has_params")
            
            # Normalize confidence score
            confidence_score = max(0.0, min(1.0, confidence_score))
            
            # Decision threshold
            is_content_page = confidence_score > 0.4
            
            logger.debug(f"[CONTENT-{check_id}] URL structure analysis | "
                        f"Segments: {path_segments} | Indicators: {indicators[:5]} | "
                        f"Score: {confidence_score:.3f} | Decision: {is_content_page}")
            
            return is_content_page, confidence_score
            
        except Exception as e:
             logger.error(f"[CONTENT-{check_id}] Error in URL structure analysis: {e}", exc_info=True)
             return False, 0.0
    
    async def _analyze_page_content(self, page, url: str, platform: str, check_id: str) -> tuple[bool, float]:
        """Dynamic page content analysis
        
        Analyzes actual page content, DOM structure, and metadata
        to determine if it's a content page.
        
        Returns:
            tuple: (is_content_page, confidence_score)
        """
        try:
            confidence_score = 0.0
            indicators = []
            
            # 1. Page title analysis
            try:
                title = await page.title()
                if title:
                    title_lower = title.lower()
                    
                    # Content-indicating title patterns
                    content_title_patterns = [
                        r'.*视频.*', r'.*文章.*', r'.*帖子.*', r'.*内容.*',
                        r'.*story.*', r'.*post.*', r'.*video.*', r'.*article.*'
                    ]
                    
                    for pattern in content_title_patterns:
                        if re.search(pattern, title_lower):
                            confidence_score += 0.2
                            indicators.append("content_title")
                            break
                    
                    # Negative title patterns
                    negative_title_patterns = [
                        r'.*首页.*', r'.*主页.*', r'.*登录.*', r'.*注册.*',
                        r'.*home.*', r'.*login.*', r'.*register.*', r'.*index.*'
                    ]
                    
                    for pattern in negative_title_patterns:
                        if re.search(pattern, title_lower):
                            confidence_score -= 0.3
                            indicators.append("negative_title")
                            break
                    
                    # Title length analysis
                    if len(title) > 20:
                        confidence_score += 0.1
                        indicators.append("detailed_title")
                        
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Title analysis failed: {e}")
            
            # 2. Meta tags analysis
            try:
                # Check for content-specific meta tags
                meta_selectors = [
                    'meta[property="og:type"]',
                    'meta[name="description"]',
                    'meta[property="og:description"]',
                    'meta[name="keywords"]'
                ]
                
                for selector in meta_selectors:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        content = await element.get_attribute('content')
                        if content:
                            content_lower = content.lower()
                            
                            # Content type indicators
                            if 'article' in content_lower or 'video' in content_lower:
                                confidence_score += 0.15
                                indicators.append("meta_content_type")
                            
                            # Rich description indicates content page
                            if len(content) > 50:
                                confidence_score += 0.1
                                indicators.append("rich_meta")
                                
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Meta analysis failed: {e}")
            
            # 3. Content structure analysis
            try:
                # Look for main content containers
                content_selectors = [
                    'article', 'main', '[role="main"]',
                    '.content', '.post', '.article',
                    '.video-container', '.media-container'
                ]
                
                content_found = False
                for selector in content_selectors:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        confidence_score += 0.2
                        indicators.append(f"content_structure:{selector}")
                        content_found = True
                        break
                
                if not content_found:
                    confidence_score -= 0.1
                    indicators.append("no_content_structure")
                    
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Content structure analysis failed: {e}")
            
            # 4. Text content analysis
            try:
                # Get visible text content
                text_content = await page.evaluate('''
                    () => {
                        const walker = document.createTreeWalker(
                            document.body,
                            NodeFilter.SHOW_TEXT,
                            {
                                acceptNode: function(node) {
                                    const parent = node.parentElement;
                                    if (!parent) return NodeFilter.FILTER_REJECT;
                                    
                                    const style = window.getComputedStyle(parent);
                                    if (style.display === 'none' || style.visibility === 'hidden') {
                                        return NodeFilter.FILTER_REJECT;
                                    }
                                    
                                    return NodeFilter.FILTER_ACCEPT;
                                }
                            }
                        );
                        
                        let text = '';
                        let node;
                        while (node = walker.nextNode()) {
                            text += node.textContent + ' ';
                        }
                        
                        return text.trim();
                    }
                ''')
                
                if text_content:
                    text_length = len(text_content)
                    
                    # Content length analysis
                    if text_length > 500:
                        confidence_score += 0.25
                        indicators.append(f"rich_text:{text_length}")
                    elif text_length > 200:
                        confidence_score += 0.15
                        indicators.append(f"moderate_text:{text_length}")
                    elif text_length < 50:
                        confidence_score -= 0.1
                        indicators.append(f"sparse_text:{text_length}")
                        
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Text content analysis failed: {e}")
            
            # 5. Media content analysis
            try:
                # Check for images and videos
                img_count = len(await page.query_selector_all('img[src]'))
                video_count = len(await page.query_selector_all('video'))
                
                if img_count > 3:
                    confidence_score += 0.15
                    indicators.append(f"rich_images:{img_count}")
                elif img_count > 0:
                    confidence_score += 0.05
                    indicators.append(f"has_images:{img_count}")
                
                if video_count > 0:
                    confidence_score += 0.2
                    indicators.append(f"has_videos:{video_count}")
                    
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Media analysis failed: {e}")
            
            # 6. Platform-specific content indicators
            try:
                platform_indicators = {
                    "xiaohongshu": [
                        '.note-item', '.explore-item', '.feed-item'
                    ],
                    "weibo": [
                        '.WB_detail', '.WB_feed_detail', '.card-wrap'
                    ],
                    "douyin": [
                        '.video-info', '.aweme-video', '.player-container'
                    ],
                    "bilibili": [
                        '.video-info', '.bpx-player', '.video-desc'
                    ]
                }
                
                if platform in platform_indicators:
                    for selector in platform_indicators[platform]:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            confidence_score += 0.2
                            indicators.append(f"platform_content:{platform}")
                            break
                            
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Platform-specific analysis failed: {e}")
            
            # 7. Navigation and UI analysis
            try:
                # Check for navigation elements (negative indicator)
                nav_selectors = [
                    'nav', '.navigation', '.nav-bar', '.menu',
                    '.sidebar', '.header-nav'
                ]
                
                nav_count = 0
                for selector in nav_selectors:
                    elements = await page.query_selector_all(selector)
                    nav_count += len(elements)
                
                if nav_count > 3:
                    confidence_score -= 0.1
                    indicators.append(f"heavy_navigation:{nav_count}")
                    
            except Exception as e:
                logger.debug(f"[CONTENT-{check_id}] Navigation analysis failed: {e}")
            
            # Normalize confidence score
            confidence_score = max(0.0, min(1.0, confidence_score))
            
            # Decision threshold
            is_content_page = confidence_score > 0.3
            
            logger.debug(f"[CONTENT-{check_id}] Page content analysis | "
                        f"Indicators: {indicators[:5]} | "
                        f"Score: {confidence_score:.3f} | Decision: {is_content_page}")
            
            return is_content_page, confidence_score
            
        except Exception as e:
            logger.error(f"[CONTENT-{check_id}] Error in page content analysis: {e}", exc_info=True)
            return False, 0.0
    
    async def _check_login_status_for_navigation(self, instance_id: str, page_id: str, page: Page, platform: str) -> bool:
        """Check if user is logged in for navigation-triggered crawling"""
        import uuid
        import time
        
        # Generate unique login check ID for tracking
        check_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"[LOGIN-{check_id}] Checking login status for navigation | "
                   f"Instance: {instance_id} | Page: {page_id} | Platform: {platform}")
        
        try:
            # Use existing login status check method
            check_start_time = time.time()
            login_status = await self._check_page_login_status(instance_id, page_id, page)
            check_duration = time.time() - check_start_time
            
            total_duration = time.time() - start_time
            
            if login_status:
                logger.info(f"[LOGIN-{check_id}] User is logged in to {platform} | "
                           f"Auto-crawl can proceed | Check duration: {check_duration:.3f}s | "
                           f"Total: {total_duration:.3f}s")
                return True
            else:
                logger.info(f"[LOGIN-{check_id}] User is not logged in to {platform} | "
                           f"Skipping auto-crawl | Check duration: {check_duration:.3f}s | "
                           f"Total: {total_duration:.3f}s")
                return False
                
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[LOGIN-{check_id}] Exception checking login status for navigation | "
                        f"Instance: {instance_id} | Page: {page_id} | Platform: {platform} | "
                        f"Duration: {total_duration:.3f}s | Error: {e}", exc_info=True)
            return False
    
    async def _should_trigger_crawl(self, url: str, platform: str, trigger_type: str = "auto") -> bool:
        """Check if crawl should be triggered for this URL (intelligent duplicate prevention)
        
        Args:
            url: The URL to check
            platform: The platform name
            trigger_type: "auto" for automatic triggers, "user" for user-initiated navigation
        """
        import uuid
        import time
        
        # Generate unique trigger check ID for tracking
        trigger_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(f"[TRIGGER-{trigger_id}] Checking if crawl should be triggered | "
                   f"URL: {url[:100]}{'...' if len(url) > 100 else ''} | "
                   f"Platform: {platform} | Type: {trigger_type}")
        
        try:
            # Create a unique key for this URL and platform
            crawl_key = f"{platform}:{url}"
            
            # Initialize crawl history if not exists
            if not hasattr(self, 'crawl_history'):
                self.crawl_history = {}
            
            current_time = datetime.utcnow()
            
            # Check if URL was recently crawled
            if crawl_key in self.crawled_urls:
                crawl_info = self.crawled_urls[crawl_key]
                
                # Get crawl history for this URL
                history = self.crawl_history.get(crawl_key, {'attempts': 0, 'last_attempt': None, 'success_count': 0, 'fail_count': 0})
                
                # Calculate dynamic time limits based on success/failure history
                base_time_limit = 30 if trigger_type == "user" else 300  # Base: 30s for user, 5min for auto
                
                # Adjust time limit based on history
                success_rate = history['success_count'] / max(history['attempts'], 1)
                if success_rate > 0.8:  # High success rate - longer cooldown
                    time_multiplier = 2.0
                elif success_rate < 0.3:  # Low success rate - shorter cooldown for retry
                    time_multiplier = 0.5
                else:
                    time_multiplier = 1.0
                
                # Apply frequency-based multiplier
                if history['attempts'] > 10:  # High frequency - increase cooldown
                    time_multiplier *= 1.5
                elif history['attempts'] > 20:  # Very high frequency - significant cooldown
                    time_multiplier *= 3.0
                
                dynamic_time_limit = base_time_limit * time_multiplier
                time_since_last = (current_time - crawl_info['timestamp']).total_seconds()
                
                # Check if within cooldown period
                if crawl_info.get('success') and time_since_last < dynamic_time_limit:
                    logger.debug(f"URL in cooldown period (trigger_type: {trigger_type}, cooldown: {dynamic_time_limit:.1f}s, elapsed: {time_since_last:.1f}s): {url}")
                    return False
                
                # Special handling for failed crawls
                if not crawl_info.get('success'):
                    # For failed crawls, use exponential backoff
                    consecutive_failures = history.get('consecutive_failures', 0)
                    backoff_time = min(base_time_limit * (2 ** consecutive_failures), 3600)  # Max 1 hour
                    
                    if time_since_last < backoff_time:
                        logger.debug(f"URL in failure backoff period (failures: {consecutive_failures}, backoff: {backoff_time:.1f}s, elapsed: {time_since_last:.1f}s): {url}")
                        return False
                
                # Check for rate limiting (max attempts per hour)
                hour_ago = current_time - timedelta(hours=1)
                recent_attempts = [attempt for attempt in history.get('attempt_times', []) if attempt > hour_ago]
                
                max_attempts_per_hour = 10 if trigger_type == "user" else 5
                if len(recent_attempts) >= max_attempts_per_hour:
                    logger.warning(f"Rate limit exceeded for URL (attempts in last hour: {len(recent_attempts)}): {url}")
                    return False
                
                # If we've passed all checks, clean up old entry
                if time_since_last > dynamic_time_limit:
                    logger.debug(f"Removed expired crawl entry (elapsed: {time_since_last:.1f}s, limit: {dynamic_time_limit:.1f}s): {url}")
            
            # Additional intelligent checks
            
            # 1. Check for URL pattern abuse (same pattern crawled too frequently)
            pattern_check_start = time.time()
            pattern_abuse = await self._check_url_pattern_abuse(url, platform, trigger_type)
            pattern_check_duration = time.time() - pattern_check_start
            
            if pattern_abuse:
                total_duration = time.time() - start_time
                logger.warning(f"[TRIGGER-{trigger_id}] URL pattern abuse detected, skipping crawl | "
                              f"Pattern check: {pattern_check_duration:.3f}s | Total: {total_duration:.3f}s | "
                              f"URL: {url[:100]}{'...' if len(url) > 100 else ''}")
                return False
            
            logger.debug(f"[TRIGGER-{trigger_id}] Pattern abuse check passed | Duration: {pattern_check_duration:.3f}s")
            
            # 2. Check for session-based rate limiting
            session_check_start = time.time()
            session_limit = await self._check_session_rate_limit(platform, trigger_type)
            session_check_duration = time.time() - session_check_start
            
            if session_limit:
                total_duration = time.time() - start_time
                logger.warning(f"[TRIGGER-{trigger_id}] Session rate limit exceeded, skipping crawl | "
                              f"Platform: {platform} | Session check: {session_check_duration:.3f}s | "
                              f"Total: {total_duration:.3f}s | URL: {url[:100]}{'...' if len(url) > 100 else ''}")
                return False
            
            logger.debug(f"[TRIGGER-{trigger_id}] Session rate limit check passed | Duration: {session_check_duration:.3f}s")
            
            # 3. Check for content freshness (if we have previous content)
            freshness_check_start = time.time()
            skip_fresh = await self._should_skip_based_on_content_freshness(url, platform)
            freshness_check_duration = time.time() - freshness_check_start
            
            if skip_fresh:
                total_duration = time.time() - start_time
                logger.debug(f"[TRIGGER-{trigger_id}] Content appears fresh, skipping crawl | "
                            f"Freshness check: {freshness_check_duration:.3f}s | Total: {total_duration:.3f}s | "
                            f"URL: {url[:100]}{'...' if len(url) > 100 else ''}")
                return False
            
            logger.debug(f"[TRIGGER-{trigger_id}] Content freshness check passed | Duration: {freshness_check_duration:.3f}s")
            
            total_duration = time.time() - start_time
            logger.info(f"[TRIGGER-{trigger_id}] URL can be crawled | Type: {trigger_type} | "
                       f"Total checks duration: {total_duration:.3f}s | "
                       f"URL: {url[:100]}{'...' if len(url) > 100 else ''}")
            return True
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[TRIGGER-{trigger_id}] Exception checking if should trigger crawl | "
                        f"Platform: {platform} | Type: {trigger_type} | Duration: {total_duration:.3f}s | "
                        f"Error: {e} | URL: {url[:100]}{'...' if len(url) > 100 else ''}", exc_info=True)
            return False
    
    async def _check_url_pattern_abuse(self, url: str, platform: str, trigger_type: str) -> bool:
        """Check if URL pattern is being crawled too frequently"""
        abuse_check_id = f"abuse-{int(time.time() * 1000)}-{hash(url) % 10000}"
        start_time = time.time()
        
        try:
            import re
            from urllib.parse import urlparse
            
            logger.debug(f"[ABUSE-{abuse_check_id}] Starting URL pattern abuse check | "
                        f"Platform: {platform} | Type: {trigger_type} | "
                        f"URL: {url[:100]}{'...' if len(url) > 100 else ''}")
            
            # Extract URL pattern (remove specific IDs)
            parse_start = time.time()
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Create pattern by replacing IDs with placeholders
            pattern_path = re.sub(r'/\\d+', '/{id}', path)  # Replace numeric IDs
            pattern_path = re.sub(r'/[a-f0-9]{8,}', '/{hash}', pattern_path)  # Replace hash IDs
            pattern_key = f"{platform}:{parsed_url.netloc}{pattern_path}"
            parse_duration = time.time() - parse_start
            
            if not hasattr(self, 'pattern_crawl_times'):
                self.pattern_crawl_times = {}
            
            current_time = datetime.utcnow()
            hour_ago = current_time - timedelta(hours=1)
            
            # Clean old entries
            cleanup_start = time.time()
            if pattern_key in self.pattern_crawl_times:
                old_count = len(self.pattern_crawl_times[pattern_key])
                self.pattern_crawl_times[pattern_key] = [
                    t for t in self.pattern_crawl_times[pattern_key] if t > hour_ago
                ]
                cleaned_count = old_count - len(self.pattern_crawl_times[pattern_key])
                if cleaned_count > 0:
                    logger.debug(f"[ABUSE-{abuse_check_id}] Cleaned {cleaned_count} old entries")
            else:
                self.pattern_crawl_times[pattern_key] = []
            cleanup_duration = time.time() - cleanup_start
            
            # Check frequency
            recent_crawls = len(self.pattern_crawl_times[pattern_key])
            max_pattern_crawls = 20 if trigger_type == "user" else 10
            
            total_duration = time.time() - start_time
            
            if recent_crawls >= max_pattern_crawls:
                logger.warning(f"[ABUSE-{abuse_check_id}] URL pattern abuse detected | "
                              f"Pattern: {pattern_key[:80]}{'...' if len(pattern_key) > 80 else ''} | "
                              f"Recent crawls: {recent_crawls}/{max_pattern_crawls} | "
                              f"Parse: {parse_duration:.3f}s | Cleanup: {cleanup_duration:.3f}s | "
                              f"Total: {total_duration:.3f}s")
                return True
            
            # Record this attempt
            self.pattern_crawl_times[pattern_key].append(current_time)
            
            logger.debug(f"[ABUSE-{abuse_check_id}] Pattern abuse check passed | "
                        f"Recent crawls: {recent_crawls}/{max_pattern_crawls} | "
                        f"Duration: {total_duration:.3f}s")
            return False
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[ABUSE-{abuse_check_id}] Exception checking URL pattern abuse | "
                        f"Platform: {platform} | Type: {trigger_type} | Duration: {total_duration:.3f}s | "
                        f"Error: {e} | URL: {url[:100]}{'...' if len(url) > 100 else ''}", exc_info=True)
            return False
    
    async def _check_session_rate_limit(self, platform: str, trigger_type: str) -> bool:
        """Check session-based rate limiting"""
        session_check_id = f"session-{int(time.time() * 1000)}-{hash(platform) % 10000}"
        start_time = time.time()
        
        try:
            logger.debug(f"[SESSION-{session_check_id}] Starting session rate limit check | "
                        f"Platform: {platform} | Type: {trigger_type}")
            
            if not hasattr(self, 'session_crawl_times'):
                self.session_crawl_times = {}
            
            current_time = datetime.utcnow()
            hour_ago = current_time - timedelta(hours=1)
            
            # Clean old entries
            cleanup_start = time.time()
            if platform in self.session_crawl_times:
                old_count = len(self.session_crawl_times[platform])
                self.session_crawl_times[platform] = [
                    t for t in self.session_crawl_times[platform] if t > hour_ago
                ]
                cleaned_count = old_count - len(self.session_crawl_times[platform])
                if cleaned_count > 0:
                    logger.debug(f"[SESSION-{session_check_id}] Cleaned {cleaned_count} old session entries")
            else:
                self.session_crawl_times[platform] = []
            cleanup_duration = time.time() - cleanup_start
            
            # Check frequency
            recent_crawls = len(self.session_crawl_times[platform])
            max_session_crawls = 50 if trigger_type == "user" else 30
            
            total_duration = time.time() - start_time
            
            if recent_crawls >= max_session_crawls:
                logger.warning(f"[SESSION-{session_check_id}] Session rate limit exceeded | "
                              f"Platform: {platform} | Recent crawls: {recent_crawls}/{max_session_crawls} | "
                              f"Cleanup: {cleanup_duration:.3f}s | Total: {total_duration:.3f}s")
                return True
            
            # Record this attempt
            self.session_crawl_times[platform].append(current_time)
            
            logger.debug(f"[SESSION-{session_check_id}] Session rate limit check passed | "
                        f"Recent crawls: {recent_crawls}/{max_session_crawls} | "
                        f"Duration: {total_duration:.3f}s")
            return False
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[SESSION-{session_check_id}] Exception checking session rate limit | "
                        f"Platform: {platform} | Type: {trigger_type} | Duration: {total_duration:.3f}s | "
                        f"Error: {e}", exc_info=True)
            return False
    
    async def _should_skip_based_on_content_freshness(self, url: str, platform: str) -> bool:
        """Check if content is likely fresh based on URL patterns and timing"""
        freshness_check_id = f"fresh-{int(time.time() * 1000)}-{hash(url) % 10000}"
        start_time = time.time()
        
        try:
            logger.debug(f"[FRESH-{freshness_check_id}] Starting content freshness check | "
                        f"Platform: {platform} | URL: {url[:100]}{'...' if len(url) > 100 else ''}")
            
            # Skip freshness check for user-initiated crawls
            # This is mainly for automatic/continuous crawls
            
            # Check if URL contains time-sensitive patterns
            pattern_check_start = time.time()
            time_sensitive_patterns = [
                r'/live/',  # Live content
                r'/breaking/',  # Breaking news
                r'/latest/',  # Latest content
                r'\\?t=\\d+',  # Timestamp parameters
                r'#live',  # Live anchors
            ]
            
            import re
            for pattern in time_sensitive_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    total_duration = time.time() - start_time
                    logger.debug(f"[FRESH-{freshness_check_id}] URL contains time-sensitive pattern, allowing crawl | "
                                f"Pattern: {pattern} | Duration: {total_duration:.3f}s")
                    return False
            pattern_check_duration = time.time() - pattern_check_start
            
            # For static content URLs, check if they were recently crawled successfully
            crawl_check_start = time.time()
            crawl_key = f"{platform}:{url}"
            if crawl_key in self.crawled_urls:
                crawl_info = self.crawled_urls[crawl_key]
                if crawl_info.get('success'):
                    # If successfully crawled within last 10 minutes, consider content fresh
                    time_since_crawl = (datetime.utcnow() - crawl_info['timestamp']).total_seconds()
                    if time_since_crawl < 600:  # 10 minutes
                        total_duration = time.time() - start_time
                        logger.debug(f"[FRESH-{freshness_check_id}] Content is fresh, skipping crawl | "
                                    f"Time since last crawl: {time_since_crawl:.0f}s | "
                                    f"Pattern check: {pattern_check_duration:.3f}s | "
                                    f"Total: {total_duration:.3f}s")
                        return True
            crawl_check_duration = time.time() - crawl_check_start
            
            total_duration = time.time() - start_time
            logger.debug(f"[FRESH-{freshness_check_id}] Content freshness check passed, allowing crawl | "
                        f"Pattern check: {pattern_check_duration:.3f}s | "
                        f"Crawl check: {crawl_check_duration:.3f}s | "
                        f"Total: {total_duration:.3f}s")
            return False
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[FRESH-{freshness_check_id}] Exception checking content freshness | "
                        f"Platform: {platform} | Duration: {total_duration:.3f}s | "
                        f"Error: {e} | URL: {url[:100]}{'...' if len(url) > 100 else ''}", exc_info=True)
            return False
    
    async def _trigger_navigation_crawl(self, url: str, platform: str, session_id: str, instance_id: str, trigger_type: str = "auto") -> bool:
        """Trigger crawl for navigation-detected target page (Queue-based)
        
        Args:
            url: The URL to crawl
            platform: The platform name
            session_id: The session ID
            instance_id: The browser instance ID
            trigger_type: "auto" for automatic triggers, "user" for user-initiated navigation
        """
        import uuid
        import time
        import aiohttp
        
        # Generate unique trigger ID for tracking
        trigger_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        crawl_key = f"{platform}:{url}"
        current_time = datetime.utcnow()
        
        # Initialize crawl history if not exists
        if not hasattr(self, 'crawl_history'):
            self.crawl_history = {}
        
        # Update crawl history before attempting
        if crawl_key not in self.crawl_history:
            self.crawl_history[crawl_key] = {
                'attempts': 0,
                'success_count': 0,
                'fail_count': 0,
                'consecutive_failures': 0,
                'attempt_times': [],
                'last_attempt': None
            }
        
        history = self.crawl_history[crawl_key]
        history['attempts'] += 1
        history['last_attempt'] = current_time
        history['attempt_times'].append(current_time)
        
        # Clean old attempt times (keep only last 24 hours)
        day_ago = current_time - timedelta(hours=24)
        history['attempt_times'] = [t for t in history['attempt_times'] if t > day_ago]
        
        success_rate = history['success_count'] / max(history['attempts'] - 1, 1)
        
        logger.info(f"[TRIGGER-{trigger_id}] Navigation crawl queued | "
                   f"Platform: {platform} | Type: {trigger_type} | "
                   f"Instance: {instance_id} | Session: {session_id} | "
                   f"Attempt: {history['attempts']} | Success rate: {success_rate:.2%} | "
                   f"Consecutive failures: {history['consecutive_failures']} | "
                   f"URL: {url[:100]}{'...' if len(url) > 100 else ''}")
        
        try:
            # Create task for Go backend queue system
            task_data_start = time.time()
            
            # Determine priority based on trigger type and history
            if trigger_type == "user":
                priority = 0  # 用户触发为超高优先级（实时爬取）
            elif trigger_type == "auto":
                priority = 1  # 自动触发为高优先级
            else:
                priority = 2  # 其他情况为普通优先级
            
            if history['consecutive_failures'] > 3:
                priority = 3  # 连续失败超过3次，降为低优先级
            
            task_payload = {
                "url": url,
                "platform": platform,
                "session_id": session_id,
                "instance_id": instance_id,
                "priority": priority,
                "trigger_type": trigger_type,
                "auto_triggered": trigger_type == "auto",
                "trigger_source": "page_navigation",
                "attempt_number": history['attempts'],
                "consecutive_failures": history['consecutive_failures'],
                "trigger_id": trigger_id,
                "created_at": current_time.isoformat(),
                "metadata": {
                    "browser_instance_id": instance_id,
                    "navigation_trigger": True,
                    "user_initiated": trigger_type == "user",
                    "success_rate": success_rate
                }
            }
            task_data_duration = time.time() - task_data_start
            
            logger.debug(f"[TRIGGER-{trigger_id}] Task payload prepared | "
                        f"Duration: {task_data_duration:.3f}s | "
                        f"Priority: {priority} | Auto triggered: {trigger_type == 'auto'}")
            
            # Submit task to Go backend queue
            queue_submission_start = time.time()
            
            # Get Go backend URL from config or environment
            go_backend_url = getattr(self, 'go_backend_url', 'http://localhost:8081')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{go_backend_url}/api/v1/tasks/create",
                    json=task_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200 or response.status == 201:
                        result = await response.json()
                        task_id = result.get("task_id")
                        
                        queue_submission_duration = time.time() - queue_submission_start
                        total_duration = time.time() - start_time
                        
                        logger.info(f"[TRIGGER-{trigger_id}] Task queued successfully | "
                                   f"Task ID: {task_id} | Priority: {priority} | "
                                   f"Queue time: {queue_submission_duration:.3f}s | "
                                   f"Total time: {total_duration:.3f}s | "
                                   f"Task type: navigation_{trigger_type}")
                        
                        # Update success statistics for queuing
                        history['success_count'] += 1
                        history['consecutive_failures'] = 0  # Reset consecutive failures for successful queuing
                        
                        # Mark as successfully queued (not executed yet)
                        self.crawled_urls[crawl_key] = {
                            'success': True,
                            'timestamp': current_time,
                            'task_id': task_id,
                            'trigger_type': trigger_type,
                            'status': 'queued',
                            'priority': priority
                        }
                        
                        # Trigger immediate worker check for idle workers
                        try:
                            if self.worker_manager:
                                await self.worker_manager.trigger_immediate_task_check()
                                logger.debug(f"[TRIGGER-{trigger_id}] Triggered immediate worker check for task {task_id}")
                        except Exception as worker_error:
                            logger.warning(f"[TRIGGER-{trigger_id}] Failed to trigger worker check: {worker_error}")
                        
                        return True
                    else:
                        error_text = await response.text()
                        raise Exception(f"Go backend returned {response.status}: {error_text}")
            
        except Exception as e:
            # Update failure statistics on exception
            history['fail_count'] += 1
            history['consecutive_failures'] += 1
            
            # Mark as failed (queue submission failed)
            self.crawled_urls[crawl_key] = {
                'success': False,
                'timestamp': current_time,
                'error': str(e),
                'trigger_type': trigger_type,
                'status': 'queue_failed'
            }
            
            total_duration = time.time() - start_time
            logger.error(f"[TRIGGER-{trigger_id}] Failed to queue navigation crawl task | "
                        f"Platform: {platform} | Duration: {total_duration:.3f}s | "
                        f"Consecutive failures: {history['consecutive_failures']} | "
                        f"Trigger type: {trigger_type} | Error: {e}")
            return False
    
    async def _trigger_realtime_navigation_crawl(self, url: str, platform: str, session_id: str, instance_id: str, trigger_type: str = "user") -> bool:
        """触发实时导航爬取任务，立即创建任务并检查Worker状态进行实时处理
        
        Args:
            url: The URL to crawl
            platform: The platform name
            session_id: The session ID
            instance_id: The browser instance ID
            trigger_type: "user" for user-initiated navigation, "auto" for automatic triggers
        
        Returns:
            bool: True if task was successfully created and processed or queued
        """
        import time
        
        trigger_id = f"rt_{int(time.time() * 1000)}_{hash(url) % 10000}"
        start_time = time.time()
        
        try:
            logger.info(f"[REALTIME-{trigger_id}] Starting real-time navigation crawl for {url}")
            
            # 1. 首先尝试立即执行（如果当前浏览器可用）
            immediate_start = time.time()
            immediate_result = await self._try_immediate_crawl(url, platform, session_id, instance_id, trigger_id)
            immediate_duration = time.time() - immediate_start
            
            if immediate_result:
                total_duration = time.time() - start_time
                logger.info(f"[REALTIME-{trigger_id}] Immediate crawl completed successfully | "
                           f"Immediate: {immediate_duration:.3f}s | Total: {total_duration:.3f}s")
                return True
            
            # 2. 如果立即执行失败，创建队列任务
            queue_start = time.time()
            queue_result = await self._trigger_navigation_crawl(url, platform, session_id, instance_id, trigger_type)
            queue_duration = time.time() - queue_start
            
            if not queue_result:
                logger.error(f"[REALTIME-{trigger_id}] Failed to create queue task")
                return False
            
            # 3. 立即检查并触发Worker处理
            worker_start = time.time()
            worker_triggered = await self._trigger_immediate_worker_check()
            worker_duration = time.time() - worker_start
            
            total_duration = time.time() - start_time
            
            if worker_triggered:
                logger.info(f"[REALTIME-{trigger_id}] Real-time crawl setup completed | "
                           f"Queue: {queue_duration:.3f}s | Worker: {worker_duration:.3f}s | "
                           f"Total: {total_duration:.3f}s | Worker triggered immediately")
            else:
                logger.warning(f"[REALTIME-{trigger_id}] Real-time crawl queued but worker trigger failed | "
                              f"Queue: {queue_duration:.3f}s | Worker: {worker_duration:.3f}s | "
                              f"Total: {total_duration:.3f}s | Task will be processed in next cycle")
            
            return True
            
        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[REALTIME-{trigger_id}] Failed to trigger real-time navigation crawl | "
                        f"Duration: {total_duration:.3f}s | Error: {str(e)}")
            return False
    
    async def _try_immediate_crawl(self, url: str, platform: str, session_id: str, instance_id: str, trigger_id: str) -> bool:
        """尝试立即执行爬取任务（使用当前浏览器实例）
        
        Args:
            url: The URL to crawl
            platform: The platform name
            session_id: The session ID
            instance_id: The browser instance ID
            trigger_id: The trigger ID for logging
        
        Returns:
            bool: True if immediate crawl was successful
        """
        try:
            # 检查当前浏览器是否可用于立即爬取
            if not hasattr(self, 'manual_crawl_service') or not self.manual_crawl_service:
                logger.debug(f"[REALTIME-{trigger_id}] No manual crawl service available for immediate execution")
                return False
            
            # 检查是否有可用的浏览器实例
            current_page = self.get_current_page()
            if not current_page:
                logger.debug(f"[REALTIME-{trigger_id}] No current page available for immediate execution")
                return False
            
            # 检查当前页面是否就是目标URL（避免重复爬取）
            current_url = current_page.url
            if current_url == url:
                logger.info(f"[REALTIME-{trigger_id}] Current page matches target URL, executing immediate crawl")
                
                # 立即执行爬取
                result = await self.manual_crawl_service.execute_crawl_task({
                    'url': url,
                    'platform': platform,
                    'session_id': session_id,
                    'instance_id': instance_id,
                    'priority': 'high',
                    'trigger_type': 'realtime_immediate',
                    'trigger_id': trigger_id
                })
                
                return result and result.get('success', False)
            else:
                logger.debug(f"[REALTIME-{trigger_id}] Current page URL mismatch | Current: {current_url} | Target: {url}")
                return False
            
        except Exception as e:
            logger.debug(f"[REALTIME-{trigger_id}] Immediate crawl failed: {str(e)}")
            return False
    
    async def _trigger_immediate_worker_check(self) -> bool:
        """触发Worker立即检查队列并处理任务
        
        Returns:
            bool: True if worker check was successfully triggered
        """
        try:
            import aiohttp
            
            # 调用Worker管理器的立即检查接口
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'http://localhost:8001/api/v1/worker/trigger-immediate-check',
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('triggered', False)
                    else:
                        logger.warning(f"Worker trigger failed with status: {response.status}")
                        return False
                        
        except Exception as e:
            logger.debug(f"Failed to trigger immediate worker check: {str(e)}")
            return False
    
    async def _handle_page_created(self, instance_id: str, page: Page):
        """Handle new page creation"""
        try:
            await self._setup_single_page_listeners(instance_id, page)
            
            # Sync session data to new page if cross-tab sync is enabled
            if self.cross_tab_sync_enabled and instance_id in self.session_storage:
                await self._sync_session_to_page(instance_id, page)
            
            logger.info(f"New page created for instance {instance_id}: {page.url}")
            
        except Exception as e:
            logger.error(f"Error handling page creation: {e}")
    
    async def _handle_page_closed(self, instance_id: str, page_id: str):
        """Handle page closure"""
        try:
            # Remove page state
            if instance_id in self.tab_states and page_id in self.tab_states[instance_id]:
                del self.tab_states[instance_id][page_id]
            
            # Remove page reference
            if page_id in self.pages:
                del self.pages[page_id]
            
            logger.info(f"Page closed: {page_id}")
            
        except Exception as e:
            logger.error(f"Error handling page closure: {e}")
    
    async def _wait_for_page_stability(self, page: Page, url: str, max_wait_time: int = 15) -> bool:
        """Enhanced page stability detection with dynamic content monitoring
        
        Args:
            page: The page object
            url: The current URL
            max_wait_time: Maximum time to wait in seconds (increased default)
            
        Returns:
            bool: True if page is stable, False if timeout or error
        """
        try:
            import asyncio
            import hashlib
            
            logger.debug(f"Enhanced page stability check starting: {url}")
            start_time = asyncio.get_event_loop().time()
            
            # Phase 1: Wait for basic DOM content loaded
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=max_wait_time * 1000)
                logger.debug(f"DOM content loaded: {url}")
            except Exception as e:
                logger.warning(f"Timeout waiting for DOM content loaded: {e}")
                return False
            
            # Phase 2: Wait for network idle (no requests for 500ms)
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)  # 5 seconds max
                logger.debug(f"Network idle achieved: {url}")
            except Exception as e:
                logger.debug(f"Network idle timeout (continuing): {e}")
            
            # Phase 3: Enhanced stability checks with dynamic content detection
            stability_checks = 0
            max_stability_checks = 4  # Increased for better accuracy
            stability_interval = 1.5  # Slightly longer interval
            
            previous_content_hash = None
            previous_image_count = None
            previous_element_count = None
            
            for check in range(max_stability_checks):
                try:
                    # Check timeout
                    current_time = asyncio.get_event_loop().time()
                    if current_time - start_time > max_wait_time:
                        logger.warning(f"Page stability check timeout: {url}")
                        break
                    
                    # Wait between checks
                    await asyncio.sleep(stability_interval)
                    
                    # Check if URL changed during wait (user navigated away)
                    current_url = page.url
                    if current_url != url:
                        logger.debug(f"URL changed during stability check, aborting: {url} -> {current_url}")
                        return False
                    
                    # Enhanced page state checks
                    page_metrics = await page.evaluate('''
                        () => {
                            const body = document.body;
                            if (!body) return null;
                            
                            // Get comprehensive page metrics
                            const textContent = body.innerText || body.textContent || '';
                            const imageElements = document.querySelectorAll('img');
                            const totalElements = document.querySelectorAll('*').length;
                            
                            // Count loaded images
                            let loadedImages = 0;
                            imageElements.forEach(img => {
                                if (img.complete && img.naturalHeight !== 0) {
                                    loadedImages++;
                                }
                            });
                            
                            // Check for loading indicators
                            const loadingIndicators = document.querySelectorAll(
                                '[class*="loading"], [class*="spinner"], [class*="skeleton"], .loading, .spinner'
                            ).length;
                            
                            // Check for AJAX activity indicators
                            const ajaxIndicators = document.querySelectorAll(
                                '[aria-busy="true"], [data-loading="true"], .ajax-loading'
                            ).length;
                            
                            return {
                                readyState: document.readyState,
                                textContent: textContent.substring(0, 1500),  // Increased sample size
                                imageCount: imageElements.length,
                                loadedImages: loadedImages,
                                totalElements: totalElements,
                                loadingIndicators: loadingIndicators,
                                ajaxIndicators: ajaxIndicators,
                                scrollHeight: document.documentElement.scrollHeight,
                                hasVisibleContent: textContent.trim().length > 50
                            };
                        }
                    ''')
                    
                    if not page_metrics:
                        logger.debug(f"No page metrics available, continuing: {url}")
                        continue
                    
                    # Check if page is still loading
                    if page_metrics['readyState'] not in ['interactive', 'complete']:
                        logger.debug(f"Page still loading (readyState: {page_metrics['readyState']}): {url}")
                        continue
                    
                    # Check for active loading indicators
                    if page_metrics['loadingIndicators'] > 0 or page_metrics['ajaxIndicators'] > 0:
                        logger.debug(f"Loading indicators detected ({page_metrics['loadingIndicators']} loading, {page_metrics['ajaxIndicators']} ajax): {url}")
                        stability_checks = 0  # Reset counter
                        continue
                    
                    # Enhanced content stability check
                    content_hash = hashlib.md5(str(page_metrics['textContent']).encode()).hexdigest()
                    image_count = page_metrics['imageCount']
                    element_count = page_metrics['totalElements']
                    
                    # Check if content has meaningful data
                    if not page_metrics['hasVisibleContent']:
                        logger.debug(f"Insufficient visible content, waiting: {url}")
                        continue
                    
                    # Compare with previous state
                    content_stable = (previous_content_hash == content_hash) if previous_content_hash else False
                    images_stable = (previous_image_count == image_count) if previous_image_count is not None else False
                    elements_stable = (previous_element_count == element_count) if previous_element_count is not None else False
                    
                    # Update previous state
                    if previous_content_hash is None:
                        previous_content_hash = content_hash
                        previous_image_count = image_count
                        previous_element_count = element_count
                        logger.debug(f"Initial page metrics recorded: {url} (elements: {element_count}, images: {image_count})")
                        continue
                    
                    # Check stability
                    if content_stable and images_stable and elements_stable:
                        stability_checks += 1
                        logger.debug(f"Page stable (check {stability_checks}/{max_stability_checks}): {url}")
                        
                        # Additional check: ensure images are loaded
                        if image_count > 0:
                            image_load_ratio = page_metrics['loadedImages'] / image_count
                            if image_load_ratio < 0.8:  # At least 80% of images should be loaded
                                logger.debug(f"Images still loading ({page_metrics['loadedImages']}/{image_count}): {url}")
                                stability_checks = max(0, stability_checks - 1)  # Reduce stability
                                continue
                        
                        # If we have enough stable checks, consider page stable
                        if stability_checks >= 2:  # At least 2 consecutive stable checks
                            logger.info(f"Page is stable and ready for crawling: {url} (final metrics: elements={element_count}, images={image_count}/{page_metrics['loadedImages']})")
                            return True
                    else:
                        # Content changed, reset stability counter
                        stability_checks = 0
                        previous_content_hash = content_hash
                        previous_image_count = image_count
                        previous_element_count = element_count
                        logger.debug(f"Page content changed, resetting stability: {url} (content: {content_stable}, images: {images_stable}, elements: {elements_stable})")
                    
                except Exception as e:
                    logger.warning(f"Error during enhanced stability check {check}: {e}")
                    continue
            
            # Final fallback check
            try:
                final_metrics = await page.evaluate('''
                    () => ({
                        readyState: document.readyState,
                        hasContent: (document.body?.innerText || '').trim().length > 50,
                        loadingIndicators: document.querySelectorAll('[class*="loading"], [class*="spinner"]').length
                    })
                ''')
                
                if (final_metrics['readyState'] == 'complete' and 
                    final_metrics['hasContent'] and 
                    final_metrics['loadingIndicators'] == 0):
                    logger.info(f"Page meets final stability criteria: {url}")
                    return True
                else:
                    logger.warning(f"Page failed final stability check: {url} (readyState: {final_metrics['readyState']}, hasContent: {final_metrics['hasContent']}, loading: {final_metrics['loadingIndicators']})")
                    return False
                    
            except Exception as e:
                logger.error(f"Error in final stability check: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in enhanced page stability check: {e}")
            return False
    
    async def _handle_page_loaded(self, instance_id: str, page_id: str, page: Page):
        """Handle page load event"""
        try:
            # Update page state
            if instance_id in self.tab_states and page_id in self.tab_states[instance_id]:
                self.tab_states[instance_id][page_id].update({
                    "url": page.url,
                    "title": await page.title(),
                    "last_activity": datetime.utcnow()
                })
            
            # Check login status on page load
            await self._check_page_login_status(instance_id, page_id, page)
            
        except Exception as e:
            logger.error(f"Error handling page load: {e}")
    
    async def _sync_page_state(self, instance_id: str, page_id: str, page: Page):
        """Sync page state including cookies and storage"""
        try:
            if instance_id not in self.tab_states or page_id not in self.tab_states[instance_id]:
                return
            
            # Get cookies
            cookies = await page.context.cookies()
            
            # Get local storage and session storage
            local_storage = await page.evaluate("() => ({ ...localStorage })")
            session_storage = await page.evaluate("() => ({ ...sessionStorage })")
            
            # Update page state
            self.tab_states[instance_id][page_id].update({
                "cookies": cookies,
                "local_storage": local_storage,
                "session_storage": session_storage,
                "last_activity": datetime.utcnow()
            })
            
            # Update instance session storage
            self.session_storage[instance_id] = {
                "cookies": cookies,
                "local_storage": local_storage,
                "session_storage": session_storage
            }
            
        except Exception as e:
            logger.error(f"Error syncing page state: {e}")
    
    async def _sync_session_to_page(self, instance_id: str, page: Page):
        """Sync session data to a new page"""
        try:
            if instance_id not in self.session_storage:
                return
            
            session_data = self.session_storage[instance_id]
            
            # Set cookies
            if "cookies" in session_data and session_data["cookies"]:
                await page.context.add_cookies(session_data["cookies"])
            
            # Set local storage
            if "local_storage" in session_data and session_data["local_storage"]:
                for key, value in session_data["local_storage"].items():
                    await page.evaluate(f"localStorage.setItem('{key}', '{value}')")
            
            # Set session storage
            if "session_storage" in session_data and session_data["session_storage"]:
                for key, value in session_data["session_storage"].items():
                    await page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
            
            logger.debug(f"Session data synced to new page for instance {instance_id}")
            
        except Exception as e:
            logger.error(f"Error syncing session to page: {e}")
    
    async def _periodic_tab_sync(self):
        """Periodically sync tab states across all instances"""
        while True:
            try:
                await asyncio.sleep(60)  # Sync every minute
                
                for instance_id in list(self.tab_states.keys()):
                    if instance_id in self.browsers:
                        await self._sync_all_tabs(instance_id)
                        
            except Exception as e:
                logger.error(f"Error in periodic tab sync: {e}")
    
    async def _sync_all_tabs(self, instance_id: str):
        """Sync all tabs for a specific instance"""
        try:
            if instance_id not in self.tab_states:
                return
            
            # Get all pages for this instance
            instance_pages = {k: v for k, v in self.pages.items() if k.startswith(instance_id)}
            
            for page_id, page in instance_pages.items():
                if not page.is_closed():
                    await self._sync_page_state(instance_id, page_id, page)
            
        except Exception as e:
            logger.error(f"Error syncing all tabs for {instance_id}: {e}")
    
    async def _check_page_login_status(self, instance_id: str, page_id: str, page: Page):
        """Check login status for a specific page"""
        try:
            # Use existing login detection logic but for specific page
            platform = "unknown"
            if instance_id in self.browsers:
                # Get platform from instance data
                instance_data = await self.db.browser_instances.find_one({"instance_id": instance_id})
                if instance_data:
                    platform = instance_data.get("platform", "unknown")
            
            # Get platform-specific selectors
            config = self.platform_configs.get(platform, {})
            logged_in_selectors = config.get("logged_in_selectors", [])
            login_selectors = config.get("login_selectors", [])
            
            is_logged_in = False
            login_user = None
            detection_method = "none"
            
            # Check for logged-in indicators
            for selector in logged_in_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_logged_in = True
                        detection_method = f"logged_in_selector: {selector}"
                        text_content = await element.text_content()
                        if text_content and text_content.strip():
                            login_user = text_content.strip()
                        break
                except Exception:
                    continue
            
            # Update page state with login status
            if instance_id in self.tab_states and page_id in self.tab_states[instance_id]:
                self.tab_states[instance_id][page_id]["login_status"] = {
                    "is_logged_in": is_logged_in,
                    "login_user": login_user,
                    "detection_method": detection_method,
                    "timestamp": datetime.utcnow()
                }
            
        except Exception as e:
            logger.error(f"Error checking page login status: {e}")
    
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
                            # Get instance data to check for status changes
                            instance_data = await self.db.browser_instances.find_one({
                                "instance_id": instance_id,
                                "is_active": True
                            })
                            
                            if instance_data:
                                platform = instance_data.get("platform", "unknown")
                                
                                # Use the existing _check_and_notify_status_change method
                                # This method properly handles status change detection and notifications
                                await self._check_and_notify_status_change(instance_id, platform, login_status)
                                
                                logger.debug(f"Checked login status for instance {instance_id}: {login_status['is_logged_in']}")
                    
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
        async with self._cleanup_lock:
            try:
                # Disable login detection
                self.login_detection_enabled = False
                
                # Close all browser instances safely
                for instance_id in list(self.browsers.keys()):
                    try:
                        await self.close_browser_instance(instance_id)
                    except Exception as e:
                        logger.warning(f"Error closing instance {instance_id} during shutdown: {e}")
                
                # Clear all locks
                self._instance_locks.clear()
                
                # Stop Playwright
                if self.playwright:
                    try:
                        await self.playwright.stop()
                    except Exception as e:
                        logger.warning(f"Error stopping playwright: {e}")
                    finally:
                        self.playwright = None
                        
                logger.info("Browser manager shutdown completed")
                
            except Exception as e:
                logger.error(f"Error during browser manager shutdown: {e}")
    
    async def _periodic_crawled_urls_cleanup(self):
        """Periodically clean up expired crawled URLs"""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                current_time = time.time()
                expired_urls = []
                
                # Find expired URLs (older than 5 minutes)
                for url, data in list(self.crawled_urls.items()):
                    if current_time - data.get("timestamp", 0) > 300:  # 5 minutes
                        expired_urls.append(url)
                
                # Remove expired URLs
                for url in expired_urls:
                    del self.crawled_urls[url]
                
                if expired_urls:
                    logger.debug(f"Cleaned up {len(expired_urls)} expired crawled URLs")
                    
            except Exception as e:
                logger.error(f"Error in periodic crawled URLs cleanup: {e}")
    
    async def _capture_page_screenshot(self, page: Page, full_page: bool = True) -> bytes:
        """Capture screenshot of the current page"""
        try:
            screenshot_options = {
                "full_page": full_page,
                "type": "png",
                "quality": 90
            }
            
            # Wait for page to be stable
            await page.wait_for_load_state("networkidle", timeout=5000)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(**screenshot_options)
            
            logger.debug(f"Screenshot captured, size: {len(screenshot_bytes)} bytes")
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return b""
    
    async def _analyze_screenshot_content(self, screenshot_bytes: bytes, url: str) -> dict:
        """Analyze screenshot to extract content indicators with enhanced visual analysis"""
        try:
            if not screenshot_bytes:
                return {"confidence": 0.0, "indicators": [], "analysis": "No screenshot data"}
            
            analysis = {
                "confidence": 0.4,  # Base confidence for having screenshot
                "indicators": [],
                "analysis": "Screenshot captured successfully",
                "screenshot_size": len(screenshot_bytes),
                "timestamp": datetime.utcnow().isoformat(),
                "visual_features": {}
            }
            
            # Enhanced URL-based content detection
            url_indicators = await self._analyze_screenshot_url_patterns(url)
            analysis["confidence"] += url_indicators["confidence_boost"]
            analysis["indicators"].extend(url_indicators["indicators"])
            
            # Platform-specific screenshot analysis
            platform_analysis = await self._analyze_platform_screenshot_features(screenshot_bytes, url)
            analysis["confidence"] += platform_analysis["confidence_boost"]
            analysis["indicators"].extend(platform_analysis["indicators"])
            analysis["visual_features"].update(platform_analysis["features"])
            
            # Basic image analysis (size, format validation)
            image_analysis = await self._analyze_screenshot_image_properties(screenshot_bytes)
            analysis["confidence"] += image_analysis["confidence_boost"]
            analysis["indicators"].extend(image_analysis["indicators"])
            analysis["visual_features"].update(image_analysis["features"])
            
            # Cap confidence at 1.0
            analysis["confidence"] = min(analysis["confidence"], 1.0)
            
            logger.debug(f"Enhanced screenshot analysis completed with confidence: {analysis['confidence']:.2f}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}")
            return {"confidence": 0.0, "indicators": [], "analysis": f"Analysis error: {str(e)}"}
    
    async def _extract_content_with_screenshot(self, page: Page, url: str) -> dict:
        """Extract content using enhanced DOM analysis and intelligent screenshot processing"""
        try:
            # Capture high-quality screenshot
            screenshot_bytes = await self._capture_page_screenshot(page, full_page=True)
            
            # Enhanced screenshot analysis with visual intelligence
            screenshot_analysis = await self._analyze_screenshot_content(screenshot_bytes, url)
            
            # Enhanced page content analysis
            page_analysis = await self._analyze_page_content(page, url)
            
            # Intelligent confidence weighting based on platform and content type
            platform_weight = await self._get_platform_analysis_weight(url)
            dom_weight = platform_weight.get("dom_weight", 0.7)
            screenshot_weight = platform_weight.get("screenshot_weight", 0.3)
            
            # Calculate weighted combined confidence
            combined_confidence = (
                page_analysis.get("confidence", 0.0) * dom_weight +
                screenshot_analysis.get("confidence", 0.0) * screenshot_weight
            )
            
            # Smart indicator combination with deduplication
            combined_indicators = list(set(
                page_analysis.get("indicators", []) + 
                screenshot_analysis.get("indicators", [])
            ))
            
            # Enhanced content extraction with screenshot data
            extracted_content = await self._extract_screenshot_content_data(screenshot_bytes, page, url)
            
            result = {
                "is_content_page": combined_confidence > 0.6,
                "confidence": combined_confidence,
                "indicators": combined_indicators,
                "dom_analysis": page_analysis,
                "screenshot_analysis": screenshot_analysis,
                "extracted_content": extracted_content,
                "screenshot_available": len(screenshot_bytes) > 0,
                "screenshot_size": len(screenshot_bytes),
                "platform_weights": platform_weight,
                "extraction_method": "enhanced_dom_screenshot",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Enhanced content extraction completed for {url}: confidence={combined_confidence:.2f}, is_content={result['is_content_page']}, screenshot_size={len(screenshot_bytes)}")
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced content extraction with screenshot: {e}")
            return {
                "is_content_page": False,
                "confidence": 0.0,
                "indicators": [],
                "error": str(e),
                "extraction_method": "error",
                "timestamp": datetime.utcnow().isoformat()
            }