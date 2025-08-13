# Database Models for Login State Management
# Defines data structures and validation schemas

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

class PlatformType(str, Enum):
    """Supported platform types"""
    WEIBO = "weibo"
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    BILIBILI = "bilibili"
    ZHIHU = "zhihu"
    CUSTOM = "custom"

class SessionStatus(str, Enum):
    """Session status types"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    LOGGED_OUT = "logged_out"

class BrowserInstanceStatus(str, Enum):
    """Browser instance status types"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    CLOSED = "closed"

class CrawlTaskStatus(str, Enum):
    """Crawl task status types"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Request/Response Models

class CreateSessionRequest(BaseModel):
    """Request model for creating a new session"""
    user_id: str = Field(..., description="User identifier")
    platform: PlatformType = Field(..., description="Target platform")
    headless: bool = Field(default=False, description="Whether to run browser in headless mode")
    browser_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom browser configuration")
    session_timeout_hours: int = Field(default=24, ge=1, le=168, description="Session timeout in hours")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('User ID cannot be empty')
        return v.strip()

class SessionResponse(BaseModel):
    """Response model for session information"""
    session_id: str
    user_id: str
    platform: PlatformType
    is_active: bool
    is_logged_in: bool
    login_user: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    browser_instances: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UpdateSessionRequest(BaseModel):
    """Request model for updating session"""
    is_logged_in: Optional[bool] = None
    login_user: Optional[str] = None
    extend_hours: Optional[int] = Field(default=None, ge=1, le=168)
    metadata: Optional[Dict[str, Any]] = None

class CreateBrowserInstanceRequest(BaseModel):
    """Request model for creating browser instance"""
    session_id: str = Field(..., description="Session identifier")
    headless: bool = Field(default=False, description="Whether to run browser in headless mode")
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom browser configuration")
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Session ID cannot be empty')
        return v.strip()

class BrowserInstanceResponse(BaseModel):
    """Response model for browser instance information"""
    instance_id: str
    session_id: str
    platform: PlatformType
    is_active: bool
    headless: bool
    user_data_dir: str
    page_count: int
    current_url: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    memory_usage: Dict[str, Any] = Field(default_factory=dict)

class NavigateRequest(BaseModel):
    """Request model for browser navigation"""
    url: str = Field(..., description="Target URL")
    wait_for: str = Field(default="networkidle", description="Wait condition")
    timeout: int = Field(default=30000, ge=5000, le=120000, description="Timeout in milliseconds")
    
    @validator('url')
    def validate_url(cls, v):
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class ExecuteScriptRequest(BaseModel):
    """Request model for script execution"""
    script: str = Field(..., description="JavaScript code to execute")
    timeout: int = Field(default=10000, ge=1000, le=60000, description="Timeout in milliseconds")
    
    @validator('script')
    def validate_script(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Script cannot be empty')
        return v.strip()

class CookieData(BaseModel):
    """Cookie data model"""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[float] = None
    httpOnly: bool = False
    secure: bool = False
    sameSite: Optional[str] = None

class SaveCookiesRequest(BaseModel):
    """Request model for saving cookies"""
    session_id: str = Field(..., description="Session identifier")
    cookies: List[CookieData] = Field(..., description="Cookie data")
    
    @validator('cookies')
    def validate_cookies(cls, v):
        if not v:
            raise ValueError('Cookies list cannot be empty')
        return v

class ManualCrawlRequest(BaseModel):
    """Request model for manual crawl"""
    session_id: str = Field(..., description="Session identifier")
    url: str = Field(..., description="Target URL")
    extract_content: bool = Field(default=True, description="Whether to extract content")
    extract_links: bool = Field(default=True, description="Whether to extract links")
    extract_images: bool = Field(default=False, description="Whether to extract images")
    custom_selectors: Optional[Dict[str, str]] = Field(default=None, description="Custom CSS selectors")
    wait_time: int = Field(default=3, ge=0, le=30, description="Wait time in seconds")
    scroll_to_bottom: bool = Field(default=False, description="Whether to scroll to bottom")
    
    @validator('url')
    def validate_url(cls, v):
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class CrawlResult(BaseModel):
    """Crawl result model"""
    task_id: str
    session_id: str
    url: str
    status: CrawlTaskStatus
    title: Optional[str] = None
    content: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None

class PlatformConfig(BaseModel):
    """Platform configuration model"""
    platform: PlatformType
    name: str
    base_url: str
    login_url: str
    login_selectors: Dict[str, str] = Field(default_factory=dict)
    browser_config: Dict[str, Any] = Field(default_factory=dict)
    crawl_config: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

# Database Collection Schemas

class SessionDocument(BaseModel):
    """Session document schema for MongoDB"""
    session_id: str
    user_id: str
    platform: str
    is_active: bool = True
    is_logged_in: bool = False
    login_user: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    browser_config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BrowserInstanceDocument(BaseModel):
    """Browser instance document schema for MongoDB"""
    instance_id: str
    session_id: str
    platform: str
    user_data_dir: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    page_count: int = 1
    memory_usage: Dict[str, Any] = Field(default_factory=dict)
    closed_at: Optional[datetime] = None

class CookieDocument(BaseModel):
    """Cookie document schema for MongoDB"""
    cookie_id: str
    session_id: str
    platform: str
    domain: str
    encrypted_data: str  # Encrypted cookie data
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: datetime
    is_active: bool = True

class CrawlTaskDocument(BaseModel):
    """Crawl task document schema for MongoDB"""
    task_id: str
    session_id: str
    user_id: str
    platform: str
    url: str
    request_data: Dict[str, Any] = Field(default_factory=dict)
    status: str = CrawlTaskStatus.PENDING
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

class PlatformConfigDocument(BaseModel):
    """Platform configuration document schema for MongoDB"""
    platform: str
    name: str
    base_url: str
    login_url: str
    login_selectors: Dict[str, str] = Field(default_factory=dict)
    browser_config: Dict[str, Any] = Field(default_factory=dict)
    crawl_config: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

# Statistics Models

class SessionStats(BaseModel):
    """Session statistics model"""
    total_sessions: int = 0
    active_sessions: int = 0
    logged_in_sessions: int = 0
    platform_stats: Dict[str, Dict[str, int]] = Field(default_factory=dict)

class BrowserInstanceStats(BaseModel):
    """Browser instance statistics model"""
    total_instances: int = 0
    active_instances: int = 0
    memory_cached_instances: int = 0
    platform_stats: Dict[str, Dict[str, int]] = Field(default_factory=dict)

class CrawlTaskStats(BaseModel):
    """Crawl task statistics model"""
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    platform_stats: Dict[str, Dict[str, int]] = Field(default_factory=dict)

class SystemStats(BaseModel):
    """System statistics model"""
    sessions: SessionStats
    browser_instances: BrowserInstanceStats
    crawl_tasks: CrawlTaskStats
    uptime: float
    memory_usage: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

# Error Models

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ValidationError(BaseModel):
    """Validation error model"""
    field: str
    message: str
    value: Any

# Success Response Models

class SuccessResponse(BaseModel):
    """Generic success response model"""
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ListResponse(BaseModel):
    """List response model with pagination"""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
    has_next: bool = False
    has_prev: bool = False

# Database Index Definitions

DATABASE_INDEXES = {
    "sessions": [
        {"keys": [("session_id", 1)], "unique": True},
        {"keys": [("user_id", 1), ("platform", 1)]},
        {"keys": [("is_active", 1), ("expires_at", 1)]},
        {"keys": [("platform", 1), ("is_logged_in", 1)]},
        {"keys": [("created_at", -1)]}
    ],
    "browser_instances": [
        {"keys": [("instance_id", 1)], "unique": True},
        {"keys": [("session_id", 1)]},
        {"keys": [("platform", 1), ("is_active", 1)]},
        {"keys": [("is_active", 1), ("expires_at", 1)]},
        {"keys": [("last_activity", 1)]}
    ],
    "cookie_data": [
        {"keys": [("cookie_id", 1)], "unique": True},
        {"keys": [("session_id", 1), ("domain", 1)]},
        {"keys": [("platform", 1), ("domain", 1)]},
        {"keys": [("is_active", 1), ("expires_at", 1)]},
        {"keys": [("created_at", -1)]}
    ],
    "crawl_tasks": [
        {"keys": [("task_id", 1)], "unique": True},
        {"keys": [("session_id", 1), ("status", 1)]},
        {"keys": [("user_id", 1), ("platform", 1)]},
        {"keys": [("status", 1), ("created_at", -1)]},
        {"keys": [("created_at", -1)]}
    ],
    "platform_configs": [
        {"keys": [("platform", 1)], "unique": True},
        {"keys": [("is_enabled", 1)]}
    ]
}

# Default Platform Configurations

DEFAULT_PLATFORM_CONFIGS = [
    {
        "platform": "weibo",
        "name": "新浪微博",
        "base_url": "https://weibo.com",
        "login_url": "https://passport.weibo.cn/signin/login",
        "login_selectors": {
            "username": "input[name='username']",
            "password": "input[name='password']",
            "submit": "a[action-type='btn_submit']",
            "captcha": "input[name='verifycode']"
        },
        "browser_config": {
            "headless": False,
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "crawl_config": {
            "wait_time": 3,
            "scroll_pause_time": 1,
            "max_scroll_attempts": 5
        },
        "is_enabled": True
    },
    {
        "platform": "xiaohongshu",
        "name": "小红书",
        "base_url": "https://www.xiaohongshu.com",
        "login_url": "https://www.xiaohongshu.com/login",
        "login_selectors": {
            "phone": "input[placeholder*='手机号']",
            "password": "input[type='password']",
            "submit": "button[type='submit']",
            "sms_code": "input[placeholder*='验证码']"
        },
        "browser_config": {
            "headless": False,
            "viewport": {"width": 1366, "height": 768},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "crawl_config": {
            "wait_time": 2,
            "scroll_pause_time": 1.5,
            "max_scroll_attempts": 3
        },
        "is_enabled": True
    },
    {
        "platform": "douyin",
        "name": "抖音",
        "base_url": "https://www.douyin.com",
        "login_url": "https://www.douyin.com/passport/web/login",
        "login_selectors": {
            "phone": "input[placeholder*='手机号']",
            "sms_code": "input[placeholder*='验证码']",
            "submit": "button[type='submit']"
        },
        "browser_config": {
            "headless": False,
            "viewport": {"width": 1440, "height": 900},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "crawl_config": {
            "wait_time": 4,
            "scroll_pause_time": 2,
            "max_scroll_attempts": 8
        },
        "is_enabled": True
    }
]