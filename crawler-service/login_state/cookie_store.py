# Cookie Storage Service for Login State Management
# Provides encrypted storage and retrieval of cookies for different platforms

import os
import json
import aiofiles
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

class CookieStore:
    """Cookie storage service with encryption support"""
    
    def __init__(self, db: AsyncIOMotorDatabase, encryption_key: bytes = None):
        self.db = db
        self.storage_dir = Path("./data/cookies")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            # Generate new key if not provided
            self.encryption_key = Fernet.generate_key()
            self.cipher = Fernet(self.encryption_key)
            # Save key to file for persistence
            self._save_encryption_key()
    
    def _save_encryption_key(self):
        """Save encryption key to file"""
        key_dir = Path("./keys")
        key_dir.mkdir(parents=True, exist_ok=True)
        key_file = key_dir / "cookie_encryption.key"
        
        with open(key_file, "wb") as f:
            f.write(self.encryption_key)
        
        logger.info(f"Encryption key saved to {key_file}")
    
    @classmethod
    def load_encryption_key(cls, key_file: str = "./keys/cookie_encryption.key") -> bytes:
        """Load encryption key from file"""
        try:
            with open(key_file, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Encryption key file not found: {key_file}")
            return None
    
    def encrypt_data(self, data: Any) -> str:
        """Encrypt data and return base64 encoded string"""
        json_data = json.dumps(data, default=str)
        encrypted_data = self.cipher.encrypt(json_data.encode())
        return encrypted_data.decode()
    
    def decrypt_data(self, encrypted_data: str) -> Any:
        """Decrypt base64 encoded string and return original data"""
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data.encode())
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            return None
    
    async def save_cookies(self, browser_instance_id: str, platform: str, 
                          cookies: List[Dict], domain: str = None) -> bool:
        """Save cookies to database with encryption"""
        try:
            # Encrypt cookie data
            encrypted_cookies = self.encrypt_data(cookies)
            
            # Prepare cookie document
            cookie_doc = {
                "browser_instance_id": browser_instance_id,
                "platform": platform,
                "domain": domain or f".{platform}.com",
                "encrypted_cookies": encrypted_cookies,
                "encryption_version": "v1",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30)
            }
            
            # Update or insert cookie data
            await self.db.cookie_data.update_one(
                {
                    "browser_instance_id": browser_instance_id,
                    "domain": cookie_doc["domain"]
                },
                {"$set": cookie_doc},
                upsert=True
            )
            
            logger.info(f"Cookies saved for {platform} (instance: {browser_instance_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
            return False
    
    async def load_cookies(self, browser_instance_id: str, platform: str = None, 
                          domain: str = None) -> List[Dict]:
        """Load and decrypt cookies from database"""
        try:
            # Build query
            query = {"browser_instance_id": browser_instance_id}
            if platform:
                query["platform"] = platform
            if domain:
                query["domain"] = domain
            
            # Find cookie documents
            cursor = self.db.cookie_data.find(query)
            cookie_docs = await cursor.to_list(length=None)
            
            all_cookies = []
            for doc in cookie_docs:
                # Check if cookies are expired
                if doc.get("expires_at") and doc["expires_at"] < datetime.utcnow():
                    logger.info(f"Cookies expired for {doc.get('platform')}")
                    continue
                
                # Decrypt cookies
                encrypted_cookies = doc.get("encrypted_cookies")
                if encrypted_cookies:
                    cookies = self.decrypt_data(encrypted_cookies)
                    if cookies:
                        all_cookies.extend(cookies)
            
            logger.info(f"Loaded {len(all_cookies)} cookies for instance {browser_instance_id}")
            return all_cookies
            
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return []
    
    async def delete_cookies(self, browser_instance_id: str, platform: str = None) -> bool:
        """Delete cookies from database"""
        try:
            query = {"browser_instance_id": browser_instance_id}
            if platform:
                query["platform"] = platform
            
            result = await self.db.cookie_data.delete_many(query)
            logger.info(f"Deleted {result.deleted_count} cookie records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete cookies: {e}")
            return False
    
    async def cleanup_expired_cookies(self) -> int:
        """Clean up expired cookies from database"""
        try:
            result = await self.db.cookie_data.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            
            logger.info(f"Cleaned up {result.deleted_count} expired cookie records")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cookies: {e}")
            return 0
    
    async def get_cookie_stats(self, browser_instance_id: str = None) -> Dict:
        """Get cookie statistics for a browser instance or all instances"""
        try:
            # Build match condition
            match_condition = {}
            if browser_instance_id:
                match_condition["browser_instance_id"] = browser_instance_id
            
            pipeline = [
                {"$match": match_condition},
                {
                    "$group": {
                        "_id": "$platform",
                        "count": {"$sum": 1},
                        "last_updated": {"$max": "$updated_at"}
                    }
                }
            ]
            
            cursor = self.db.cookie_data.aggregate(pipeline)
            stats = await cursor.to_list(length=None)
            
            return {
                "platforms": {stat["_id"]: {
                    "count": stat["count"],
                    "last_updated": stat["last_updated"]
                } for stat in stats},
                "total_platforms": len(stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get cookie stats: {e}")
            return {"platforms": {}, "total_platforms": 0}
    
    async def backup_cookies(self, browser_instance_id: str, backup_path: str = None) -> str:
        """Backup cookies to file"""
        try:
            if not backup_path:
                backup_dir = Path("./backups/cookies")
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"cookies_{browser_instance_id}_{timestamp}.json"
            
            # Get all cookies for the instance
            cursor = self.db.cookie_data.find({"browser_instance_id": browser_instance_id})
            cookie_docs = await cursor.to_list(length=None)
            
            # Prepare backup data (keep encrypted)
            backup_data = {
                "browser_instance_id": browser_instance_id,
                "backup_time": datetime.utcnow().isoformat(),
                "cookies": []
            }
            
            for doc in cookie_docs:
                backup_data["cookies"].append({
                    "platform": doc.get("platform"),
                    "domain": doc.get("domain"),
                    "encrypted_cookies": doc.get("encrypted_cookies"),
                    "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                    "expires_at": doc.get("expires_at").isoformat() if doc.get("expires_at") else None
                })
            
            # Save to file
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(backup_data, indent=2, default=str))
            
            logger.info(f"Cookies backed up to {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to backup cookies: {e}")
            return None
    
    async def restore_cookies(self, backup_path: str, browser_instance_id: str = None) -> bool:
        """Restore cookies from backup file"""
        try:
            # Load backup data
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                backup_data = json.loads(content)
            
            target_instance_id = browser_instance_id or backup_data.get("browser_instance_id")
            if not target_instance_id:
                logger.error("No browser instance ID specified for restore")
                return False
            
            # Restore each cookie record
            restored_count = 0
            for cookie_data in backup_data.get("cookies", []):
                cookie_doc = {
                    "browser_instance_id": target_instance_id,
                    "platform": cookie_data.get("platform"),
                    "domain": cookie_data.get("domain"),
                    "encrypted_cookies": cookie_data.get("encrypted_cookies"),
                    "encryption_version": "v1",
                    "created_at": datetime.fromisoformat(cookie_data["created_at"]) if cookie_data.get("created_at") else datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "expires_at": datetime.fromisoformat(cookie_data["expires_at"]) if cookie_data.get("expires_at") else datetime.utcnow() + timedelta(days=30)
                }
                
                await self.db.cookie_data.update_one(
                    {
                        "browser_instance_id": target_instance_id,
                        "domain": cookie_doc["domain"]
                    },
                    {"$set": cookie_doc},
                    upsert=True
                )
                restored_count += 1
            
            logger.info(f"Restored {restored_count} cookie records from backup")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore cookies: {e}")
            return False