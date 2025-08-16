"""缓存管理器模块

实现Redis缓存和Bloom Filter，提供高性能的去重检测支持
"""

import redis
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from .types import ContentItem, DuplicateType
from .monitoring import get_monitoring_service


@dataclass
class CacheConfig:
    """缓存配置"""
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # 缓存过期时间（秒）
    url_cache_ttl: int = 86400 * 7  # 7天
    content_hash_ttl: int = 86400 * 30  # 30天
    task_status_ttl: int = 86400 * 3  # 3天
    context_data_ttl: int = 86400 * 7  # 7天
    
    # Bloom Filter配置
    bloom_filter_capacity: int = 1000000  # 100万个元素
    bloom_filter_error_rate: float = 0.01  # 1%误判率
    
    # 连接池配置
    max_connections: int = 20
    connection_timeout: int = 5
    socket_timeout: int = 5


class BloomFilter:
    """简单的Bloom Filter实现"""
    
    def __init__(self, capacity: int, error_rate: float):
        """
        初始化Bloom Filter
        
        Args:
            capacity: 预期元素数量
            error_rate: 误判率
        """
        self.capacity = capacity
        self.error_rate = error_rate
        
        # 计算最优参数
        self.bit_size = self._calculate_bit_size(capacity, error_rate)
        self.hash_count = self._calculate_hash_count(self.bit_size, capacity)
        
        # 位数组（使用Redis的位操作）
        self.redis_key = "bloom_filter:urls"
        
        self.logger = logging.getLogger(__name__)
    
    def _calculate_bit_size(self, capacity: int, error_rate: float) -> int:
        """计算位数组大小"""
        import math
        return int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
    
    def _calculate_hash_count(self, bit_size: int, capacity: int) -> int:
        """计算哈希函数数量"""
        import math
        return int(bit_size * math.log(2) / capacity)
    
    def _hash_functions(self, item: str) -> List[int]:
        """生成多个哈希值"""
        hashes = []
        
        # 使用不同的哈希算法
        hash1 = int(hashlib.md5(item.encode()).hexdigest(), 16)
        hash2 = int(hashlib.sha1(item.encode()).hexdigest(), 16)
        
        for i in range(self.hash_count):
            # 双重哈希
            hash_val = (hash1 + i * hash2) % self.bit_size
            hashes.append(hash_val)
        
        return hashes
    
    async def add(self, redis_client: redis.Redis, item: str):
        """添加元素到Bloom Filter"""
        hashes = self._hash_functions(item)
        
        # 使用Redis管道批量设置位
        pipe = redis_client.pipeline()
        for hash_val in hashes:
            pipe.setbit(self.redis_key, hash_val, 1)
        await asyncio.get_event_loop().run_in_executor(None, pipe.execute)
    
    async def contains(self, redis_client: redis.Redis, item: str) -> bool:
        """检查元素是否可能存在"""
        hashes = self._hash_functions(item)
        
        # 检查所有位是否都为1
        pipe = redis_client.pipeline()
        for hash_val in hashes:
            pipe.getbit(self.redis_key, hash_val)
        
        results = await asyncio.get_event_loop().run_in_executor(None, pipe.execute)
        return all(results)
    
    async def clear(self, redis_client: redis.Redis):
        """清空Bloom Filter"""
        await asyncio.get_event_loop().run_in_executor(
            None, redis_client.delete, self.redis_key
        )


class CacheManager:
    """缓存管理器
    
    提供Redis缓存和Bloom Filter功能
    """
    
    def __init__(self, config: CacheConfig = None):
        """
        初始化缓存管理器
        
        Args:
            config: 缓存配置
        """
        self.config = config or CacheConfig()
        self.logger = logging.getLogger(__name__)
        
        # 监控服务
        self.monitoring = get_monitoring_service()
        
        # Redis连接池
        self._redis_pool = None
        self._redis_client = None
        
        # Bloom Filter
        self.url_bloom_filter = BloomFilter(
            self.config.bloom_filter_capacity,
            self.config.bloom_filter_error_rate
        )
        
        # 线程池用于异步操作
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # 连接锁
        self._connection_lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'bloom_filter_hits': 0,
            'bloom_filter_misses': 0,
            'errors': 0
        }
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            # 创建连接池
            self._redis_pool = redis.ConnectionPool(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.connection_timeout,
                decode_responses=True
            )
            
            # 创建Redis客户端
            self._redis_client = redis.Redis(connection_pool=self._redis_pool)
            
            # 测试连接
            await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.ping
            )
            
            self.logger.info("Redis连接初始化成功")
            
        except Exception as e:
            self.logger.error(f"Redis连接初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        try:
            if self._redis_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.close
                )
            
            if self._redis_pool:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_pool.disconnect
                )
            
            self._executor.shutdown(wait=True)
            
            self.logger.info("缓存管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭缓存管理器失败: {e}")
    
    async def get_task_status(self, task_key: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_key: 任务键
            
        Returns:
            任务状态数据或None
        """
        try:
            redis_key = f"task_status:{task_key}"
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.get, redis_key
            )
            
            if data:
                self.stats['cache_hits'] += 1
                self.monitoring.record_cache_operation(hit=True)
                return json.loads(data)
            else:
                self.stats['cache_misses'] += 1
                self.monitoring.record_cache_operation(hit=False)
                return None
                
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {e}")
            self.stats['errors'] += 1
            return None
    
    async def set_task_status(self, 
                            task_key: str, 
                            status_data: Dict[str, Any]):
        """设置任务状态
        
        Args:
            task_key: 任务键
            status_data: 状态数据
        """
        try:
            redis_key = f"task_status:{task_key}"
            data = json.dumps(status_data, ensure_ascii=False)
            
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self._redis_client.setex,
                redis_key,
                self.config.task_status_ttl,
                data
            )
            
        except Exception as e:
            self.logger.error(f"设置任务状态失败: {e}")
            self.stats['errors'] += 1
    
    async def get_content_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """获取内容哈希缓存
        
        Args:
            content_hash: 内容哈希
            
        Returns:
            缓存数据或None
        """
        try:
            redis_key = f"content_hash:{content_hash}"
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.get, redis_key
            )
            
            if data:
                self.stats['cache_hits'] += 1
                return json.loads(data)
            else:
                self.stats['cache_misses'] += 1
                return None
                
        except Exception as e:
            self.logger.error(f"获取内容哈希缓存失败: {e}")
            self.stats['errors'] += 1
            return None
    
    async def set_content_hash(self, 
                             content_hash: str, 
                             cache_data: Dict[str, Any]):
        """设置内容哈希缓存
        
        Args:
            content_hash: 内容哈希
            cache_data: 缓存数据
        """
        try:
            redis_key = f"content_hash:{content_hash}"
            data = json.dumps(cache_data, ensure_ascii=False)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._redis_client.setex,
                redis_key,
                self.config.content_hash_ttl,
                data
            )
            
        except Exception as e:
            self.logger.error(f"设置内容哈希缓存失败: {e}")
            self.stats['errors'] += 1
    
    async def check_url_bloom_filter(self, url: str) -> bool:
        """检查URL是否在Bloom Filter中
        
        Args:
            url: URL
            
        Returns:
            是否可能存在
        """
        try:
            result = await self.url_bloom_filter.contains(self._redis_client, url)
            
            if result:
                self.stats['bloom_filter_hits'] += 1
            else:
                self.stats['bloom_filter_misses'] += 1
            
            return result
            
        except Exception as e:
            self.logger.error(f"检查URL Bloom Filter失败: {e}")
            self.stats['errors'] += 1
            return False
    
    async def add_url_to_bloom_filter(self, url: str):
        """添加URL到Bloom Filter
        
        Args:
            url: URL
        """
        try:
            await self.url_bloom_filter.add(self._redis_client, url)
            
        except Exception as e:
            self.logger.error(f"添加URL到Bloom Filter失败: {e}")
            self.stats['errors'] += 1
    
    async def get_context_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取上下文数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            上下文数据或None
        """
        try:
            redis_key = f"context:{task_id}"
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.get, redis_key
            )
            
            if data:
                self.stats['cache_hits'] += 1
                return json.loads(data)
            else:
                self.stats['cache_misses'] += 1
                return None
                
        except Exception as e:
            self.logger.error(f"获取上下文数据失败: {e}")
            self.stats['errors'] += 1
            return None
    
    async def set_context_data(self, 
                             task_id: str, 
                             context_data: Dict[str, Any]):
        """设置上下文数据
        
        Args:
            task_id: 任务ID
            context_data: 上下文数据
        """
        try:
            redis_key = f"context:{task_id}"
            data = json.dumps(context_data, ensure_ascii=False)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._redis_client.setex,
                redis_key,
                self.config.context_data_ttl,
                data
            )
            
        except Exception as e:
            self.logger.error(f"设置上下文数据失败: {e}")
            self.stats['errors'] += 1
    
    async def delete_context_data(self, task_id: str):
        """删除上下文数据
        
        Args:
            task_id: 任务ID
        """
        try:
            redis_key = f"context:{task_id}"
            await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.delete, redis_key
            )
            
        except Exception as e:
            self.logger.error(f"删除上下文数据失败: {e}")
            self.stats['errors'] += 1
    
    async def clear_expired_data(self):
        """清理过期数据"""
        try:
            # Redis会自动清理过期数据，这里主要是清理一些特殊情况
            
            # 清理长时间未活动的上下文
            pattern = "context:*"
            keys = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.keys, pattern
            )
            
            expired_count = 0
            for key in keys:
                ttl = await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.ttl, key
                )
                
                # 如果TTL小于1小时，认为即将过期
                if 0 < ttl < 3600:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._redis_client.delete, key
                    )
                    expired_count += 1
            
            if expired_count > 0:
                self.logger.info(f"清理了{expired_count}个即将过期的缓存项")
            
        except Exception as e:
            self.logger.error(f"清理过期数据失败: {e}")
            self.stats['errors'] += 1
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            # Redis信息
            redis_info = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.info, 'memory'
            )
            
            # 键统计
            total_keys = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.dbsize
            )
            
            return {
                'cache_stats': self.stats.copy(),
                'redis_memory_used': redis_info.get('used_memory_human', 'N/A'),
                'redis_memory_peak': redis_info.get('used_memory_peak_human', 'N/A'),
                'total_keys': total_keys,
                'bloom_filter_capacity': self.url_bloom_filter.capacity,
                'bloom_filter_error_rate': self.url_bloom_filter.error_rate
            }
            
        except Exception as e:
            self.logger.error(f"获取缓存统计失败: {e}")
            return {'error': str(e)}
    
    async def health_check(self) -> bool:
        """健康检查
        
        Returns:
            是否健康
        """
        try:
            # 测试Redis连接
            await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.ping
            )
            
            # 测试基本操作
            test_key = "health_check:test"
            test_value = "ok"
            
            await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.setex, test_key, 10, test_value
            )
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.get, test_key
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, self._redis_client.delete, test_key
            )
            
            return result == test_value
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False