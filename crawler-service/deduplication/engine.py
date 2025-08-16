"""去重引擎核心模块

实现多层次去重机制：
1. 任务级去重 - 防止重复任务创建
2. URL级去重 - 基于URL的快速去重
3. 内容哈希去重 - 基于内容MD5/SHA256的精确去重
4. 语义相似度去重 - 基于文本相似度的智能去重
5. 时间窗口去重 - 基于时间窗口的重复检测
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
from difflib import SequenceMatcher

from .context import DeduplicationContext
from .cache_manager import CacheManager
from .index_manager import IndexManager
from .monitoring import get_monitoring_service, get_error_recovery_service


class DuplicateType(Enum):
    """重复类型枚举"""
    TASK_DUPLICATE = "task_duplicate"  # 任务级重复
    URL_DUPLICATE = "url_duplicate"    # URL级重复
    CONTENT_HASH_DUPLICATE = "content_hash_duplicate"  # 内容哈希重复
    SEMANTIC_DUPLICATE = "semantic_duplicate"  # 语义相似重复
    TIME_WINDOW_DUPLICATE = "time_window_duplicate"  # 时间窗口重复
    TITLE_DUPLICATE = "title_duplicate"  # 标题重复（同平台时间窗口）
    NO_DUPLICATE = "no_duplicate"  # 无重复


@dataclass
class DuplicationResult:
    """去重检测结果"""
    is_duplicate: bool
    duplicate_type: DuplicateType
    confidence: float  # 置信度 0-1
    duplicate_id: Optional[str] = None  # 重复项的ID
    similarity_score: Optional[float] = None  # 相似度分数
    reason: Optional[str] = None  # 重复原因描述
    metadata: Optional[Dict[str, Any]] = None  # 额外元数据


class DeduplicationEngine:
    """去重引擎核心类
    
    实现多层次去重检测，每个爬取任务拥有独立的去重上下文
    """
    
    def __init__(self, 
                 cache_manager: CacheManager,
                 index_manager: IndexManager,
                 similarity_threshold: float = 0.85,
                 time_window_hours: int = 24):
        """
        初始化去重引擎
        
        Args:
            cache_manager: 缓存管理器
            index_manager: 索引管理器
            similarity_threshold: 语义相似度阈值
            time_window_hours: 时间窗口（小时）
        """
        self.cache_manager = cache_manager
        self.index_manager = index_manager
        self.similarity_threshold = similarity_threshold
        self.time_window_hours = time_window_hours
        self.logger = logging.getLogger(__name__)
        
        # 监控服务
        self.monitoring = get_monitoring_service()
        self.error_recovery = get_error_recovery_service()
        
        # 任务上下文缓存
        self._contexts: Dict[str, DeduplicationContext] = {}
    
    def get_context(self, task_id: str) -> DeduplicationContext:
        """获取或创建任务上下文"""
        if task_id not in self._contexts:
            self._contexts[task_id] = DeduplicationContext(
                task_id=task_id,
                cache_manager=self.cache_manager,
                index_manager=self.index_manager
            )
        return self._contexts[task_id]
    
    async def check_duplicate(self, 
                            task_id: str,
                            url: str,
                            content: str,
                            title: str = "",
                            platform: str = "",
                            creator_url: str = "") -> DuplicationResult:
        """执行完整的去重检测
        
        Args:
            task_id: 任务ID
            url: 内容URL
            content: 内容文本
            title: 标题
            platform: 平台名称
            creator_url: 创建者URL
            
        Returns:
            DuplicationResult: 去重检测结果
        """
        start_time = time.time()
        error = None
        result = None
        context = self.get_context(task_id)
        
        try:
            # 1. 任务级去重检测
            task_result = await self._check_task_duplicate(
                context, platform, creator_url
            )
            if task_result.is_duplicate:
                result = task_result
                return result
            
            # 2. URL级去重检测
            url_result = await self._check_url_duplicate(context, url)
            if url_result.is_duplicate:
                result = url_result
                return result
            
            # 3. 内容哈希去重检测
            hash_result = await self._check_content_hash_duplicate(
                context, content, title
            )
            if hash_result.is_duplicate:
                result = hash_result
                return result
            
            # 4. 标题去重（同平台时间窗口内）
            title_result = await self._check_title_duplicate(
                context, title, platform
            )
            if title_result.is_duplicate:
                result = title_result
                return result

            # 5. 语义相似度去重检测
            semantic_result = await self._check_semantic_duplicate(
                context, content, title
            )
            if semantic_result.is_duplicate:
                result = semantic_result
                return result
            
            # 6. 时间窗口去重检测（URL）
            time_result = await self._check_time_window_duplicate(
                context, url, content
            )
            if time_result.is_duplicate:
                result = time_result
                return result
            
            # 无重复，记录到上下文
            await self._record_content(context, url, content, title)
            
            result = DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0,
                reason="通过所有去重检测"
            )
            return result
            
        except Exception as e:
            error = e
            self.logger.error(f"去重检测失败: {e}")
            
            # 尝试错误恢复
            recovery_context = {
                "url": url,
                "task_id": task_id,
                "operation": "duplicate_check"
            }
            
            await self.error_recovery.handle_error(e, recovery_context)
            
            # 发生错误时，为安全起见返回不重复
            result = DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=0.0,
                reason=f"检测异常: {str(e)}"
            )
            return result
            
        finally:
            # 记录监控指标
            response_time = time.time() - start_time
            duplicate_type = result.duplicate_type if result and result.is_duplicate else None
            self.monitoring.record_check(
                is_duplicate=result.is_duplicate if result else False,
                response_time=response_time,
                duplicate_type=duplicate_type,
                error=error
            )
    
    async def _check_task_duplicate(self, 
                                  context: DeduplicationContext,
                                  platform: str,
                                  creator_url: str) -> DuplicationResult:
        """检查任务级重复"""
        if not platform or not creator_url:
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0
            )
        
        # 生成任务唯一标识
        task_key = f"task:{platform}:{creator_url}"
        
        # 检查缓存中是否存在相同任务
        existing_task = await self.cache_manager.get_task_status(task_key)
        if existing_task and existing_task.get('status') in ['pending', 'running']:
            return DuplicationResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.TASK_DUPLICATE,
                confidence=1.0,
                duplicate_id=existing_task.get('task_id'),
                reason=f"存在相同的{existing_task.get('status')}任务"
            )
        
        # 记录当前任务
        await self.cache_manager.set_task_status(task_key, {
            'task_id': context.task_id,
            'status': 'running',
            'platform': platform,
            'creator_url': creator_url,
            'created_at': datetime.now().isoformat()
        })
        
        return DuplicationResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NO_DUPLICATE,
            confidence=1.0
        )
    
    async def _check_url_duplicate(self, 
                                 context: DeduplicationContext,
                                 url: str) -> DuplicationResult:
        """检查URL级重复"""
        if not url:
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0
            )
        
        # 标准化URL
        normalized_url = self._normalize_url(url)
        
        # 检查Bloom Filter
        if await self.cache_manager.check_url_bloom_filter(normalized_url):
            # 可能重复，进行精确检查
            existing_content = await self.index_manager.get_content_by_url(normalized_url)
            if existing_content:
                return DuplicationResult(
                    is_duplicate=True,
                    duplicate_type=DuplicateType.URL_DUPLICATE,
                    confidence=1.0,
                    duplicate_id=existing_content.get('_id'),
                    reason=f"URL已存在: {normalized_url}"
                )
        
        # 添加到Bloom Filter
        await self.cache_manager.add_url_to_bloom_filter(normalized_url)
        
        return DuplicationResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NO_DUPLICATE,
            confidence=1.0
        )
    
    async def _check_content_hash_duplicate(self, 
                                          context: DeduplicationContext,
                                          content: str,
                                          title: str = "") -> DuplicationResult:
        """检查内容哈希重复"""
        if not content:
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0
            )
        
        # 计算内容哈希
        content_hash = self._calculate_content_hash(content, title)
        
        # 检查缓存
        cached_result = await self.cache_manager.get_content_hash(content_hash)
        if cached_result:
            return DuplicationResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.CONTENT_HASH_DUPLICATE,
                confidence=1.0,
                duplicate_id=cached_result.get('content_id'),
                reason=f"内容哈希重复: {content_hash[:16]}..."
            )
        
        # 检查数据库索引
        existing_content = await self.index_manager.get_content_by_hash(content_hash)
        if existing_content:
            # 缓存结果
            await self.cache_manager.set_content_hash(content_hash, {
                'content_id': existing_content.get('_id'),
                'created_at': datetime.now().isoformat()
            })
            
            return DuplicationResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.CONTENT_HASH_DUPLICATE,
                confidence=1.0,
                duplicate_id=existing_content.get('_id'),
                reason=f"内容哈希重复: {content_hash[:16]}..."
            )
        
        return DuplicationResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NO_DUPLICATE,
            confidence=1.0
        )
    
    async def _check_semantic_duplicate(self, 
                                      context: DeduplicationContext,
                                      content: str,
                                      title: str = "") -> DuplicationResult:
        """检查语义相似度重复"""
        if not content or len(content.strip()) < 50:  # 内容太短，跳过语义检测
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0
            )
        
        # 获取最近的内容进行相似度比较
        recent_contents = await self.index_manager.get_recent_contents(
            limit=100,  # 限制比较数量以提高性能
            hours=self.time_window_hours * 7  # 扩大时间窗口
        )
        
        max_similarity = 0.0
        most_similar_content = None
        
        for existing_content in recent_contents:
            similarity = self._calculate_text_similarity(
                content, existing_content.get('content', '')
            )
            
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_content = existing_content
        
        if max_similarity >= self.similarity_threshold:
            return DuplicationResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.SEMANTIC_DUPLICATE,
                confidence=max_similarity,
                duplicate_id=most_similar_content.get('_id'),
                similarity_score=max_similarity,
                reason=f"语义相似度过高: {max_similarity:.2f}"
            )
        
        return DuplicationResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NO_DUPLICATE,
            confidence=1.0 - max_similarity,
            similarity_score=max_similarity
        )
    
    async def _check_time_window_duplicate(self, 
                                         context: DeduplicationContext,
                                         url: str,
                                         content: str) -> DuplicationResult:
        """检查时间窗口重复"""
        if not url:
            return DuplicationResult(
                is_duplicate=False,
                duplicate_type=DuplicateType.NO_DUPLICATE,
                confidence=1.0
            )
        
        # 检查时间窗口内的相同URL
        time_threshold = datetime.now() - timedelta(hours=self.time_window_hours)
        
        recent_content = await self.index_manager.get_content_by_url_and_time(
            url, time_threshold
        )
        
        if recent_content:
            return DuplicationResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.TIME_WINDOW_DUPLICATE,
                confidence=1.0,
                duplicate_id=recent_content.get('_id'),
                reason=f"时间窗口内重复: {self.time_window_hours}小时内已爬取"
            )
        
        return DuplicationResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NO_DUPLICATE,
            confidence=1.0
        )
    
    async def _record_content(self, 
                            context: DeduplicationContext,
                            url: str,
                            content: str,
                            title: str = ""):
        """记录内容到上下文和缓存"""
        # 计算哈希
        content_hash = self._calculate_content_hash(content, title)
        normalized_url = self._normalize_url(url)
        
        # 记录到上下文
        context.add_processed_url(normalized_url)
        context.add_content_hash(content_hash)
        
        # 更新缓存
        await self.cache_manager.set_content_hash(content_hash, {
            'url': normalized_url,
            'created_at': datetime.now().isoformat()
        })
    
    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        # 移除查询参数中的时间戳等动态参数
        import urllib.parse as urlparse
        
        parsed = urlparse.urlparse(url)
        query_params = urlparse.parse_qs(parsed.query)
        
        # 移除常见的动态参数
        dynamic_params = ['timestamp', 'ts', '_t', 'time', 'rand', 'random']
        for param in dynamic_params:
            query_params.pop(param, None)
        
        # 重构URL
        new_query = urlparse.urlencode(query_params, doseq=True)
        normalized = urlparse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''  # 移除fragment
        ))
        
        return normalized.lower().strip()
    
    def _calculate_content_hash(self, content: str, title: str = "") -> str:
        """计算内容哈希"""
        # 组合标题和内容
        combined_content = f"{title}\n{content}".strip()
        
        # 标准化文本（移除多余空白、统一换行符）
        normalized_content = ' '.join(combined_content.split())
        
        # 计算SHA256哈希
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 使用SequenceMatcher计算相似度
        matcher = SequenceMatcher(None, text1.lower(), text2.lower())
        return matcher.ratio()
    
    async def cleanup_context(self, task_id: str):
        """清理任务上下文"""
        if task_id in self._contexts:
            context = self._contexts[task_id]
            await context.cleanup()
            del self._contexts[task_id]
    
    async def get_statistics(self, task_id: str) -> Dict[str, Any]:
        """获取去重统计信息"""
        context = self.get_context(task_id)
        return {
            'task_id': task_id,
            'processed_urls': len(context.processed_urls),
            'content_hashes': len(context.content_hashes),
            'created_at': context.created_at.isoformat(),
            'last_activity': context.last_activity.isoformat() if context.last_activity else None
        }