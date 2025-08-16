"""去重系统监控和错误处理模块"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json

from .types import DuplicateType
from .config import get_config


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Alert:
    """告警信息"""
    level: AlertLevel
    message: str
    component: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details or {},
            "resolved": self.resolved
        }


@dataclass
class Metric:
    """性能指标"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime
    labels: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels or {}
        }


@dataclass
class PerformanceStats:
    """性能统计"""
    total_checks: int = 0
    duplicate_found: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    error_count: int = 0
    last_reset: datetime = None
    
    def __post_init__(self):
        if self.last_reset is None:
            self.last_reset = datetime.now()
    
    @property
    def duplicate_rate(self) -> float:
        """重复率"""
        if self.total_checks == 0:
            return 0.0
        return self.duplicate_found / self.total_checks
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total_cache_ops = self.cache_hits + self.cache_misses
        if total_cache_ops == 0:
            return 0.0
        return self.cache_hits / total_cache_ops
    
    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.total_checks == 0:
            return 0.0
        return self.error_count / self.total_checks
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_checks": self.total_checks,
            "duplicate_found": self.duplicate_found,
            "duplicate_rate": self.duplicate_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "avg_response_time": self.avg_response_time,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "last_reset": self.last_reset.isoformat() if self.last_reset else None
        }


class MonitoringService:
    """监控服务"""
    
    def __init__(self, max_alerts: int = 1000, max_metrics: int = 10000):
        self.config = get_config().monitoring
        self.logger = logging.getLogger(__name__)
        self.stats = PerformanceStats()
        self.alerts: List[Alert] = []
        self.metrics: List[Metric] = []
        self.max_alerts = max_alerts
        self.max_metrics = max_metrics
        self.response_times: List[float] = []
        self.start_time = datetime.now()
        
        # 性能阈值配置
        self.thresholds = {
            "max_response_time": 1.0,  # 1秒
            "max_error_rate": 0.05,   # 5%
            "min_cache_hit_rate": 0.8, # 80%
            "max_duplicate_rate": 0.3  # 30%
        }
    
    def record_performance(self, response_time: float, duplicate_type: Optional[DuplicateType] = None, error: Optional[str] = None):
        """记录性能指标"""
        metric = Metric(
            name="deduplication_performance",
            type=MetricType.TIMER,
            value=response_time,
            timestamp=datetime.now(),
            labels={
                "duplicate_type": duplicate_type.value if duplicate_type else "none",
                "has_error": "true" if error else "false"
            }
        )
        
        self.metrics.append(metric)
        
        # 更新性能统计
        self.stats.total_checks += 1
        
        if duplicate_type:
            self.stats.duplicate_found += 1
        
        if error:
            self.stats.error_count += 1
            self.logger.error(f"去重检查错误: {error}")
        
        # 记录响应时间
        self.response_times.append(response_time)
        if len(self.response_times) > 1000:  # 保持最近1000次记录
            self.response_times.pop(0)
        
        # 更新平均响应时间
        self.stats.avg_response_time = sum(self.response_times) / len(self.response_times)
        
        # 检查性能告警
        self._check_performance_thresholds()
    
    def record_check(self, is_duplicate: bool, response_time: float, 
                    duplicate_type: Optional[DuplicateType] = None, 
                    error: Optional[Exception] = None):
        """记录去重检查"""
        self.stats.total_checks += 1
        
        if error:
            self.stats.error_count += 1
            self._create_alert(
                AlertLevel.ERROR,
                f"去重检查失败: {str(error)}",
                "deduplication_engine",
                {"error_type": type(error).__name__, "error_message": str(error)}
            )
        
        if is_duplicate:
            self.stats.duplicate_found += 1
        
        # 记录响应时间
        self.response_times.append(response_time)
        if len(self.response_times) > 1000:  # 保持最近1000次记录
            self.response_times.pop(0)
        
        # 更新平均响应时间
        self.stats.avg_response_time = sum(self.response_times) / len(self.response_times)
        
        # 检查性能阈值
        self._check_performance_thresholds()
        
        # 记录指标
        self._record_metric("dedup_checks_total", MetricType.COUNTER, self.stats.total_checks)
        self._record_metric("dedup_response_time", MetricType.TIMER, response_time)
        
        if duplicate_type:
            self._record_metric(
                "dedup_duplicates_by_type", 
                MetricType.COUNTER, 
                1, 
                {"type": duplicate_type.value}
            )
    
    def record_cache_operation(self, hit: bool):
        """记录缓存操作"""
        if hit:
            self.stats.cache_hits += 1
            self._record_metric("cache_hits_total", MetricType.COUNTER, self.stats.cache_hits)
        else:
            self.stats.cache_misses += 1
            self._record_metric("cache_misses_total", MetricType.COUNTER, self.stats.cache_misses)
    
    def _check_performance_alerts(self, response_time: float, error: Optional[str]):
        """检查性能告警"""
        # 响应时间告警
        if response_time > self.config.max_response_time_ms:
            alert = Alert(
                id=f"perf_{int(time.time())}",
                level=AlertLevel.WARNING,
                message=f"去重检查响应时间过长: {response_time:.2f}ms (阈值: {self.config.max_response_time_ms}ms)",
                timestamp=datetime.now(),
                metadata={"response_time": response_time, "threshold": self.config.max_response_time_ms}
            )
            self._add_alert(alert)
        
        # 错误率告警
        if self.performance_stats.total_requests > 0:
            error_rate = self.performance_stats.errors / self.performance_stats.total_requests
            if error_rate > self.config.max_error_rate:
                alert = Alert(
                    id=f"error_{int(time.time())}",
                    level=AlertLevel.CRITICAL,
                    message=f"去重检查错误率过高: {error_rate:.2%} (阈值: {self.config.max_error_rate:.2%})",
                    timestamp=datetime.now(),
                    metadata={"error_rate": error_rate, "threshold": self.config.max_error_rate}
                )
                self._add_alert(alert)
    
    def _create_alert(self, level: AlertLevel, message: str, component: str, 
                     details: Optional[Dict[str, Any]] = None):
        """创建告警"""
        alert = Alert(
            level=level,
            message=message,
            component=component,
            timestamp=datetime.now(),
            details=details
        )
        
        self.alerts.append(alert)
        
        # 限制告警数量
        if len(self.alerts) > self.max_alerts:
            self.alerts.pop(0)
        
        # 记录日志
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }[level]
        
        self.logger.log(log_level, f"[{component}] {message}", extra=details or {})
    
    def _record_metric(self, name: str, metric_type: MetricType, value: float, 
                      labels: Optional[Dict[str, str]] = None):
        """记录指标"""
        metric = Metric(
            name=name,
            type=metric_type,
            value=value,
            timestamp=datetime.now(),
            labels=labels
        )
        
        self.metrics.append(metric)
        
        # 限制指标数量
        if len(self.metrics) > self.max_metrics:
            self.metrics.pop(0)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = datetime.now() - self.start_time
        
        return {
            "performance": self.stats.to_dict(),
            "uptime_seconds": uptime.total_seconds(),
            "active_alerts": len([a for a in self.alerts if not a.resolved]),
            "total_alerts": len(self.alerts),
            "thresholds": self.thresholds
        }
    
    def get_alerts(self, level: Optional[AlertLevel] = None, 
                  resolved: Optional[bool] = None, 
                  limit: int = 100) -> List[Dict[str, Any]]:
        """获取告警列表"""
        alerts = self.alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # 按时间倒序排列
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [alert.to_dict() for alert in alerts[:limit]]
    
    def get_metrics(self, name_pattern: Optional[str] = None, 
                   since: Optional[datetime] = None, 
                   limit: int = 1000) -> List[Dict[str, Any]]:
        """获取指标列表"""
        metrics = self.metrics
        
        if name_pattern:
            metrics = [m for m in metrics if name_pattern in m.name]
        
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        
        # 按时间倒序排列
        metrics.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [metric.to_dict() for metric in metrics[:limit]]
    
    def resolve_alert(self, alert_index: int) -> bool:
        """解决告警"""
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].resolved = True
            return True
        return False
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = PerformanceStats()
        self.response_times.clear()
        self.logger.info("性能统计已重置")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        now = datetime.now()
        uptime = now - self.start_time
        
        # 检查关键指标
        critical_alerts = [a for a in self.alerts if a.level == AlertLevel.CRITICAL and not a.resolved]
        error_alerts = [a for a in self.alerts if a.level == AlertLevel.ERROR and not a.resolved]
        
        is_healthy = (
            len(critical_alerts) == 0 and
            len(error_alerts) < 5 and
            self.stats.error_rate < 0.1 and
            (self.stats.avg_response_time < 2.0 if self.response_times else True)
        )
        
        return {
            "healthy": is_healthy,
            "uptime_seconds": uptime.total_seconds(),
            "critical_alerts": len(critical_alerts),
            "error_alerts": len(error_alerts),
            "error_rate": self.stats.error_rate,
            "avg_response_time": self.stats.avg_response_time,
            "last_check": now.isoformat()
        }


class ErrorRecoveryService:
    """错误恢复服务"""
    
    def __init__(self, monitoring_service: MonitoringService):
        self.logger = logging.getLogger(__name__)
        self.monitoring = monitoring_service
        self.recovery_strategies = {
            "cache_failure": self._recover_cache_failure,
            "db_connection_failure": self._recover_db_failure,
            "high_error_rate": self._recover_high_error_rate,
            "performance_degradation": self._recover_performance_degradation
        }
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """处理错误并尝试恢复"""
        error_type = type(error).__name__
        self.logger.error(f"处理错误: {error_type} - {str(error)}", extra=context)
        
        # 根据错误类型选择恢复策略
        recovery_strategy = None
        
        if "redis" in str(error).lower() or "cache" in str(error).lower():
            recovery_strategy = "cache_failure"
        elif "mongo" in str(error).lower() or "database" in str(error).lower():
            recovery_strategy = "db_connection_failure"
        elif self.monitoring.stats.error_rate > 0.1:
            recovery_strategy = "high_error_rate"
        elif self.monitoring.stats.avg_response_time > 2.0:
            recovery_strategy = "performance_degradation"
        
        if recovery_strategy and recovery_strategy in self.recovery_strategies:
            try:
                success = await self.recovery_strategies[recovery_strategy](error, context)
                if success:
                    self.monitoring._create_alert(
                        AlertLevel.INFO,
                        f"错误恢复成功: {recovery_strategy}",
                        "error_recovery",
                        {"error_type": error_type, "strategy": recovery_strategy}
                    )
                    return True
            except Exception as recovery_error:
                self.logger.error(f"错误恢复失败: {str(recovery_error)}")
        
        return False
    
    async def _recover_cache_failure(self, error: Exception, context: Dict[str, Any]) -> bool:
        """恢复缓存故障"""
        self.logger.info("尝试恢复缓存故障")
        
        # 等待一段时间后重试
        await asyncio.sleep(1)
        
        # 这里可以添加缓存重连逻辑
        # 例如：重新初始化Redis连接
        
        return True  # 简化实现，实际应该检查缓存是否恢复
    
    async def _recover_db_failure(self, error: Exception, context: Dict[str, Any]) -> bool:
        """恢复数据库故障"""
        self.logger.info("尝试恢复数据库故障")
        
        # 等待一段时间后重试
        await asyncio.sleep(2)
        
        # 这里可以添加数据库重连逻辑
        
        return True  # 简化实现
    
    async def _recover_high_error_rate(self, error: Exception, context: Dict[str, Any]) -> bool:
        """恢复高错误率"""
        self.logger.info("检测到高错误率，启动恢复策略")
        
        # 暂停一段时间，让系统恢复
        await asyncio.sleep(5)
        
        # 重置错误计数
        self.monitoring.reset_stats()
        
        return True
    
    async def _recover_performance_degradation(self, error: Exception, context: Dict[str, Any]) -> bool:
        """恢复性能下降"""
        self.logger.info("检测到性能下降，启动优化策略")
        
        # 清理缓存以释放内存
        # 这里可以添加具体的优化逻辑
        
        return True


# 全局监控实例
_monitoring_service = None
_error_recovery_service = None


def get_monitoring_service() -> MonitoringService:
    """获取监控服务实例"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service


def get_error_recovery_service() -> ErrorRecoveryService:
    """获取错误恢复服务实例"""
    global _error_recovery_service
    if _error_recovery_service is None:
        _error_recovery_service = ErrorRecoveryService(get_monitoring_service())
    return _error_recovery_service