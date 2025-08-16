"""去重系统集成服务

该模块负责将去重系统集成到现有的爬虫服务中，
提供统一的去重接口和管理功能。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .engine import DeduplicationEngine, DuplicateType, DuplicationResult
from .context import DeduplicationContext
from .cache_manager import CacheManager, CacheConfig
from .index_manager import IndexManager, IndexConfig

logger = logging.getLogger(__name__)

class DeduplicationIntegrationService:
    """去重系统集成服务
    
    负责管理和协调所有去重组件，为爬虫服务提供统一的去重接口。
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        redis_url: str = "redis://localhost:6379",
        cache_config: Optional[CacheConfig] = None,
        index_config: Optional[IndexConfig] = None
    ):
        self.db = db
        self.redis_url = redis_url
        
        # 初始化配置
        self.cache_config = cache_config or CacheConfig()
        self.index_config = index_config or IndexConfig()
        
        # 核心组件
        self.cache_manager: Optional[CacheManager] = None
        self.index_manager: Optional[IndexManager] = None
        self.dedup_engine: Optional[DeduplicationEngine] = None
        
        # 任务上下文管理
        self.task_contexts: Dict[str, DeduplicationContext] = {}
        
        # 性能统计
        self.stats = {
            "total_checks": 0,
            "duplicates_found": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化去重系统"""
        if self._initialized:
            return
        
        try:
            logger.info("初始化去重系统集成服务...")
            
            # 初始化缓存管理器
            self.cache_manager = CacheManager(
                redis_url=self.redis_url,
                config=self.cache_config
            )
            await self.cache_manager.initialize()
            
            # 初始化索引管理器
            self.index_manager = IndexManager(
                db=self.db,
                config=self.index_config
            )
            await self.index_manager.initialize()
            
            # 初始化去重引擎
            self.dedup_engine = DeduplicationEngine(
                db=self.db,
                cache_manager=self.cache_manager,
                index_manager=self.index_manager
            )
            
            self._initialized = True
            logger.info("去重系统集成服务初始化完成")
            
        except Exception as e:
            logger.error(f"去重系统初始化失败: {e}")
            raise
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            # 清理所有任务上下文
            for context in self.task_contexts.values():
                await context.cleanup()
            self.task_contexts.clear()
            
            # 清理组件
            if self.cache_manager:
                await self.cache_manager.cleanup()
            if self.index_manager:
                await self.index_manager.cleanup()
            
            logger.info("去重系统集成服务清理完成")
            
        except Exception as e:
            logger.error(f"去重系统清理失败: {e}")
    
    async def create_task_context(
        self,
        task_id: str,
        platform: str,
        user_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> DeduplicationContext:
        """为爬取任务创建独立的去重上下文"""
        if not self._initialized:
            await self.initialize()
        
        if task_id in self.task_contexts:
            logger.warning(f"任务 {task_id} 的去重上下文已存在")
            return self.task_contexts[task_id]
        
        try:
            # 创建任务上下文
            context = DeduplicationContext(
                task_id=task_id,
                platform=platform,
                user_id=user_id,
                cache_manager=self.cache_manager,
                config=config or {}
            )
            
            await context.initialize()
            self.task_contexts[task_id] = context
            
            logger.info(f"为任务 {task_id} 创建去重上下文 (平台: {platform})")
            return context
            
        except Exception as e:
            logger.error(f"创建任务上下文失败 {task_id}: {e}")
            raise
    
    async def remove_task_context(self, task_id: str) -> None:
        """移除任务上下文"""
        if task_id in self.task_contexts:
            context = self.task_contexts[task_id]
            await context.cleanup()
            del self.task_contexts[task_id]
            logger.info(f"移除任务 {task_id} 的去重上下文")
    
    async def check_duplicate(
        self,
        task_id: str,
        url: str,
        title: str,
        content: str,
        author: str = "",
        platform: str = "",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> DuplicationResult:
        """检查内容是否重复"""
        if not self._initialized:
            await self.initialize()
        
        self.stats["total_checks"] += 1
        
        try:
            # 获取任务上下文
            context = self.task_contexts.get(task_id)
            if not context:
                logger.warning(f"任务 {task_id} 的去重上下文不存在，创建默认上下文")
                context = await self.create_task_context(
                    task_id=task_id,
                    platform=platform,
                    user_id="unknown"
                )
            
            # 执行去重检查
            result = await self.dedup_engine.check_duplicate(
                context=context,
                url=url,
                title=title,
                content=content,
                author=author,
                platform=platform,
                additional_data=additional_data or {}
            )
            
            # 更新统计
            if result.is_duplicate:
                self.stats["duplicates_found"] += 1
            
            # 记录到上下文
            await context.record_check(url, title, content, result)
            
            return result
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"去重检查失败 {task_id}: {e}")
            # 返回非重复结果，允许内容通过
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=None,
                confidence=0.0,
                similar_content_id=None,
                reason=f"去重检查失败: {str(e)}"
            )
    
    async def batch_check_duplicates(
        self,
        task_id: str,
        items: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], DuplicationResult]]:
        """批量检查重复内容"""
        results = []
        
        for item in items:
            try:
                result = await self.check_duplicate(
                    task_id=task_id,
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    author=item.get("author", ""),
                    platform=item.get("platform", ""),
                    additional_data=item.get("additional_data")
                )
                results.append((item, result))
                
            except Exception as e:
                logger.error(f"批量去重检查项目失败: {e}")
                # 添加失败结果
                results.append((item, DuplicationResult(
                    is_duplicate=False,
                    duplicate_type=None,
                    confidence=0.0,
                    similar_content_id=None,
                    reason=f"检查失败: {str(e)}"
                )))
        
        return results
    
    async def get_task_stats(self, task_id: str) -> Dict[str, Any]:
        """获取任务去重统计信息"""
        context = self.task_contexts.get(task_id)
        if not context:
            return {"error": "任务上下文不存在"}
        
        return await context.get_stats()
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统级统计信息"""
        system_stats = self.stats.copy()
        
        # 添加缓存统计
        if self.cache_manager:
            cache_stats = await self.cache_manager.get_stats()
            system_stats.update(cache_stats)
        
        # 添加索引统计
        if self.index_manager:
            index_stats = await self.index_manager.get_stats()
            system_stats.update(index_stats)
        
        # 添加任务上下文统计
        system_stats["active_tasks"] = len(self.task_contexts)
        
        return system_stats
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            "status": "healthy",
            "initialized": self._initialized,
            "components": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # 检查缓存管理器
            if self.cache_manager:
                cache_health = await self.cache_manager.health_check()
                health["components"]["cache_manager"] = cache_health
            
            # 检查索引管理器
            if self.index_manager:
                index_health = await self.index_manager.health_check()
                health["components"]["index_manager"] = index_health
            
            # 检查是否有组件不健康
            for component, status in health["components"].items():
                if not status.get("healthy", False):
                    health["status"] = "degraded"
                    break
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    async def optimize_performance(self) -> Dict[str, Any]:
        """性能优化"""
        optimization_results = {
            "cache_optimization": {},
            "index_optimization": {},
            "context_cleanup": {}
        }
        
        try:
            # 缓存优化
            if self.cache_manager:
                cache_result = await self.cache_manager.optimize()
                optimization_results["cache_optimization"] = cache_result
            
            # 索引优化
            if self.index_manager:
                index_result = await self.index_manager.optimize_queries()
                optimization_results["index_optimization"] = index_result
            
            # 清理过期的任务上下文
            cleaned_contexts = 0
            current_time = datetime.now(timezone.utc)
            
            for task_id, context in list(self.task_contexts.items()):
                # 如果上下文超过1小时未使用，清理它
                if (current_time - context.created_at).total_seconds() > 3600:
                    await self.remove_task_context(task_id)
                    cleaned_contexts += 1
            
            optimization_results["context_cleanup"] = {
                "cleaned_contexts": cleaned_contexts
            }
            
        except Exception as e:
            logger.error(f"性能优化失败: {e}")
            optimization_results["error"] = str(e)
        
        return optimization_results

# 全局实例
_dedup_service: Optional[DeduplicationIntegrationService] = None

async def get_deduplication_service(
    db: AsyncIOMotorDatabase,
    redis_url: str = "redis://localhost:6379"
) -> DeduplicationIntegrationService:
    """获取去重服务实例"""
    global _dedup_service
    
    if _dedup_service is None:
        _dedup_service = DeduplicationIntegrationService(
            db=db,
            redis_url=redis_url
        )
        await _dedup_service.initialize()
    
    return _dedup_service

async def cleanup_deduplication_service() -> None:
    """清理去重服务实例"""
    global _dedup_service
    
    if _dedup_service:
        await _dedup_service.cleanup()
        _dedup_service = None