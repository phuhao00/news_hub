"""去重上下文管理模块

为每个爬取任务提供独立的去重上下文，确保判定逻辑的独立性
"""

import logging
from datetime import datetime
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, field
import asyncio
from collections import defaultdict


@dataclass
class DeduplicationStats:
    """去重统计信息"""
    total_checked: int = 0
    duplicates_found: int = 0
    url_duplicates: int = 0
    content_duplicates: int = 0
    semantic_duplicates: int = 0
    time_window_duplicates: int = 0
    task_duplicates: int = 0
    
    @property
    def duplicate_rate(self) -> float:
        """重复率"""
        if self.total_checked == 0:
            return 0.0
        return self.duplicates_found / self.total_checked
    
    @property
    def unique_rate(self) -> float:
        """唯一率"""
        return 1.0 - self.duplicate_rate


class DeduplicationContext:
    """去重上下文管理类
    
    为每个爬取任务维护独立的去重状态和历史记录
    """
    
    def __init__(self, 
                 task_id: str,
                 cache_manager: 'CacheManager',
                 index_manager: 'IndexManager',
                 max_memory_items: int = 10000):
        """
        初始化去重上下文
        
        Args:
            task_id: 任务ID
            cache_manager: 缓存管理器
            index_manager: 索引管理器
            max_memory_items: 内存中最大缓存项数
        """
        self.task_id = task_id
        self.cache_manager = cache_manager
        self.index_manager = index_manager
        self.max_memory_items = max_memory_items
        
        # 时间戳
        self.created_at = datetime.now()
        self.last_activity: Optional[datetime] = None
        
        # 内存缓存集合（用于快速查找）
        self.processed_urls: Set[str] = set()
        self.content_hashes: Set[str] = set()
        self.processed_titles: Set[str] = set()
        
        # 统计信息
        self.stats = DeduplicationStats()
        
        # 性能监控
        self.performance_metrics: Dict[str, list] = defaultdict(list)
        
        # 错误记录
        self.error_count = 0
        self.last_error: Optional[str] = None
        
        # 日志记录器
        self.logger = logging.getLogger(f"{__name__}.{task_id}")
        
        # 锁，确保线程安全
        self._lock = asyncio.Lock()
        
        self.logger.info(f"创建去重上下文: {task_id}")
    
    async def add_processed_url(self, url: str) -> bool:
        """添加已处理的URL
        
        Args:
            url: 标准化的URL
            
        Returns:
            bool: 是否成功添加（False表示已存在）
        """
        async with self._lock:
            if url in self.processed_urls:
                return False
            
            self.processed_urls.add(url)
            self._update_activity()
            
            # 内存管理
            await self._manage_memory()
            
            return True
    
    async def add_content_hash(self, content_hash: str) -> bool:
        """添加内容哈希
        
        Args:
            content_hash: 内容哈希值
            
        Returns:
            bool: 是否成功添加（False表示已存在）
        """
        async with self._lock:
            if content_hash in self.content_hashes:
                return False
            
            self.content_hashes.add(content_hash)
            self._update_activity()
            
            # 内存管理
            await self._manage_memory()
            
            return True
    
    async def add_processed_title(self, title: str) -> bool:
        """添加已处理的标题
        
        Args:
            title: 标题文本
            
        Returns:
            bool: 是否成功添加（False表示已存在）
        """
        if not title or len(title.strip()) < 3:
            return True  # 忽略过短的标题
        
        normalized_title = title.strip().lower()
        
        async with self._lock:
            if normalized_title in self.processed_titles:
                return False
            
            self.processed_titles.add(normalized_title)
            self._update_activity()
            
            # 内存管理
            await self._manage_memory()
            
            return True
    
    async def is_url_processed(self, url: str) -> bool:
        """检查URL是否已处理"""
        async with self._lock:
            return url in self.processed_urls
    
    async def is_content_hash_processed(self, content_hash: str) -> bool:
        """检查内容哈希是否已处理"""
        async with self._lock:
            return content_hash in self.content_hashes
    
    async def is_title_processed(self, title: str) -> bool:
        """检查标题是否已处理"""
        if not title or len(title.strip()) < 3:
            return False
        
        normalized_title = title.strip().lower()
        
        async with self._lock:
            return normalized_title in self.processed_titles
    
    def update_stats(self, 
                    is_duplicate: bool,
                    duplicate_type: str = None):
        """更新统计信息
        
        Args:
            is_duplicate: 是否为重复
            duplicate_type: 重复类型
        """
        self.stats.total_checked += 1
        
        if is_duplicate:
            self.stats.duplicates_found += 1
            
            # 按类型统计
            if duplicate_type == 'url_duplicate':
                self.stats.url_duplicates += 1
            elif duplicate_type == 'content_hash_duplicate':
                self.stats.content_duplicates += 1
            elif duplicate_type == 'semantic_duplicate':
                self.stats.semantic_duplicates += 1
            elif duplicate_type == 'time_window_duplicate':
                self.stats.time_window_duplicates += 1
            elif duplicate_type == 'task_duplicate':
                self.stats.task_duplicates += 1
        
        self._update_activity()
    
    def record_performance_metric(self, 
                                operation: str, 
                                duration_ms: float):
        """记录性能指标
        
        Args:
            operation: 操作名称
            duration_ms: 耗时（毫秒）
        """
        self.performance_metrics[operation].append(duration_ms)
        
        # 保持最近100条记录
        if len(self.performance_metrics[operation]) > 100:
            self.performance_metrics[operation] = \
                self.performance_metrics[operation][-100:]
    
    def record_error(self, error_message: str):
        """记录错误
        
        Args:
            error_message: 错误信息
        """
        self.error_count += 1
        self.last_error = error_message
        self.logger.error(f"去重上下文错误: {error_message}")
    
    async def get_memory_usage(self) -> Dict[str, int]:
        """获取内存使用情况"""
        async with self._lock:
            return {
                'processed_urls': len(self.processed_urls),
                'content_hashes': len(self.content_hashes),
                'processed_titles': len(self.processed_titles),
                'total_items': (
                    len(self.processed_urls) + 
                    len(self.content_hashes) + 
                    len(self.processed_titles)
                )
            }
    
    async def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """获取性能摘要"""
        summary = {}
        
        for operation, durations in self.performance_metrics.items():
            if durations:
                summary[operation] = {
                    'avg_ms': sum(durations) / len(durations),
                    'min_ms': min(durations),
                    'max_ms': max(durations),
                    'count': len(durations)
                }
        
        return summary
    
    async def _manage_memory(self):
        """管理内存使用，防止内存溢出"""
        total_items = (
            len(self.processed_urls) + 
            len(self.content_hashes) + 
            len(self.processed_titles)
        )
        
        if total_items > self.max_memory_items:
            # 清理最老的数据（简单的FIFO策略）
            cleanup_count = total_items - int(self.max_memory_items * 0.8)
            
            # 优先清理URL缓存
            if len(self.processed_urls) > cleanup_count:
                urls_to_remove = list(self.processed_urls)[:cleanup_count]
                for url in urls_to_remove:
                    self.processed_urls.discard(url)
                cleanup_count = 0
            else:
                cleanup_count -= len(self.processed_urls)
                self.processed_urls.clear()
            
            # 然后清理标题缓存
            if cleanup_count > 0 and len(self.processed_titles) > cleanup_count:
                titles_to_remove = list(self.processed_titles)[:cleanup_count]
                for title in titles_to_remove:
                    self.processed_titles.discard(title)
                cleanup_count = 0
            elif cleanup_count > 0:
                cleanup_count -= len(self.processed_titles)
                self.processed_titles.clear()
            
            # 最后清理内容哈希（最重要，最后清理）
            if cleanup_count > 0:
                hashes_to_remove = list(self.content_hashes)[:cleanup_count]
                for hash_val in hashes_to_remove:
                    self.content_hashes.discard(hash_val)
            
            self.logger.warning(f"内存清理完成，当前项目数: {await self.get_memory_usage()}")
    
    def _update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()
    
    async def persist_to_cache(self):
        """将上下文数据持久化到缓存"""
        try:
            context_data = {
                'task_id': self.task_id,
                'created_at': self.created_at.isoformat(),
                'last_activity': self.last_activity.isoformat() if self.last_activity else None,
                'stats': {
                    'total_checked': self.stats.total_checked,
                    'duplicates_found': self.stats.duplicates_found,
                    'url_duplicates': self.stats.url_duplicates,
                    'content_duplicates': self.stats.content_duplicates,
                    'semantic_duplicates': self.stats.semantic_duplicates,
                    'time_window_duplicates': self.stats.time_window_duplicates,
                    'task_duplicates': self.stats.task_duplicates
                },
                'memory_usage': await self.get_memory_usage(),
                'error_count': self.error_count,
                'last_error': self.last_error
            }
            
            await self.cache_manager.set_context_data(self.task_id, context_data)
            self.logger.debug(f"上下文数据已持久化: {self.task_id}")
            
        except Exception as e:
            self.record_error(f"持久化上下文失败: {str(e)}")
    
    async def load_from_cache(self) -> bool:
        """从缓存加载上下文数据
        
        Returns:
            bool: 是否成功加载
        """
        try:
            context_data = await self.cache_manager.get_context_data(self.task_id)
            if not context_data:
                return False
            
            # 恢复统计信息
            stats_data = context_data.get('stats', {})
            self.stats.total_checked = stats_data.get('total_checked', 0)
            self.stats.duplicates_found = stats_data.get('duplicates_found', 0)
            self.stats.url_duplicates = stats_data.get('url_duplicates', 0)
            self.stats.content_duplicates = stats_data.get('content_duplicates', 0)
            self.stats.semantic_duplicates = stats_data.get('semantic_duplicates', 0)
            self.stats.time_window_duplicates = stats_data.get('time_window_duplicates', 0)
            self.stats.task_duplicates = stats_data.get('task_duplicates', 0)
            
            # 恢复错误信息
            self.error_count = context_data.get('error_count', 0)
            self.last_error = context_data.get('last_error')
            
            # 恢复时间信息
            if context_data.get('last_activity'):
                self.last_activity = datetime.fromisoformat(context_data['last_activity'])
            
            self.logger.info(f"从缓存恢复上下文数据: {self.task_id}")
            return True
            
        except Exception as e:
            self.record_error(f"从缓存加载上下文失败: {str(e)}")
            return False
    
    async def cleanup(self):
        """清理上下文资源"""
        try:
            # 持久化最终状态
            await self.persist_to_cache()
            
            # 清理内存
            async with self._lock:
                self.processed_urls.clear()
                self.content_hashes.clear()
                self.processed_titles.clear()
                self.performance_metrics.clear()
            
            self.logger.info(f"上下文清理完成: {self.task_id}")
            
        except Exception as e:
            self.logger.error(f"上下文清理失败: {str(e)}")
    
    def __str__(self) -> str:
        return f"DeduplicationContext(task_id={self.task_id}, stats={self.stats})"
    
    def __repr__(self) -> str:
        return self.__str__()