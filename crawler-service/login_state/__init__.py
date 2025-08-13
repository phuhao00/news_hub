# Login State Management Package
# Provides session management, browser instance management, and cookie storage for crawler service

"""
Login State Management Package for NewsHub Crawler Service

This package provides comprehensive login state management functionality including:
- Session management across different platforms
- Browser instance management with Playwright
- Encrypted cookie storage and retrieval
- Manual crawl triggering for logged-in websites
- REST API endpoints for frontend integration

Main Components:
- SessionManager: Manages user sessions with Redis caching and MongoDB persistence
- BrowserInstanceManager: Manages Playwright browser instances with session persistence
- CookieStore: Provides encrypted storage and retrieval of cookie data
- DatabaseManager: Handles database initialization and management
- API Router: REST endpoints for all login state management operations

Usage:
    from login_state import initialize_managers, router
    from login_state.api import initialize_managers
    
    # Initialize managers
    initialize_managers(db, redis_client)
    
    # Add API routes
    app.include_router(router)
"""

from .session_manager import SessionManager
from .browser_manager import BrowserInstanceManager
from .cookie_store import CookieStore
from .database import DatabaseManager, create_database_manager
from .api import router, initialize_managers, shutdown_managers
from .models import (
    PlatformType,
    SessionStatus,
    BrowserInstanceStatus,
    CrawlTaskStatus,
    CreateSessionRequest,
    SessionResponse,
    UpdateSessionRequest,
    CreateBrowserInstanceRequest,
    BrowserInstanceResponse,
    NavigateRequest,
    ExecuteScriptRequest,
    SaveCookiesRequest,
    ManualCrawlRequest,
    CrawlResult,
    SuccessResponse,
    ErrorResponse,
    ListResponse
)

__version__ = "1.0.0"
__author__ = "NewsHub Team"
__description__ = "Login State Management for NewsHub Crawler Service"

# Export main components
__all__ = [
    # Core managers
    "SessionManager",
    "BrowserInstanceManager", 
    "CookieStore",
    "DatabaseManager",
    "create_database_manager",
    
    # API components
    "router",
    "initialize_managers",
    "shutdown_managers",
    
    # Models and types
    "PlatformType",
    "SessionStatus",
    "BrowserInstanceStatus",
    "CrawlTaskStatus",
    "CreateSessionRequest",
    "SessionResponse",
    "UpdateSessionRequest",
    "CreateBrowserInstanceRequest",
    "BrowserInstanceResponse",
    "NavigateRequest",
    "ExecuteScriptRequest",
    "SaveCookiesRequest",
    "ManualCrawlRequest",
    "CrawlResult",
    "SuccessResponse",
    "ErrorResponse",
    "ListResponse",
    
    # Package info
    "__version__",
    "__author__",
    "__description__"
]

# Package-level configuration
DEFAULT_CONFIG = {
    "session_timeout_hours": 24,
    "browser_instance_timeout_hours": 2,
    "cookie_expiry_days": 30,
    "max_instances_per_platform": 5,
    "max_total_instances": 20,
    "cleanup_interval_minutes": 5,
    "redis_key_prefix": "newshub:login_state",
    "encryption_algorithm": "Fernet",
    "supported_platforms": [
        "weibo",
        "xiaohongshu", 
        "douyin",
        "bilibili",
        "zhihu"
    ]
}

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "login_state": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False
        }
    }
}

def get_package_info():
    """Get package information"""
    return {
        "name": "login_state",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "components": [
            "SessionManager",
            "BrowserInstanceManager",
            "CookieStore",
            "DatabaseManager",
            "API Router"
        ],
        "supported_platforms": DEFAULT_CONFIG["supported_platforms"]
    }

def get_default_config():
    """Get default configuration"""
    return DEFAULT_CONFIG.copy()