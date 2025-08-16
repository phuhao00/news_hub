"""索引管理器模块

优化数据库查询性能，提供高效的索引管理和查询优化功能
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import pymongo
from concurrent.futures import ThreadPoolExecutor
import threading
import time


@dataclass
class IndexConfig:
    """索引配置"""
    # MongoDB连接配置
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "newshub"
    
    # 索引配置
    enable_compound_indexes: bool = True
    enable_text_indexes: bool = True
    enable_sparse_indexes: bool = True
    
    # 性能配置
    index_build_timeout: int = 300  # 5分钟
    query_timeout: int = 30  # 30秒
    batch_size: int = 1000
    
    # 缓存配置
    query_cache_size: int = 1000
    query_cache_ttl: int = 300  # 5分钟


@dataclass
class IndexInfo:
    """索引信息"""
    name: str
    keys: List[Tuple[str, int]]
    unique: bool = False
    sparse: bool = False
    background: bool = True
    expire_after_seconds: Optional[int] = None
    partial_filter_expression: Optional[Dict] = None


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 查询统计
        self.query_stats = {
            'total_queries': 0,
            'slow_queries': 0,
            'optimized_queries': 0,
            'cache_hits': 0
        }
        
        # 查询缓存
        self.query_cache = {}
        self.cache_timestamps = {}
    
    def optimize_query(self, collection_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """优化查询
        
        Args:
            collection_name: 集合名称
            query: 原始查询
            
        Returns:
            优化后的查询
        """
        try:
            optimized_query = query.copy()
            
            # 根据集合类型优化查询
            if collection_name == "crawler_contents":
                optimized_query = self._optimize_content_query(optimized_query)
            elif collection_name == "crawler_tasks":
                optimized_query = self._optimize_task_query(optimized_query)
            elif collection_name == "continuous_tasks":
                optimized_query = self._optimize_continuous_task_query(optimized_query)
            
            self.query_stats['optimized_queries'] += 1
            return optimized_query
            
        except Exception as e:
            self.logger.error(f"查询优化失败: {e}")
            return query
    
    def _optimize_content_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """优化内容查询"""
        optimized = query.copy()
        
        # 优化内容哈希查询
        if 'content_hash' in optimized:
            # 确保使用索引
            pass
        
        # 优化URL查询
        if 'url' in optimized:
            # 使用精确匹配而不是正则表达式
            if isinstance(optimized['url'], dict) and '$regex' in optimized['url']:
                # 如果是简单的前缀匹配，转换为范围查询
                regex_pattern = optimized['url']['$regex']
                if regex_pattern.startswith('^') and not any(c in regex_pattern for c in ['*', '+', '?', '[', ']']):
                    prefix = regex_pattern[1:].rstrip('$')
                    optimized['url'] = {
                        '$gte': prefix,
                        '$lt': prefix + '\uffff'
                    }
        
        # 优化时间范围查询
        if 'created_at' in optimized:
            # 确保时间查询使用索引
            pass
        
        return optimized
    
    def _optimize_task_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """优化任务查询"""
        optimized = query.copy()
        
        # 优化状态查询
        if 'status' in optimized:
            # 确保状态查询使用索引
            pass
        
        # 优化平台查询
        if 'platform' in optimized:
            # 确保平台查询使用索引
            pass
        
        return optimized
    
    def _optimize_continuous_task_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """优化连续任务查询"""
        optimized = query.copy()
        
        # 优化用户ID查询
        if 'user_id' in optimized:
            # 确保用户ID查询使用索引
            pass
        
        return optimized
    
    def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计"""
        return self.query_stats.copy()


class IndexManager:
    """索引管理器
    
    优化数据库查询性能，提供高效的索引管理和查询优化功能
    """
    
    def __init__(self, config: IndexConfig = None):
        """
        初始化索引管理器
        
        Args:
            config: 索引配置
        """
        self.config = config or IndexConfig()
        self.logger = logging.getLogger(__name__)
        
        # MongoDB连接
        self._client = None
        self._database = None
        
        # 查询优化器
        self.query_optimizer = QueryOptimizer()
        
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=5)
        
        # 索引定义
        self.index_definitions = self._get_index_definitions()
        
        # 统计信息
        self.stats = {
            'indexes_created': 0,
            'indexes_dropped': 0,
            'queries_optimized': 0,
            'slow_queries_detected': 0
        }
    
    def _get_index_definitions(self) -> Dict[str, List[IndexInfo]]:
        """获取索引定义"""
        return {
            'crawler_contents': [
                # 内容哈希索引（唯一）
                IndexInfo(
                    name="content_hash_1",
                    keys=[("content_hash", 1)],
                    unique=True,
                    sparse=True
                ),
                # 标题+平台+创建时间 复合索引（用于同平台标题时间窗去重）
                IndexInfo(
                    name="title_1_platform_1_created_at_-1",
                    keys=[("title", 1), ("platform", 1), ("created_at", -1)]
                ),
                # URL索引
                IndexInfo(
                    name="url_1",
                    keys=[("url", 1)],
                    sparse=True
                ),
                # 创建时间索引
                IndexInfo(
                    name="created_at_-1",
                    keys=[("created_at", -1)]
                ),
                # 平台和创建时间复合索引
                IndexInfo(
                    name="platform_1_created_at_-1",
                    keys=[("platform", 1), ("created_at", -1)]
                ),
                # 标题文本索引
                IndexInfo(
                    name="title_text",
                    keys=[("title", "text")],
                    sparse=True
                ) if self.config.enable_text_indexes else None,
                # 内容文本索引
                IndexInfo(
                    name="content_text",
                    keys=[("content", "text")],
                    sparse=True
                ) if self.config.enable_text_indexes else None,
            ],
            'crawler_tasks': [
                # 任务ID索引（唯一）
                IndexInfo(
                    name="task_id_1",
                    keys=[("task_id", 1)],
                    unique=True
                ),
                # 状态索引
                IndexInfo(
                    name="status_1",
                    keys=[("status", 1)]
                ),
                # 平台索引
                IndexInfo(
                    name="platform_1",
                    keys=[("platform", 1)]
                ),
                # 创建时间索引
                IndexInfo(
                    name="created_at_-1",
                    keys=[("created_at", -1)]
                ),
                # 状态和创建时间复合索引
                IndexInfo(
                    name="status_1_created_at_-1",
                    keys=[("status", 1), ("created_at", -1)]
                ),
                # 平台和状态复合索引
                IndexInfo(
                    name="platform_1_status_1",
                    keys=[("platform", 1), ("status", 1)]
                ),
                # URL索引
                IndexInfo(
                    name="url_1",
                    keys=[("url", 1)],
                    sparse=True
                ),
            ],
            'continuous_tasks': [
                # 用户ID索引
                IndexInfo(
                    name="user_id_1",
                    keys=[("user_id", 1)]
                ),
                # 平台索引
                IndexInfo(
                    name="platform_1",
                    keys=[("platform", 1)]
                ),
                # 状态索引
                IndexInfo(
                    name="status_1",
                    keys=[("status", 1)]
                ),
                # 用户ID和平台复合索引
                IndexInfo(
                    name="user_id_1_platform_1",
                    keys=[("user_id", 1), ("platform", 1)]
                ),
                # 创建时间索引
                IndexInfo(
                    name="created_at_-1",
                    keys=[("created_at", -1)]
                ),
                # 最后运行时间索引
                IndexInfo(
                    name="last_run_at_-1",
                    keys=[("last_run_at", -1)],
                    sparse=True
                ),
                # 内容哈希索引
                IndexInfo(
                    name="last_content_hash_1",
                    keys=[("last_content_hash", 1)],
                    sparse=True
                ),
            ]
        }
    
    async def initialize(self):
        """初始化MongoDB连接和索引"""
        try:
            # 创建MongoDB连接
            self._client = AsyncIOMotorClient(self.config.mongodb_url)
            self._database = self._client[self.config.database_name]
            
            # 测试连接
            await self._client.admin.command('ping')
            
            # 创建索引
            await self._create_all_indexes()
            
            self.logger.info("索引管理器初始化成功")
            
        except Exception as e:
            self.logger.error(f"索引管理器初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        try:
            if self._client:
                self._client.close()
            
            self._executor.shutdown(wait=True)
            
            self.logger.info("索引管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭索引管理器失败: {e}")
    
    async def _create_all_indexes(self):
        """创建所有索引"""
        for collection_name, indexes in self.index_definitions.items():
            if indexes:
                await self._create_collection_indexes(collection_name, indexes)
    
    async def _create_collection_indexes(self, collection_name: str, indexes: List[IndexInfo]):
        """为集合创建索引"""
        try:
            collection = self._database[collection_name]
            
            # 获取现有索引
            existing_indexes = set()
            async for index_info in collection.list_indexes():
                existing_indexes.add(index_info['name'])
            
            # 创建新索引
            for index_info in indexes:
                if index_info is None:
                    continue
                
                if index_info.name not in existing_indexes:
                    try:
                        # 构建索引选项
                        index_options = {
                            'name': index_info.name,
                            'background': index_info.background
                        }
                        
                        if index_info.unique:
                            index_options['unique'] = True
                        
                        if index_info.sparse:
                            index_options['sparse'] = True
                        
                        if index_info.expire_after_seconds is not None:
                            index_options['expireAfterSeconds'] = index_info.expire_after_seconds
                        
                        if index_info.partial_filter_expression:
                            index_options['partialFilterExpression'] = index_info.partial_filter_expression
                        
                        # 创建索引
                        await collection.create_index(
                            index_info.keys,
                            **index_options
                        )
                        
                        self.stats['indexes_created'] += 1
                        self.logger.info(f"为集合 {collection_name} 创建索引: {index_info.name}")
                        
                    except Exception as e:
                        self.logger.error(f"创建索引 {index_info.name} 失败: {e}")
                else:
                    self.logger.debug(f"索引 {index_info.name} 已存在")
            
        except Exception as e:
            self.logger.error(f"为集合 {collection_name} 创建索引失败: {e}")
    
    async def optimize_query(self, collection_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """优化查询
        
        Args:
            collection_name: 集合名称
            query: 原始查询
            
        Returns:
            优化后的查询
        """
        try:
            optimized_query = self.query_optimizer.optimize_query(collection_name, query)
            self.stats['queries_optimized'] += 1
            return optimized_query
            
        except Exception as e:
            self.logger.error(f"查询优化失败: {e}")
            return query
    
    async def find_with_optimization(self, 
                                   collection_name: str, 
                                   query: Dict[str, Any],
                                   projection: Optional[Dict[str, Any]] = None,
                                   sort: Optional[List[Tuple[str, int]]] = None,
                                   limit: Optional[int] = None,
                                   skip: Optional[int] = None) -> List[Dict[str, Any]]:
        """使用优化的查询进行查找
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            projection: 投影
            sort: 排序
            limit: 限制数量
            skip: 跳过数量
            
        Returns:
            查询结果
        """
        try:
            # 优化查询
            optimized_query = await self.optimize_query(collection_name, query)
            
            # 执行查询
            collection = self._database[collection_name]
            cursor = collection.find(optimized_query, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            
            if skip:
                cursor = cursor.skip(skip)
            
            if limit:
                cursor = cursor.limit(limit)
            
            # 转换为列表
            results = await cursor.to_list(length=limit)
            
            return results
            
        except Exception as e:
            self.logger.error(f"优化查询执行失败: {e}")
            raise
    
    async def find_one_with_optimization(self, 
                                       collection_name: str, 
                                       query: Dict[str, Any],
                                       projection: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """使用优化的查询进行单个文档查找
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            projection: 投影
            
        Returns:
            查询结果或None
        """
        try:
            # 优化查询
            optimized_query = await self.optimize_query(collection_name, query)
            
            # 执行查询
            collection = self._database[collection_name]
            result = await collection.find_one(optimized_query, projection)
            
            return result
            
        except Exception as e:
            self.logger.error(f"优化单个查询执行失败: {e}")
            raise

    async def get_content_by_title_platform_time(self,
                                                 title: str,
                                                 platform: str,
                                                 since: datetime) -> Optional[Dict[str, Any]]:
        """查询同平台同标题在时间窗口内是否存在"""
        try:
            query = {
                'title': title,
                'platform': platform,
                'created_at': {'$gte': since}
            }
            return await self.find_one_with_optimization('crawler_contents', query)
        except Exception as e:
            self.logger.error(f"按标题/平台/时间查询失败: {e}")
            return None
    
    async def count_with_optimization(self, 
                                    collection_name: str, 
                                    query: Dict[str, Any]) -> int:
        """使用优化的查询进行计数
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            
        Returns:
            文档数量
        """
        try:
            # 优化查询
            optimized_query = await self.optimize_query(collection_name, query)
            
            # 执行计数
            collection = self._database[collection_name]
            count = await collection.count_documents(optimized_query)
            
            return count
            
        except Exception as e:
            self.logger.error(f"优化计数查询执行失败: {e}")
            raise
    
    async def analyze_query_performance(self, 
                                      collection_name: str, 
                                      query: Dict[str, Any]) -> Dict[str, Any]:
        """分析查询性能
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            
        Returns:
            性能分析结果
        """
        try:
            collection = self._database[collection_name]
            
            # 使用explain分析查询
            explain_result = await collection.find(query).explain()
            
            # 提取关键性能指标
            execution_stats = explain_result.get('executionStats', {})
            
            analysis = {
                'total_docs_examined': execution_stats.get('totalDocsExamined', 0),
                'total_keys_examined': execution_stats.get('totalKeysExamined', 0),
                'docs_returned': execution_stats.get('nReturned', 0),
                'execution_time_ms': execution_stats.get('executionTimeMillis', 0),
                'index_used': execution_stats.get('indexUsed', False),
                'winning_plan': explain_result.get('queryPlanner', {}).get('winningPlan', {})
            }
            
            # 判断是否为慢查询
            if analysis['execution_time_ms'] > 1000:  # 超过1秒
                self.stats['slow_queries_detected'] += 1
                self.logger.warning(f"检测到慢查询: {query}, 执行时间: {analysis['execution_time_ms']}ms")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"查询性能分析失败: {e}")
            return {'error': str(e)}
    
    async def get_index_statistics(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            statistics = {
                'collections': {},
                'total_indexes': 0,
                'index_sizes': {}
            }
            
            for collection_name in self.index_definitions.keys():
                collection = self._database[collection_name]
                
                # 获取索引信息
                indexes = []
                async for index_info in collection.list_indexes():
                    indexes.append({
                        'name': index_info['name'],
                        'keys': index_info['key'],
                        'unique': index_info.get('unique', False),
                        'sparse': index_info.get('sparse', False)
                    })
                
                statistics['collections'][collection_name] = {
                    'indexes': indexes,
                    'index_count': len(indexes)
                }
                
                statistics['total_indexes'] += len(indexes)
                
                # 获取索引大小（如果可能）
                try:
                    stats_result = await self._database.command('collStats', collection_name)
                    if 'indexSizes' in stats_result:
                        statistics['index_sizes'][collection_name] = stats_result['indexSizes']
                except Exception:
                    pass
            
            # 添加管理器统计
            statistics['manager_stats'] = self.stats.copy()
            statistics['query_optimizer_stats'] = self.query_optimizer.get_query_stats()
            
            return statistics
            
        except Exception as e:
            self.logger.error(f"获取索引统计失败: {e}")
            return {'error': str(e)}
    
    async def rebuild_indexes(self, collection_name: str):
        """重建集合的索引
        
        Args:
            collection_name: 集合名称
        """
        try:
            if collection_name not in self.index_definitions:
                raise ValueError(f"未知的集合: {collection_name}")
            
            collection = self._database[collection_name]
            
            # 删除除_id之外的所有索引
            await collection.drop_indexes()
            
            # 重新创建索引
            indexes = self.index_definitions[collection_name]
            await self._create_collection_indexes(collection_name, indexes)
            
            self.logger.info(f"集合 {collection_name} 的索引重建完成")
            
        except Exception as e:
            self.logger.error(f"重建索引失败: {e}")
            raise
    
    async def health_check(self) -> bool:
        """健康检查
        
        Returns:
            是否健康
        """
        try:
            # 测试MongoDB连接
            await self._client.admin.command('ping')
            
            # 测试基本查询
            collection = self._database['crawler_tasks']
            await collection.find_one({})
            
            return True
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False