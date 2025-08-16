#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去重系统数据类型定义
定义去重系统中使用的所有数据结构和枚举类型
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

class DuplicateType(Enum):
    """
    重复类型枚举
    """
    NONE = "none"  # 不重复
    CONTENT_HASH = "content_hash"  # 内容哈希重复
    URL = "url"  # URL重复
    TITLE_AUTHOR = "title_author"  # 标题+作者重复
    SEMANTIC = "semantic"  # 语义相似
    TIME_WINDOW = "time_window"  # 时间窗口重复

@dataclass
class ContentItem:
    """
    内容项数据结构
    """
    url: str
    title: str
    content: str
    author: str
    published_at: str
    platform: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "published_at": self.published_at,
            "platform": self.platform,
            "content_hash": self.content_hash,
            "metadata": self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentItem':
        """
        从字典创建ContentItem实例
        """
        return cls(
            url=data["url"],
            title=data["title"],
            content=data["content"],
            author=data["author"],
            published_at=data["published_at"],
            platform=data.get("platform"),
            content_hash=data.get("content_hash"),
            metadata=data.get("metadata")
        )

@dataclass
class DuplicateCheckResult:
    """
    去重检查结果
    """
    is_duplicate: bool
    duplicate_type: DuplicateType
    confidence: float = 0.0
    existing_content_id: Optional[str] = None
    similarity_score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "is_duplicate": self.is_duplicate,
            "duplicate_type": self.duplicate_type.value,
            "confidence": self.confidence,
            "existing_content_id": self.existing_content_id,
            "similarity_score": self.similarity_score,
            "details": self.details or {}
        }

@dataclass
class DeduplicationStats:
    """
    去重统计信息
    """
    total_checks: int = 0
    duplicates_found: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    error_count: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """
        缓存命中率
        """
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def duplicate_rate(self) -> float:
        """
        重复率
        """
        return self.duplicates_found / self.total_checks if self.total_checks > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "total_checks": self.total_checks,
            "duplicates_found": self.duplicates_found,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "duplicate_rate": self.duplicate_rate,
            "avg_response_time": self.avg_response_time,
            "error_count": self.error_count
        }

@dataclass
class Alert:
    """
    告警信息
    """
    id: str
    type: str
    message: str
    severity: str  # "low", "medium", "high", "critical"
    created_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def is_active(self) -> bool:
        """
        是否为活跃告警
        """
        return self.resolved_at is None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "id": self.id,
            "type": self.type,
            "message": self.message,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "is_active": self.is_active,
            "metadata": self.metadata or {}
        }

@dataclass
class Metric:
    """
    性能指标
    """
    name: str
    value: float
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags or {}
        }

@dataclass
class PerformanceStats:
    """
    性能统计信息
    """
    total_checks: int = 0
    duplicates_found: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    
    def update(self, response_time: float, is_duplicate: bool = False, has_error: bool = False):
        """
        更新统计信息
        """
        self.total_checks += 1
        
        if is_duplicate:
            self.duplicates_found += 1
        
        if has_error:
            self.error_count += 1
        
        # 更新响应时间统计
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)
        
        # 计算平均响应时间
        if self.total_checks == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                (self.avg_response_time * (self.total_checks - 1) + response_time) / 
                self.total_checks
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        """
        return {
            "total_checks": self.total_checks,
            "duplicates_found": self.duplicates_found,
            "error_count": self.error_count,
            "avg_response_time": self.avg_response_time,
            "min_response_time": self.min_response_time if self.min_response_time != float('inf') else 0.0,
            "max_response_time": self.max_response_time
        }