"""去重系统配置模块"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class MonitoringConfig:
    """监控配置"""
    # 性能阈值
    max_response_time_ms: int = 100  # 最大响应时间（毫秒）
    max_error_rate: float = 0.02  # 最大错误率（2%）
    min_accuracy_rate: float = 0.95  # 最小准确率（95%）
    
    # 告警配置
    alert_cooldown_seconds: int = 300  # 告警冷却时间（5分钟）
    max_alerts_per_hour: int = 10  # 每小时最大告警数
    
    # 指标收集
    metrics_retention_hours: int = 24  # 指标保留时间（小时）
    metrics_collection_interval_seconds: int = 60  # 指标收集间隔（秒）
    
    # 健康检查
    health_check_interval_seconds: int = 30  # 健康检查间隔（秒）
    health_check_timeout_seconds: int = 5  # 健康检查超时（秒）

@dataclass
class CacheConfig:
    """缓存配置"""
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_timeout_seconds: int = 5
    
    # 缓存策略
    default_ttl_seconds: int = 3600  # 默认TTL（1小时）
    max_memory_mb: int = 512  # 最大内存使用（MB）
    eviction_policy: str = "allkeys-lru"  # 淘汰策略
    
    # Bloom Filter配置
    bloom_filter_capacity: int = 1000000  # 布隆过滤器容量
    bloom_filter_error_rate: float = 0.001  # 布隆过滤器错误率
    bloom_filter_ttl_seconds: int = 86400  # 布隆过滤器TTL（24小时）

@dataclass
class DatabaseConfig:
    """数据库配置"""
    # MongoDB配置
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "newshub"
    collection_name: str = "crawler_contents"
    
    # 连接池配置
    max_pool_size: int = 100
    min_pool_size: int = 10
    max_idle_time_ms: int = 30000
    
    # 查询配置
    query_timeout_seconds: int = 30
    batch_size: int = 1000
    max_retries: int = 3

@dataclass
class DeduplicationConfig:
    """去重配置"""
    # 去重策略
    enable_content_hash: bool = True
    enable_url_check: bool = True
    enable_title_author_check: bool = True
    enable_semantic_similarity: bool = False  # 语义相似度检查（可选）
    enable_time_window: bool = True
    
    # 相似度阈值
    semantic_similarity_threshold: float = 0.85
    title_similarity_threshold: float = 0.9
    content_similarity_threshold: float = 0.8
    
    # 时间窗口
    time_window_hours: int = 24  # 时间窗口（小时）
    
    # 性能优化
    enable_batch_processing: bool = True
    batch_size: int = 100
    enable_parallel_processing: bool = True
    max_workers: int = 4

class Config:
    """统一配置管理器"""
    
    def __init__(self):
        self.monitoring = MonitoringConfig()
        self.cache = CacheConfig()
        self.database = DatabaseConfig()
        self.deduplication = DeduplicationConfig()
        
        # 从环境变量加载配置
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 监控配置
        self.monitoring.max_response_time_ms = int(
            os.getenv("DEDUP_MAX_RESPONSE_TIME_MS", self.monitoring.max_response_time_ms)
        )
        self.monitoring.max_error_rate = float(
            os.getenv("DEDUP_MAX_ERROR_RATE", self.monitoring.max_error_rate)
        )
        self.monitoring.min_accuracy_rate = float(
            os.getenv("DEDUP_MIN_ACCURACY_RATE", self.monitoring.min_accuracy_rate)
        )
        
        # 缓存配置
        self.cache.redis_host = os.getenv("REDIS_HOST", self.cache.redis_host)
        self.cache.redis_port = int(os.getenv("REDIS_PORT", self.cache.redis_port))
        self.cache.redis_password = os.getenv("REDIS_PASSWORD")
        
        # 数据库配置
        self.database.mongodb_uri = os.getenv("MONGODB_URI", self.database.mongodb_uri)
        self.database.database_name = os.getenv("DATABASE_NAME", self.database.database_name)
        
        # 去重配置
        self.deduplication.enable_semantic_similarity = (
            os.getenv("DEDUP_ENABLE_SEMANTIC", "false").lower() == "true"
        )
        self.deduplication.semantic_similarity_threshold = float(
            os.getenv("DEDUP_SEMANTIC_THRESHOLD", self.deduplication.semantic_similarity_threshold)
        )
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        return {
            "monitoring": {
                "max_response_time_ms": self.monitoring.max_response_time_ms,
                "max_error_rate": self.monitoring.max_error_rate,
                "min_accuracy_rate": self.monitoring.min_accuracy_rate,
                "alert_cooldown_seconds": self.monitoring.alert_cooldown_seconds,
                "max_alerts_per_hour": self.monitoring.max_alerts_per_hour,
            },
            "cache": {
                "redis_host": self.cache.redis_host,
                "redis_port": self.cache.redis_port,
                "default_ttl_seconds": self.cache.default_ttl_seconds,
                "bloom_filter_capacity": self.cache.bloom_filter_capacity,
                "bloom_filter_error_rate": self.cache.bloom_filter_error_rate,
            },
            "database": {
                "mongodb_uri": self.database.mongodb_uri,
                "database_name": self.database.database_name,
                "collection_name": self.database.collection_name,
                "max_pool_size": self.database.max_pool_size,
            },
            "deduplication": {
                "enable_content_hash": self.deduplication.enable_content_hash,
                "enable_url_check": self.deduplication.enable_url_check,
                "enable_title_author_check": self.deduplication.enable_title_author_check,
                "enable_semantic_similarity": self.deduplication.enable_semantic_similarity,
                "semantic_similarity_threshold": self.deduplication.semantic_similarity_threshold,
                "time_window_hours": self.deduplication.time_window_hours,
            }
        }
    
    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 验证阈值范围
            assert 0 < self.monitoring.max_error_rate < 1, "错误率必须在0-1之间"
            assert 0 < self.monitoring.min_accuracy_rate < 1, "准确率必须在0-1之间"
            assert 0 < self.deduplication.semantic_similarity_threshold < 1, "相似度阈值必须在0-1之间"
            
            # 验证时间配置
            assert self.monitoring.alert_cooldown_seconds > 0, "告警冷却时间必须大于0"
            assert self.cache.default_ttl_seconds > 0, "缓存TTL必须大于0"
            assert self.deduplication.time_window_hours > 0, "时间窗口必须大于0"
            
            # 验证容量配置
            assert self.cache.bloom_filter_capacity > 0, "布隆过滤器容量必须大于0"
            assert self.database.max_pool_size > 0, "数据库连接池大小必须大于0"
            
            return True
        except AssertionError as e:
            print(f"配置验证失败: {e}")
            return False

# 全局配置实例
_config_instance = None

def get_config() -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
        if not _config_instance.validate():
            raise ValueError("配置验证失败")
    return _config_instance

def reload_config() -> Config:
    """重新加载配置"""
    global _config_instance
    _config_instance = None
    return get_config()