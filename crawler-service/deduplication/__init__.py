"""去重系统模块

该模块实现了完整的爬取任务去重系统，包括：
- DeduplicationEngine: 核心去重引擎
- DeduplicationContext: 任务上下文管理
- CacheManager: 缓存管理器
- IndexManager: 索引管理器
"""

from .engine import DeduplicationEngine
from .context import DeduplicationContext
from .cache_manager import CacheManager
from .index_manager import IndexManager

__all__ = [
    'DeduplicationEngine',
    'DeduplicationContext', 
    'CacheManager',
    'IndexManager'
]