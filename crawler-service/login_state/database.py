# Database initialization and management for Login State Management
# Handles MongoDB collections, indexes, and initial data setup

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel
from .models import (
    DATABASE_INDEXES, 
    DEFAULT_PLATFORM_CONFIGS,
    PlatformConfigDocument
)
from logging_config import get_logger, LoggerMixin, log_async_function_call

logger = get_logger('login_state.database')

class DatabaseManager(LoggerMixin):
    """Database management service for login state management"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collections = {
            "sessions": db.sessions,
            "browser_instances": db.browser_instances,
            "cookie_data": db.cookie_data,
            "crawl_tasks": db.crawl_tasks,
            "platform_configs": db.platform_configs,
            "continuous_crawl_tasks": db.continuous_crawl_tasks
        }
    
    async def initialize_database(self) -> bool:
        """Initialize database with collections, indexes, and default data"""
        try:
            logger.info("Starting database initialization...")
            
            # Create indexes for all collections
            await self._create_indexes()
            
            # Initialize platform configurations
            await self._initialize_platform_configs()
            
            # Verify database setup
            await self._verify_database_setup()
            
            logger.info("Database initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    async def _create_indexes(self):
        """Create indexes for all collections"""
        try:
            for collection_name, indexes in DATABASE_INDEXES.items():
                collection = self.collections[collection_name]
                
                # Create index models
                index_models = []
                for index_def in indexes:
                    index_model = IndexModel(
                        index_def["keys"],
                        unique=index_def.get("unique", False),
                        background=True
                    )
                    index_models.append(index_model)
                
                # Create indexes
                if index_models:
                    await collection.create_indexes(index_models)
                    logger.info(f"Created {len(index_models)} indexes for collection '{collection_name}'")
                    
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise
    
    async def _initialize_platform_configs(self):
        """Initialize default platform configurations"""
        try:
            platform_configs_collection = self.collections["platform_configs"]
            
            for config_data in DEFAULT_PLATFORM_CONFIGS:
                # Check if platform config already exists
                existing_config = await platform_configs_collection.find_one({
                    "platform": config_data["platform"]
                })
                
                if not existing_config:
                    # Add timestamps
                    config_data["created_at"] = datetime.utcnow()
                    config_data["updated_at"] = datetime.utcnow()
                    
                    # Insert new platform config
                    await platform_configs_collection.insert_one(config_data)
                    logger.info(f"Initialized platform config for '{config_data['platform']}'")
                else:
                    logger.info(f"Platform config for '{config_data['platform']}' already exists")
                    
        except Exception as e:
            logger.error(f"Failed to initialize platform configs: {e}")
            raise
    
    async def _verify_database_setup(self):
        """Verify database setup is correct and create missing collections"""
        try:
            # Check collections exist
            collection_names = await self.db.list_collection_names()
            
            for collection_name in self.collections.keys():
                if collection_name not in collection_names:
                    logger.warning(f"Collection '{collection_name}' not found, creating...")
                    try:
                        # Create the collection by inserting and immediately removing a dummy document
                        collection = self.collections[collection_name]
                        dummy_doc = {"_temp": True}
                        result = await collection.insert_one(dummy_doc)
                        await collection.delete_one({"_id": result.inserted_id})
                        logger.info(f"Successfully created collection '{collection_name}'")
                    except Exception as create_error:
                        logger.error(f"Failed to create collection '{collection_name}': {create_error}")
                        # Continue with other collections even if one fails
                        continue
                else:
                    # Check indexes
                    try:
                        collection = self.collections[collection_name]
                        indexes = await collection.list_indexes().to_list(length=None)
                        logger.info(f"Collection '{collection_name}' has {len(indexes)} indexes")
                    except Exception as index_error:
                        logger.warning(f"Failed to check indexes for collection '{collection_name}': {index_error}")
            
            # Check platform configs
            platform_count = await self.collections["platform_configs"].count_documents({})
            logger.info(f"Found {platform_count} platform configurations")
            
        except Exception as e:
            logger.error(f"Failed to verify database setup: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Dict]:
        """Get statistics for all collections"""
        try:
            stats = {}
            
            for collection_name, collection in self.collections.items():
                # Get document count
                doc_count = await collection.count_documents({})
                
                # Get collection stats
                try:
                    collection_stats = await self.db.command("collStats", collection_name)
                    stats[collection_name] = {
                        "document_count": doc_count,
                        "size_bytes": collection_stats.get("size", 0),
                        "index_count": collection_stats.get("nindexes", 0),
                        "index_size_bytes": collection_stats.get("totalIndexSize", 0)
                    }
                except Exception:
                    # Fallback if collStats is not available
                    stats[collection_name] = {
                        "document_count": doc_count,
                        "size_bytes": 0,
                        "index_count": 0,
                        "index_size_bytes": 0
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    async def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired data from all collections"""
        try:
            cleanup_results = {}
            current_time = datetime.utcnow()
            
            # Clean up expired sessions
            sessions_result = await self.collections["sessions"].delete_many({
                "$or": [
                    {"expires_at": {"$lt": current_time}},
                    {"is_active": False}
                ]
            })
            cleanup_results["sessions"] = sessions_result.deleted_count
            
            # Clean up expired browser instances
            instances_result = await self.collections["browser_instances"].delete_many({
                "$or": [
                    {"expires_at": {"$lt": current_time}},
                    {"is_active": False}
                ]
            })
            cleanup_results["browser_instances"] = instances_result.deleted_count
            
            # Clean up expired cookies
            cookies_result = await self.collections["cookie_data"].delete_many({
                "$or": [
                    {"expires_at": {"$lt": current_time}},
                    {"is_active": False}
                ]
            })
            cleanup_results["cookie_data"] = cookies_result.deleted_count
            
            # Clean up old completed crawl tasks (older than 7 days)
            seven_days_ago = datetime.utcnow().replace(day=datetime.utcnow().day - 7)
            tasks_result = await self.collections["crawl_tasks"].delete_many({
                "status": {"$in": ["completed", "failed", "cancelled"]},
                "completed_at": {"$lt": seven_days_ago}
            })
            cleanup_results["crawl_tasks"] = tasks_result.deleted_count
            
            logger.info(f"Cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}")
            return {}
    
    async def backup_collection(self, collection_name: str, backup_path: str) -> bool:
        """Backup a collection to a file"""
        try:
            if collection_name not in self.collections:
                raise ValueError(f"Collection '{collection_name}' not found")
            
            collection = self.collections[collection_name]
            
            # Get all documents
            cursor = collection.find({})
            documents = await cursor.to_list(length=None)
            
            # Convert ObjectId and datetime to string for JSON serialization
            import json
            from bson import ObjectId
            
            def json_serializer(obj):
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            # Write to backup file
            import aiofiles
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(documents, default=json_serializer, indent=2))
            
            logger.info(f"Backed up {len(documents)} documents from '{collection_name}' to '{backup_path}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup collection '{collection_name}': {e}")
            return False
    
    async def restore_collection(self, collection_name: str, backup_path: str, 
                               clear_existing: bool = False) -> bool:
        """Restore a collection from a backup file"""
        try:
            if collection_name not in self.collections:
                raise ValueError(f"Collection '{collection_name}' not found")
            
            collection = self.collections[collection_name]
            
            # Clear existing data if requested
            if clear_existing:
                await collection.delete_many({})
                logger.info(f"Cleared existing data from '{collection_name}'")
            
            # Read backup file
            import aiofiles
            import json
            
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                documents = json.loads(content)
            
            # Convert string dates back to datetime objects
            from datetime import datetime
            
            def restore_dates(doc):
                for key, value in doc.items():
                    if isinstance(value, str) and key.endswith(('_at', 'At')):
                        try:
                            doc[key] = datetime.fromisoformat(value)
                        except ValueError:
                            pass  # Keep as string if not a valid datetime
                    elif isinstance(value, dict):
                        restore_dates(value)
                return doc
            
            # Restore documents
            if documents:
                restored_documents = [restore_dates(doc) for doc in documents]
                await collection.insert_many(restored_documents)
                logger.info(f"Restored {len(restored_documents)} documents to '{collection_name}'")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore collection '{collection_name}': {e}")
            return False
    
    async def get_platform_config(self, platform: str) -> Optional[Dict]:
        """Get platform configuration"""
        try:
            config = await self.collections["platform_configs"].find_one({
                "platform": platform,
                "is_enabled": True
            })
            return config
            
        except Exception as e:
            logger.error(f"Failed to get platform config for '{platform}': {e}")
            return None
    
    async def update_platform_config(self, platform: str, config_data: Dict) -> bool:
        """Update platform configuration"""
        try:
            config_data["updated_at"] = datetime.utcnow()
            
            result = await self.collections["platform_configs"].update_one(
                {"platform": platform},
                {"$set": config_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated platform config for '{platform}'")
                return True
            else:
                logger.warning(f"No platform config found to update for '{platform}'")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update platform config for '{platform}': {e}")
            return False
    
    async def get_all_platform_configs(self) -> List[Dict]:
        """Get all platform configurations"""
        try:
            cursor = self.collections["platform_configs"].find({})
            configs = await cursor.to_list(length=None)
            return configs
            
        except Exception as e:
            logger.error(f"Failed to get all platform configs: {e}")
            return []
    
    async def health_check(self) -> Dict[str, bool]:
        """Perform database health check"""
        try:
            health_status = {}
            
            # Check database connection
            try:
                await self.db.command("ping")
                health_status["database_connection"] = True
            except Exception:
                health_status["database_connection"] = False
            
            # Check each collection
            for collection_name, collection in self.collections.items():
                try:
                    await collection.find_one({})
                    health_status[f"collection_{collection_name}"] = True
                except Exception:
                    health_status[f"collection_{collection_name}"] = False
            
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to perform health check: {e}")
            return {"database_connection": False}

# Utility functions

async def create_database_manager(db: AsyncIOMotorDatabase) -> DatabaseManager:
    """Create and initialize database manager"""
    manager = DatabaseManager(db)
    await manager.initialize_database()
    return manager

async def setup_database_indexes(db: AsyncIOMotorDatabase) -> bool:
    """Setup database indexes only (without full initialization)"""
    try:
        manager = DatabaseManager(db)
        await manager._create_indexes()
        return True
    except Exception as e:
        logger.error(f"Failed to setup database indexes: {e}")
        return False

async def cleanup_database(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """Cleanup expired data from database"""
    try:
        manager = DatabaseManager(db)
        return await manager.cleanup_expired_data()
    except Exception as e:
        logger.error(f"Failed to cleanup database: {e}")
        return {}