# API Routes for Login State Management
# Implements REST endpoints for session, browser, and cookie management

import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Header, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as aioredis

from .models import (
    CreateSessionRequest, SessionResponse, UpdateSessionRequest,
    CreateBrowserInstanceRequest, BrowserInstanceResponse,
    NavigateRequest, ExecuteScriptRequest, SaveCookiesRequest,
    ManualCrawlRequest, CrawlResult, PlatformType, CrawlTaskStatus,
    SuccessResponse, ErrorResponse, ListResponse,
    SessionStats, BrowserInstanceStats, SystemStats
)
from .session_manager import SessionManager
from .browser_manager import BrowserInstanceManager
from .cookie_store import CookieStore
from .database import DatabaseManager
from .manual_crawl import ManualCrawlService

logger = logging.getLogger(__name__)

# Global managers (will be initialized in main.py)
session_manager: Optional[SessionManager] = None
browser_manager: Optional[BrowserInstanceManager] = None
cookie_store: Optional[CookieStore] = None
db_manager: Optional[DatabaseManager] = None
manual_crawl_service: Optional[ManualCrawlService] = None

def get_session_manager() -> SessionManager:
    """Dependency to get session manager"""
    if session_manager is None:
        raise HTTPException(status_code=500, detail="Session manager not initialized")
    return session_manager

def get_browser_manager() -> BrowserInstanceManager:
    """Dependency to get browser manager"""
    if browser_manager is None:
        raise HTTPException(status_code=500, detail="Browser manager not initialized")
    return browser_manager

def get_cookie_store() -> CookieStore:
    """Dependency to get cookie store"""
    if cookie_store is None:
        raise HTTPException(status_code=500, detail="Cookie store not initialized")
    return cookie_store

def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager"""
    if db_manager is None:
        raise HTTPException(status_code=500, detail="Database manager not initialized")
    return db_manager

def get_manual_crawl_service() -> ManualCrawlService:
    """Dependency to get manual crawl service"""
    if manual_crawl_service is None:
        raise HTTPException(status_code=500, detail="Manual crawl service not initialized")
    return manual_crawl_service

# Create API router
router = APIRouter(prefix="/api/login-state", tags=["Login State Management"])

# Session Management Endpoints

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    sm: SessionManager = Depends(get_session_manager)
):
    """Create a new login session"""
    try:
        session_data = await sm.create_session(
            user_id=request.user_id,
            platform=request.platform.value,
            browser_config=request.browser_config
        )
        # 合并传入的 metadata（例如 platform_alias），以便前端展示与后续逻辑使用
        if request.metadata:
            from copy import deepcopy
            merged = deepcopy(session_data.get("metadata", {}))
            merged.update(request.metadata)
            session_data["metadata"] = merged
            # 立即持久化到数据库
            await sm.db.sessions.update_one({"session_id": session_data["session_id"]}, {"$set": {"metadata": merged}})
        
        # Extend session if custom timeout is specified
        if request.session_timeout_hours != 24:
            await sm.extend_session(session_data["session_id"], request.session_timeout_hours)
            session_data["expires_at"] = datetime.utcnow() + timedelta(hours=request.session_timeout_hours)
        
        return SessionResponse(**session_data)
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    check_login: bool = Query(False, description="Whether to check current login status"),
    sm: SessionManager = Depends(get_session_manager),
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Get session information"""
    try:
        # Validate session with optional login status check
        session_data = await sm.validate_session(session_id, check_login_status=check_login)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Get browser instances for this session
        browser_instances = await bm.get_session_instances(session_id)
        session_data["browser_instances"] = [inst["instance_id"] for inst in browser_instances]
        
        return SessionResponse(**session_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/sessions/{session_id}", response_model=SuccessResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    sm: SessionManager = Depends(get_session_manager)
):
    """Update session information"""
    try:
        # Validate session exists
        session_data = await sm.validate_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Update login status if provided
        if request.is_logged_in is not None:
            success = await sm.update_login_status(
                session_id=session_id,
                is_logged_in=request.is_logged_in,
                login_user=request.login_user,
                metadata=request.metadata
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update login status")
        
        # Extend session if requested
        if request.extend_hours:
            success = await sm.extend_session(session_id, request.extend_hours)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to extend session")
        
        return SuccessResponse(message="Session updated successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Delete a session and its associated browser instances"""
    try:
        # Close all browser instances for this session
        browser_instances = await bm.get_session_instances(session_id)
        for instance in browser_instances:
            await bm.close_browser_instance(instance["instance_id"])
        
        # Delete session
        success = await sm.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SuccessResponse(message="Session deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=ListResponse)
async def list_user_sessions(
    user_id: str,
    platform: Optional[str] = None,
    sm: SessionManager = Depends(get_session_manager)
):
    """List sessions for a user"""
    try:
        sessions = await sm.get_user_sessions(user_id, platform)
        
        return ListResponse(
            items=sessions,
            total=len(sessions),
            page=1,
            page_size=len(sessions)
        )
        
    except Exception as e:
        logger.error(f"Failed to list sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/check-login", response_model=dict)
async def check_session_login_status(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Check login status for a session by examining its browser instances"""
    try:
        # Validate session exists
        session_data = await sm.validate_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Get browser instances for this session
        browser_instances = await bm.get_session_instances(session_id)
        
        if not browser_instances:
            return {
                "session_id": session_id,
                "is_logged_in": False,
                "message": "No browser instances found for this session",
                "timestamp": datetime.utcnow()
            }
        
        # Check login status for each browser instance
        login_results = []
        overall_logged_in = False
        
        for instance in browser_instances:
            instance_id = instance["instance_id"]
            login_status = await bm.check_login_status(instance_id)
            login_results.append({
                "instance_id": instance_id,
                "platform": instance.get("platform"),
                **login_status
            })
            
            if login_status.get("is_logged_in", False):
                overall_logged_in = True
        
        # Update session login status if changed
        if overall_logged_in != session_data.get("is_logged_in", False):
            await sm.update_login_status(
                session_id=session_id,
                is_logged_in=overall_logged_in,
                login_user=next((r.get("login_user") for r in login_results if r.get("login_user")), None)
            )
        
        return {
            "session_id": session_id,
            "is_logged_in": overall_logged_in,
            "browser_instances": login_results,
            "timestamp": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check login status for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Browser Instance Management Endpoints

@router.post("/browser-instances", response_model=BrowserInstanceResponse)
async def create_browser_instance(
    request: CreateBrowserInstanceRequest,
    bm: BrowserInstanceManager = Depends(get_browser_manager),
    sm: SessionManager = Depends(get_session_manager)
):
    """Create a new browser instance"""
    try:
        # Validate session
        session_data = await sm.validate_session(request.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Create browser instance
        instance_data = await bm.create_browser_instance(
            session_id=request.session_id,
            platform=session_data["platform"],
            headless=request.headless,
            custom_config=request.custom_config
        )
        
        return BrowserInstanceResponse(
            instance_id=instance_data["instance_id"],
            session_id=instance_data["session_id"],
            platform=instance_data["platform"],
            is_active=True,
            headless=instance_data["headless"],
            user_data_dir=instance_data["user_data_dir"],
            page_count=1,
            current_url=instance_data.get("page_url"),
            created_at=instance_data["created_at"],
            last_activity=instance_data["created_at"],
            expires_at=instance_data["expires_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create browser instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/browser-instances/{instance_id}", response_model=BrowserInstanceResponse)
async def get_browser_instance(
    instance_id: str,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Get browser instance information"""
    try:
        instance_data = await bm.get_browser_instance(instance_id)
        if not instance_data:
            raise HTTPException(status_code=404, detail="Browser instance not found or expired")
        
        return BrowserInstanceResponse(**instance_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser-instances/{instance_id}/navigate", response_model=SuccessResponse)
async def navigate_browser(
    instance_id: str,
    request: NavigateRequest,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Navigate browser instance to a URL"""
    try:
        page_info = await bm.navigate_to_url(
            instance_id=instance_id,
            url=request.url,
            wait_for=request.wait_for
        )
        
        return SuccessResponse(
            message="Navigation completed successfully",
            data=page_info
        )
        
    except Exception as e:
        logger.error(f"Failed to navigate browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser-instances/{instance_id}/execute-script", response_model=SuccessResponse)
async def execute_script(
    instance_id: str,
    request: ExecuteScriptRequest,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Execute JavaScript in browser instance"""
    try:
        result = await bm.execute_script(instance_id, request.script)
        
        return SuccessResponse(
            message="Script executed successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Failed to execute script in browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser-instances/{instance_id}/screenshot", response_model=SuccessResponse)
async def take_screenshot(
    instance_id: str,
    full_page: bool = False,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Take screenshot of browser instance"""
    try:
        screenshot_path = await bm.take_screenshot(instance_id, full_page)
        
        return SuccessResponse(
            message="Screenshot taken successfully",
            data={"screenshot_path": screenshot_path}
        )
        
    except Exception as e:
        logger.error(f"Failed to take screenshot of browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/browser-instances/{instance_id}", response_model=SuccessResponse)
async def close_browser_instance(
    instance_id: str,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Close a browser instance"""
    try:
        success = await bm.close_browser_instance(instance_id)
        if not success:
            raise HTTPException(status_code=404, detail="Browser instance not found")
        
        return SuccessResponse(message="Browser instance closed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/browser-instances", response_model=ListResponse)
async def list_session_browser_instances(
    session_id: str,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """List browser instances for a session"""
    try:
        instances = await bm.get_session_instances(session_id)
        
        return ListResponse(
            items=instances,
            total=len(instances),
            page=1,
            page_size=len(instances)
        )
        
    except Exception as e:
        logger.error(f"Failed to list browser instances for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Cookie Management Endpoints

@router.get("/browser-instances/{instance_id}/cookies", response_model=SuccessResponse)
async def get_browser_cookies(
    instance_id: str,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Get cookies from browser instance"""
    try:
        cookies = await bm.get_cookies(instance_id)
        
        return SuccessResponse(
            message="Cookies retrieved successfully",
            data={"cookies": cookies}
        )
        
    except Exception as e:
        logger.error(f"Failed to get cookies from browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser-instances/{instance_id}/cookies", response_model=SuccessResponse)
async def set_browser_cookies(
    instance_id: str,
    request: SaveCookiesRequest,
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Set cookies in browser instance"""
    try:
        cookies_data = [cookie.dict() for cookie in request.cookies]
        success = await bm.set_cookies(instance_id, cookies_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set cookies")
        
        return SuccessResponse(message="Cookies set successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set cookies in browser instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cookies/save", response_model=SuccessResponse)
async def save_cookies(
    request: SaveCookiesRequest,
    cs: CookieStore = Depends(get_cookie_store),
    sm: SessionManager = Depends(get_session_manager)
):
    """Save cookies to encrypted storage"""
    try:
        # Validate session
        session_data = await sm.validate_session(request.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Save cookies
        cookies_data = [cookie.dict() for cookie in request.cookies]
        cookie_id = await cs.save_cookies(
            session_id=request.session_id,
            platform=session_data["platform"],
            cookies=cookies_data
        )
        
        return SuccessResponse(
            message="Cookies saved successfully",
            data={"cookie_id": cookie_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save cookies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cookies/{session_id}", response_model=SuccessResponse)
async def load_cookies(
    session_id: str,
    domain: Optional[str] = None,
    cs: CookieStore = Depends(get_cookie_store)
):
    """Load cookies from encrypted storage"""
    try:
        cookies = await cs.load_cookies(session_id, domain)
        
        return SuccessResponse(
            message="Cookies loaded successfully",
            data={"cookies": cookies}
        )
        
    except Exception as e:
        logger.error(f"Failed to load cookies for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cookies/{session_id}", response_model=SuccessResponse)
async def delete_cookies(
    session_id: str,
    domain: Optional[str] = None,
    cs: CookieStore = Depends(get_cookie_store)
):
    """Delete cookies from storage"""
    try:
        success = await cs.delete_cookies(session_id, domain)
        if not success:
            raise HTTPException(status_code=404, detail="Cookies not found")
        
        return SuccessResponse(message="Cookies deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete cookies for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Statistics and Monitoring Endpoints

@router.get("/stats/sessions", response_model=SessionStats)
async def get_session_stats(
    sm: SessionManager = Depends(get_session_manager)
):
    """Get session statistics"""
    try:
        stats = await sm.get_session_stats()
        return SessionStats(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get session stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/browser-instances", response_model=BrowserInstanceStats)
async def get_browser_instance_stats(
    bm: BrowserInstanceManager = Depends(get_browser_manager)
):
    """Get browser instance statistics"""
    try:
        stats = await bm.get_instance_stats()
        return BrowserInstanceStats(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get browser instance stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/system", response_model=SystemStats)
async def get_system_stats(
    sm: SessionManager = Depends(get_session_manager),
    bm: BrowserInstanceManager = Depends(get_browser_manager),
    cs: CookieStore = Depends(get_cookie_store)
):
    """Get system statistics"""
    try:
        session_stats = await sm.get_session_stats()
        browser_stats = await bm.get_instance_stats()
        cookie_stats = await cs.get_cookie_stats()
        
        import psutil
        import time
        
        # Get system info
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return SystemStats(
            sessions=SessionStats(**session_stats),
            browser_instances=BrowserInstanceStats(**browser_stats),
            crawl_tasks={"total_tasks": 0, "pending_tasks": 0, "running_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "platform_stats": {}},
            uptime=time.time() - process.create_time(),
            memory_usage={
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            },
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health Check Endpoint

@router.get("/health", response_model=SuccessResponse)
async def health_check(
    db_mgr: DatabaseManager = Depends(get_db_manager)
):
    """Health check endpoint"""
    try:
        health_status = await db_mgr.health_check()
        
        # Check if all components are healthy
        all_healthy = all(health_status.values())
        
        return SuccessResponse(
            message="Health check completed",
            data={
                "status": "healthy" if all_healthy else "unhealthy",
                "components": health_status,
                "timestamp": datetime.utcnow()
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Cleanup Endpoints

@router.post("/cleanup/expired", response_model=SuccessResponse)
async def cleanup_expired_data(
    background_tasks: BackgroundTasks,
    sm: SessionManager = Depends(get_session_manager),
    bm: BrowserInstanceManager = Depends(get_browser_manager),
    cs: CookieStore = Depends(get_cookie_store)
):
    """Clean up expired sessions, browser instances, and cookies"""
    try:
        async def cleanup_task():
            session_count = await sm.cleanup_expired_sessions()
            instance_count = await bm.cleanup_expired_instances()
            cookie_count = await cs.cleanup_expired_cookies()
            
            logger.info(f"Cleanup completed: {session_count} sessions, {instance_count} instances, {cookie_count} cookies")
        
        background_tasks.add_task(cleanup_task)
        
        return SuccessResponse(message="Cleanup task started")
        
    except Exception as e:
        logger.error(f"Failed to start cleanup task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Platform Configuration Endpoints

@router.get("/platforms", response_model=ListResponse)
async def list_platforms(
    db_mgr: DatabaseManager = Depends(get_db_manager)
):
    """List all platform configurations"""
    try:
        platforms = await db_mgr.get_all_platform_configs()
        
        return ListResponse(
            items=platforms,
            total=len(platforms),
            page=1,
            page_size=len(platforms)
        )
        
    except Exception as e:
        logger.error(f"Failed to list platforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/platforms/{platform}", response_model=SuccessResponse)
async def get_platform_config(
    platform: str,
    db_mgr: DatabaseManager = Depends(get_db_manager)
):
    """Get platform configuration"""
    try:
        config = await db_mgr.get_platform_config(platform)
        if not config:
            raise HTTPException(status_code=404, detail="Platform configuration not found")
        
        return SuccessResponse(
            message="Platform configuration retrieved successfully",
            data=config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get platform config for {platform}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Initialize managers function (to be called from main.py)
async def initialize_managers(
    db: AsyncIOMotorDatabase,
    redis_client: Optional[aioredis.Redis] = None
):
    """Initialize all managers with database and Redis connections"""
    global session_manager, browser_manager, cookie_store, db_manager, manual_crawl_service
    
    try:
        # Initialize managers
        session_manager = SessionManager(db, redis_client)
        cookie_store = CookieStore(db)
        browser_manager = BrowserInstanceManager(db, session_manager, cookie_store)  # Pass all required parameters
        
        # Initialize Playwright for browser manager
        await browser_manager.initialize()
        db_manager = DatabaseManager(db)
        
        # Initialize database
        await db_manager.initialize_database()
        
        manual_crawl_service = ManualCrawlService(db, session_manager, browser_manager, cookie_store)
        
        logger.info("Login state management API initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize login state management API: {e}")
        raise

# Shutdown function
async def shutdown_managers():
    """Shutdown all managers and cleanup resources"""
    global session_manager, browser_manager, cookie_store, db_manager, manual_crawl_service
    
    try:
        if browser_manager:
            await browser_manager.shutdown()
        
        # Reset global managers
        session_manager = None
        browser_manager = None
        cookie_store = None
        db_manager = None
        manual_crawl_service = None
        
        logger.info("Login state management API shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during login state management API shutdown: {e}")

# Notification Endpoints

@router.get("/notifications/{user_id}", response_model=ListResponse)
async def get_user_notifications(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    sm: SessionManager = Depends(get_session_manager)
):
    """Get notifications for a user"""
    try:
        notifications = await sm.get_user_notifications(
            user_id=user_id,
            limit=limit,
            offset=offset,
            unread_only=unread_only
        )
        
        return ListResponse(
            items=notifications,
            total=len(notifications),
            page=(offset // limit) + 1,
            page_size=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to get notifications for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/{notification_id}/mark-read", response_model=SuccessResponse)
async def mark_notification_read(
    notification_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    sm: SessionManager = Depends(get_session_manager)
):
    """Mark a notification as read"""
    try:
        success = await sm.mark_notification_read(notification_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return SuccessResponse(message="Notification marked as read")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/{user_id}/mark-all-read", response_model=SuccessResponse)
async def mark_all_notifications_read(
    user_id: str,
    sm: SessionManager = Depends(get_session_manager)
):
    """Mark all notifications as read for a user"""
    try:
        count = await sm.mark_all_notifications_read(user_id)
        
        return SuccessResponse(
            message=f"Marked {count} notifications as read",
            data={"marked_count": count}
        )
        
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/{user_id}/unread-count", response_model=Dict[str, int])
async def get_unread_notification_count(
    user_id: str,
    sm: SessionManager = Depends(get_session_manager)
):
    """Get unread notification count for a user"""
    try:
        count = await sm.get_unread_notification_count(user_id)
        return {"unread_count": count}
        
    except Exception as e:
        logger.error(f"Failed to get unread notification count for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Manual Crawl Endpoints

@router.post("/crawl/create", response_model=Dict[str, str])
async def create_crawl_task(
    request: ManualCrawlRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Create a new manual crawl task"""
    try:
        task_id = await crawl_service.create_crawl_task(request, user_id)
        return {"task_id": task_id, "status": "created"}
    except Exception as e:
        logger.error(f"Failed to create crawl task: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/crawl/{task_id}/execute", response_model=CrawlResult)
async def execute_crawl_task(
    task_id: str,
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Execute a crawl task"""
    try:
        result = await crawl_service.execute_crawl_task(task_id)
        return result
    except Exception as e:
        logger.error(f"Failed to execute crawl task {task_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/crawl/{task_id}", response_model=Dict[str, Any])
async def get_crawl_task(
    task_id: str,
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Get crawl task details"""
    task = await crawl_service.get_crawl_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/crawl", response_model=ListResponse)
async def list_crawl_tasks(
    user_id: str = Header(..., alias="X-User-ID"),
    platform: Optional[PlatformType] = Query(None),
    status: Optional[CrawlTaskStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """List crawl tasks for a user"""
    try:
        tasks = await crawl_service.list_crawl_tasks(
            user_id=user_id,
            platform=platform,
            status=status,
            limit=limit,
            offset=offset
        )
        return ListResponse(items=tasks, total=len(tasks), limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Failed to list crawl tasks: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/crawl/{task_id}", response_model=SuccessResponse)
async def delete_crawl_task(
    task_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Delete a crawl task"""
    try:
        success = await crawl_service.delete_crawl_task(task_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")
        return SuccessResponse(message="Task deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete crawl task {task_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/crawl/stats", response_model=Dict[str, Any])
async def get_crawl_statistics(
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Get crawl statistics"""
    try:
        stats = await crawl_service.get_crawl_statistics(user_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get crawl statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/crawl/cleanup", response_model=Dict[str, int])
async def cleanup_old_crawl_tasks(
    days: int = Query(30, ge=1, le=365),
    crawl_service: ManualCrawlService = Depends(get_manual_crawl_service)
):
    """Clean up old crawl tasks"""
    try:
        deleted_count = await crawl_service.cleanup_old_tasks(days)
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Failed to cleanup old crawl tasks: {e}")
        raise HTTPException(status_code=400, detail=str(e))