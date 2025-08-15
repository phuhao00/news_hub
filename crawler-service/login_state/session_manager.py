# Session Manager for Login State Management
# Manages user sessions across different platforms with Redis caching

import asyncio
import uuid
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorDatabase
from cryptography.fernet import Fernet
from bson import ObjectId
import logging
from logging_config import get_logger, LoggerMixin, log_async_function_call

logger = get_logger('login_state.session_manager')

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

class SessionManager(LoggerMixin):
    """Session management service with Redis caching and MongoDB persistence"""
    
    def __init__(self, db: AsyncIOMotorDatabase, redis_client: aioredis.Redis = None):
        self.db = db
        self.redis = redis_client
        self.active_sessions: Dict[str, dict] = {}
        
        # Initialize encryption for session data
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Session configuration
        self.session_timeout = timedelta(hours=24)  # Default 24 hours
        self.cleanup_interval = 300  # 5 minutes
        
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def create_session(self, user_id: str, platform: str, 
                           browser_config: dict = None) -> dict:
        """Create a new login session"""
        try:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            expires_at = datetime.utcnow() + self.session_timeout
            
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "platform": platform,
                "is_active": True,
                "is_logged_in": False,
                "login_user": None,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "last_activity": datetime.utcnow(),
                "browser_config": browser_config or {},
                "metadata": {
                    "user_agent": browser_config.get("user_agent") if browser_config else None,
                    "ip_address": None,  # Will be set by API handler
                    "browser_version": None
                }
            }
            
            # Save to database
            await self.db.sessions.insert_one(session_data.copy())
            
            # Cache in Redis if available
            if self.redis:
                await self._cache_session(session_id, session_data)
            
            # Store in memory
            self.active_sessions[session_id] = session_data
            
            logger.info(f"Created session {session_id} for user {user_id} on platform {platform}")
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def validate_session(self, session_id: str, check_login_status: bool = False) -> Optional[dict]:
        """Validate session and return session data if valid"""
        try:
            # First check memory cache
            if session_id in self.active_sessions:
                session_data = self.active_sessions[session_id]
                if self._is_session_valid(session_data):
                    # Optionally check login status via browser instances
                    if check_login_status:
                        await self._update_session_login_status(session_id, session_data)
                    return session_data
                else:
                    # Remove expired session from memory
                    del self.active_sessions[session_id]
            
            # Check Redis cache if available
            if self.redis:
                session_data = await self._get_cached_session(session_id)
                if session_data and self._is_session_valid(session_data):
                    # Restore to memory cache
                    self.active_sessions[session_id] = session_data
                    # Optionally check login status via browser instances
                    if check_login_status:
                        await self._update_session_login_status(session_id, session_data)
                    return session_data
            
            # Check database
            session_data = await self.db.sessions.find_one({"session_id": session_id})
            if session_data:
                # Convert ObjectId to string for JSON serialization
                session_data = convert_objectid_to_str(session_data)
                if self._is_session_valid(session_data):
                    # Restore to caches
                    self.active_sessions[session_id] = session_data
                    if self.redis:
                        await self._cache_session(session_id, session_data)
                    # Optionally check login status via browser instances
                    if check_login_status:
                        await self._update_session_login_status(session_id, session_data)
                    return session_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to validate session {session_id}: {e}")
            return None
    
    async def update_login_status(self, session_id: str, is_logged_in: bool, 
                                login_user: str = None, metadata: dict = None) -> bool:
        """Update login status for a session"""
        try:
            update_data = {
                "is_logged_in": is_logged_in,
                "last_activity": datetime.utcnow()
            }
            
            if login_user:
                update_data["login_user"] = login_user
            
            if metadata:
                update_data["metadata"] = metadata
            
            # Update database
            result = await self.db.sessions.update_one(
                {"session_id": session_id},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                logger.warning(f"No session found to update: {session_id}")
                return False
            
            # Update memory cache
            if session_id in self.active_sessions:
                self.active_sessions[session_id].update(update_data)
            
            # Update Redis cache
            if self.redis:
                session_data = await self.validate_session(session_id)
                if session_data:
                    await self._cache_session(session_id, session_data)
            
            logger.info(f"Updated login status for session {session_id}: logged_in={is_logged_in}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update login status for session {session_id}: {e}")
            return False
    
    async def update_activity(self, session_id: str) -> bool:
        """Update last activity timestamp for a session"""
        try:
            current_time = datetime.utcnow()
            
            # Update database
            await self.db.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"last_activity": current_time}}
            )
            
            # Update memory cache
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["last_activity"] = current_time
            
            # Update Redis cache
            if self.redis and session_id in self.active_sessions:
                await self._cache_session(session_id, self.active_sessions[session_id])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update activity for session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            # Remove from database
            result = await self.db.sessions.delete_one({"session_id": session_id})
            
            # Remove from memory cache
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # Remove from Redis cache
            if self.redis:
                await self.redis.delete(f"session:{session_id}")
            
            logger.info(f"Deleted session {session_id}")
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def get_user_sessions(self, user_id: str, platform: str = None) -> List[dict]:
        """Get all sessions for a user"""
        try:
            query = {"user_id": user_id, "is_active": True}
            if platform:
                query["platform"] = platform
            
            cursor = self.db.sessions.find(query)
            sessions = await cursor.to_list(length=None)
            
            # Filter out expired sessions and convert ObjectId
            valid_sessions = []
            for session in sessions:
                # Convert ObjectId to string for JSON serialization
                session = convert_objectid_to_str(session)
                if self._is_session_valid(session):
                    valid_sessions.append(session)
                else:
                    # Clean up expired session
                    await self.delete_session(session["session_id"])
            
            return valid_sessions
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []
    
    async def get_platform_sessions(self, platform: str) -> List[dict]:
        """Get all active sessions for a platform"""
        try:
            cursor = self.db.sessions.find({
                "platform": platform,
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            sessions = await cursor.to_list(length=None)
            # Convert ObjectId to string for JSON serialization
            sessions = [convert_objectid_to_str(session) for session in sessions]
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get platform sessions for {platform}: {e}")
            return []
    
    async def extend_session(self, session_id: str, hours: int = 24) -> bool:
        """Extend session expiration time"""
        try:
            new_expires_at = datetime.utcnow() + timedelta(hours=hours)
            
            result = await self.db.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"expires_at": new_expires_at}}
            )
            
            # Update memory cache
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["expires_at"] = new_expires_at
            
            # Update Redis cache
            if self.redis and session_id in self.active_sessions:
                await self._cache_session(session_id, self.active_sessions[session_id])
            
            logger.info(f"Extended session {session_id} until {new_expires_at}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to extend session {session_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            current_time = datetime.utcnow()
            
            # Find expired sessions
            cursor = self.db.sessions.find({
                "$or": [
                    {"expires_at": {"$lt": current_time}},
                    {"is_active": False}
                ]
            })
            
            expired_sessions = await cursor.to_list(length=None)
            
            # Delete expired sessions
            if expired_sessions:
                session_ids = [session["session_id"] for session in expired_sessions]
                
                # Remove from database
                result = await self.db.sessions.delete_many({
                    "session_id": {"$in": session_ids}
                })
                
                # Remove from memory cache
                for session_id in session_ids:
                    if session_id in self.active_sessions:
                        del self.active_sessions[session_id]
                
                # Remove from Redis cache
                if self.redis:
                    for session_id in session_ids:
                        await self.redis.delete(f"session:{session_id}")
                
                logger.info(f"Cleaned up {result.deleted_count} expired sessions")
                return result.deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    async def _update_session_login_status(self, session_id: str, session_data: dict):
        """Update session login status by checking browser instances"""
        try:
            # Get browser instances for this session
            browser_instances = await self.db.browser_instances.find({
                "session_id": session_id,
                "is_active": True
            }).to_list(length=None)
            
            if not browser_instances:
                return
            
            # Import browser manager to check login status
            # Note: This creates a circular import, so we'll do a dynamic import
            from .browser_manager import BrowserInstanceManager
            
            # Check if any browser instance is logged in
            overall_logged_in = False
            login_user = None
            
            for instance in browser_instances:
                instance_id = instance["instance_id"]
                
                # We need to access the browser manager instance
                # For now, we'll check the database for recent login detection results
                recent_session = await self.db.sessions.find_one({
                    "session_id": session_id,
                    "login_detection_timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)}
                })
                
                if recent_session and recent_session.get("is_logged_in"):
                    overall_logged_in = True
                    login_user = recent_session.get("login_user")
                    break
            
            # Update session if login status changed
            current_login_status = session_data.get("is_logged_in", False)
            if overall_logged_in != current_login_status:
                await self.update_login_status(
                    session_id=session_id,
                    is_logged_in=overall_logged_in,
                    login_user=login_user
                )
                logger.info(f"Updated session {session_id} login status: {overall_logged_in}")
                
        except Exception as e:
            logger.error(f"Failed to update session login status for {session_id}: {e}")
    
    def _is_session_valid(self, session_data: dict) -> bool:
        """Check if session is valid (not expired and active)"""
        if not session_data.get("is_active", False):
            return False
        
        expires_at = session_data.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            return False
        
        return True
    
    async def _cache_session(self, session_id: str, session_data: dict):
        """Cache session data in Redis"""
        try:
            if self.redis:
                # Encrypt session data
                json_data = json.dumps(session_data, default=str)
                encrypted_data = self.cipher.encrypt(json_data.encode())
                
                # Calculate TTL
                expires_at = session_data.get("expires_at")
                if expires_at:
                    ttl = int((expires_at - datetime.utcnow()).total_seconds())
                    ttl = max(ttl, 60)  # Minimum 1 minute
                else:
                    ttl = 86400  # Default 24 hours
                
                await self.redis.setex(
                    f"session:{session_id}",
                    ttl,
                    encrypted_data
                )
        except Exception as e:
            logger.error(f"Failed to cache session {session_id}: {e}")
    
    async def _get_cached_session(self, session_id: str) -> Optional[dict]:
        """Get session data from Redis cache"""
        try:
            if self.redis:
                cached_data = await self.redis.get(f"session:{session_id}")
                if cached_data:
                    # Decrypt session data
                    decrypted_data = self.cipher.decrypt(cached_data)
                    session_data = json.loads(decrypted_data.decode())
                    
                    # Convert datetime strings back to datetime objects
                    for field in ["created_at", "expires_at", "last_activity"]:
                        if field in session_data and isinstance(session_data[field], str):
                            session_data[field] = datetime.fromisoformat(session_data[field])
                    
                    return session_data
        except Exception as e:
            logger.error(f"Failed to get cached session {session_id}: {e}")
        
        return None
    
    async def _periodic_cleanup(self):
        """Periodic cleanup task for expired sessions"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    # Notification methods
    async def get_user_notifications(self, user_id: str, limit: int = 50, offset: int = 0, unread_only: bool = False):
        """Get notifications for a user"""
        try:
            # Build query filter
            query_filter = {}
            
            # Get user sessions to filter notifications
            user_sessions = await self.get_user_sessions(user_id)
            session_ids = [session["session_id"] for session in user_sessions]
            
            if session_ids:
                query_filter["session_id"] = {"$in": session_ids}
            else:
                # No sessions for user, return empty list
                return []
            
            if unread_only:
                query_filter["read"] = {"$ne": True}
            
            # Query notifications
            cursor = self.db.notifications.find(query_filter)
            cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
            
            notifications = []
            async for notification in cursor:
                notification["_id"] = str(notification["_id"])
                notifications.append(notification)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Failed to get notifications for user {user_id}: {e}")
            return []
    
    async def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        try:
            # Verify the notification belongs to the user
            user_sessions = await self.get_user_sessions(user_id)
            session_ids = [session["session_id"] for session in user_sessions]
            
            result = await self.db.notifications.update_one(
                {
                    "_id": ObjectId(notification_id),
                    "session_id": {"$in": session_ids}
                },
                {
                    "$set": {
                        "read": True,
                        "read_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to mark notification {notification_id} as read: {e}")
            return False
    
    async def mark_all_notifications_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user"""
        try:
            # Get user sessions
            user_sessions = await self.get_user_sessions(user_id)
            session_ids = [session["session_id"] for session in user_sessions]
            
            if not session_ids:
                return 0
            
            result = await self.db.notifications.update_many(
                {
                    "session_id": {"$in": session_ids},
                    "read": {"$ne": True}
                },
                {
                    "$set": {
                        "read": True,
                        "read_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Failed to mark all notifications as read for user {user_id}: {e}")
            return 0
    
    async def get_unread_notification_count(self, user_id: str) -> int:
        """Get unread notification count for a user"""
        try:
            # Get user sessions
            user_sessions = await self.get_user_sessions(user_id)
            session_ids = [session["session_id"] for session in user_sessions]
            
            if not session_ids:
                return 0
            
            count = await self.db.notifications.count_documents({
                "session_id": {"$in": session_ids},
                "read": {"$ne": True}
            })
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to get unread notification count for user {user_id}: {e}")
            return 0
    
    async def get_session_stats(self) -> Dict:
        """Get session statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$platform",
                        "total_sessions": {"$sum": 1},
                        "active_sessions": {
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
                        },
                        "logged_in_sessions": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$is_logged_in", True]},
                                    1,
                                    0
                                ]
                            }
                        }
                    }
                }
            ]
            
            cursor = self.db.sessions.aggregate(pipeline)
            platform_stats = await cursor.to_list(length=None)
            
            # Get total counts
            total_sessions = await self.db.sessions.count_documents({})
            active_sessions = await self.db.sessions.count_documents({
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "memory_cached_sessions": len(self.active_sessions),
                "platform_stats": {stat["_id"]: {
                    "total": stat["total_sessions"],
                    "active": stat["active_sessions"],
                    "logged_in": stat["logged_in_sessions"]
                } for stat in platform_stats}
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {}