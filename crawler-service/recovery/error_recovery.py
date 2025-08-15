#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误恢复机制
实现智能重试、错误分类、降级触发逻辑和故障恢复策略
提供完整的错误处理和系统恢复能力
"""

import asyncio
import json
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Union, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import uuid
import traceback
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ErrorCategory(Enum):
    """错误分类"""
    NETWORK_ERROR = "network_error"           # 网络错误
    TIMEOUT_ERROR = "timeout_error"           # 超时错误
    PARSING_ERROR = "parsing_error"           # 解析错误
    AUTHENTICATION_ERROR = "auth_error"       # 认证错误
    RATE_LIMIT_ERROR = "rate_limit_error"     # 限流错误
    CONTENT_ERROR = "content_error"           # 内容错误
    SYSTEM_ERROR = "system_error"             # 系统错误
    BROWSER_ERROR = "browser_error"           # 浏览器错误
    DATABASE_ERROR = "database_error"         # 数据库错误
    VALIDATION_ERROR = "validation_error"     # 验证错误
    UNKNOWN_ERROR = "unknown_error"           # 未知错误

class ErrorSeverity(Enum):
    """错误严重程度"""
    CRITICAL = "critical"     # 严重错误，需要立即处理
    HIGH = "high"             # 高级错误，需要快速处理
    MEDIUM = "medium"         # 中级错误，正常处理
    LOW = "low"               # 低级错误，可延迟处理
    INFO = "info"             # 信息性错误，仅记录

class RecoveryStrategy(Enum):
    """恢复策略"""
    IMMEDIATE_RETRY = "immediate_retry"       # 立即重试
    DELAYED_RETRY = "delayed_retry"           # 延迟重试
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    LINEAR_BACKOFF = "linear_backoff"         # 线性退避
    CIRCUIT_BREAKER = "circuit_breaker"       # 熔断器
    FALLBACK = "fallback"                     # 降级处理
    SKIP = "skip"                             # 跳过任务
    ESCALATE = "escalate"                     # 升级处理

class RecoveryAction(Enum):
    """恢复动作"""
    RETRY_TASK = "retry_task"                 # 重试任务
    CHANGE_STRATEGY = "change_strategy"       # 更改策略
    USE_FALLBACK = "use_fallback"             # 使用降级
    RESTART_WORKER = "restart_worker"         # 重启Worker
    SCALE_UP = "scale_up"                     # 扩容
    SCALE_DOWN = "scale_down"                 # 缩容
    ALERT_ADMIN = "alert_admin"               # 管理员告警
    QUARANTINE = "quarantine"                 # 隔离处理

@dataclass
class ErrorPattern:
    """错误模式"""
    pattern: str                              # 错误模式（正则表达式）
    category: ErrorCategory                   # 错误分类
    severity: ErrorSeverity                   # 严重程度
    strategy: RecoveryStrategy                # 恢复策略
    max_retries: int = 3                      # 最大重试次数
    retry_delay: float = 1.0                  # 重试延迟
    backoff_factor: float = 2.0               # 退避因子
    timeout_multiplier: float = 1.5           # 超时倍数
    description: str = ""                     # 描述
    tags: List[str] = field(default_factory=list)  # 标签

@dataclass
class ErrorRecord:
    """错误记录"""
    id: str
    task_id: str
    worker_id: Optional[str]
    error_message: str
    error_type: str
    category: ErrorCategory
    severity: ErrorSeverity
    
    # 时间信息
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # 上下文信息
    url: Optional[str] = None
    platform: Optional[str] = None
    session_id: Optional[str] = None
    
    # 技术信息
    stack_trace: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    
    # 恢复信息
    recovery_attempts: int = 0
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None

@dataclass
class RecoveryConfig:
    """恢复配置"""
    # 基础设置
    max_retry_attempts: int = 5
    base_retry_delay: float = 1.0
    max_retry_delay: float = 300.0  # 5分钟
    
    # 退避策略
    exponential_base: float = 2.0
    linear_increment: float = 1.0
    jitter_enabled: bool = True
    jitter_factor: float = 0.1
    
    # 熔断器设置
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    circuit_breaker_recovery_timeout: float = 300.0
    
    # 超时设置
    default_timeout: float = 30.0
    max_timeout: float = 600.0
    timeout_escalation_factor: float = 1.5
    
    # 错误阈值
    error_rate_threshold: float = 0.5
    consecutive_error_threshold: int = 3
    
    # 降级设置
    fallback_enabled: bool = True
    fallback_timeout: float = 10.0
    
    # 监控设置
    monitoring_enabled: bool = True
    alert_threshold: int = 10
    health_check_interval: float = 30.0
    
    # 存储设置
    error_retention_days: int = 30
    max_error_records: int = 10000

@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None
    success_count: int = 0
    total_requests: int = 0

@dataclass
class RecoveryMetrics:
    """恢复指标"""
    # 错误统计
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    
    # 恢复统计
    total_recoveries: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    recovery_success_rate: float = 0.0
    
    # 性能指标
    avg_recovery_time: float = 0.0
    max_recovery_time: float = 0.0
    min_recovery_time: float = float('inf')
    
    # 策略统计
    strategy_usage: Dict[str, int] = field(default_factory=dict)
    strategy_success_rate: Dict[str, float] = field(default_factory=dict)
    
    # 时间戳
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
        
        # 错误模式库
        self.error_patterns: List[ErrorPattern] = []
        self._initialize_default_patterns()
        
        # 错误记录
        self.error_records: deque = deque(maxlen=config.max_error_records)
        self.error_history: Dict[str, List[ErrorRecord]] = defaultdict(list)
        
        # 熔断器状态
        self.circuit_breakers: Dict[str, CircuitBreakerState] = defaultdict(CircuitBreakerState)
        
        # 恢复策略缓存
        self.strategy_cache: Dict[str, RecoveryStrategy] = {}
        
        # 统计信息
        self.metrics = RecoveryMetrics()
        self.metrics_history: deque = deque(maxlen=1000)
        
        # 监控状态
        self.monitoring_task = None
        self.health_check_task = None
        
        # 锁
        self.recovery_lock = threading.RLock()
        self.metrics_lock = threading.RLock()
        
        # 回调函数
        self.recovery_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # 活跃恢复任务
        self.active_recoveries: Dict[str, asyncio.Task] = {}
    
    def _initialize_default_patterns(self):
        """初始化默认错误模式"""
        patterns = [
            # 网络错误
            ErrorPattern(
                pattern=r"(connection|network|socket|dns).*error",
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.HIGH,
                strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=5,
                retry_delay=2.0,
                description="网络连接错误"
            ),
            
            # 超时错误
            ErrorPattern(
                pattern=r"(timeout|timed out|time out)",
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                strategy=RecoveryStrategy.LINEAR_BACKOFF,
                max_retries=3,
                retry_delay=5.0,
                timeout_multiplier=2.0,
                description="请求超时错误"
            ),
            
            # 限流错误
            ErrorPattern(
                pattern=r"(rate limit|too many requests|429)",
                category=ErrorCategory.RATE_LIMIT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=10,
                retry_delay=60.0,
                backoff_factor=1.5,
                description="API限流错误"
            ),
            
            # 认证错误
            ErrorPattern(
                pattern=r"(auth|unauthorized|forbidden|401|403)",
                category=ErrorCategory.AUTHENTICATION_ERROR,
                severity=ErrorSeverity.HIGH,
                strategy=RecoveryStrategy.FALLBACK,
                max_retries=1,
                description="认证授权错误"
            ),
            
            # 解析错误
            ErrorPattern(
                pattern=r"(parse|parsing|json|xml|html).*error",
                category=ErrorCategory.PARSING_ERROR,
                severity=ErrorSeverity.MEDIUM,
                strategy=RecoveryStrategy.FALLBACK,
                max_retries=2,
                description="内容解析错误"
            ),
            
            # 浏览器错误
            ErrorPattern(
                pattern=r"(browser|chrome|playwright|selenium).*error",
                category=ErrorCategory.BROWSER_ERROR,
                severity=ErrorSeverity.HIGH,
                strategy=RecoveryStrategy.CIRCUIT_BREAKER,
                max_retries=3,
                description="浏览器操作错误"
            ),
            
            # 数据库错误
            ErrorPattern(
                pattern=r"(database|mongodb|redis|sql).*error",
                category=ErrorCategory.DATABASE_ERROR,
                severity=ErrorSeverity.CRITICAL,
                strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=5,
                retry_delay=1.0,
                description="数据库操作错误"
            ),
            
            # 系统错误
            ErrorPattern(
                pattern=r"(memory|disk|cpu|system).*error",
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.CRITICAL,
                strategy=RecoveryStrategy.ESCALATE,
                max_retries=1,
                description="系统资源错误"
            )
        ]
        
        self.error_patterns.extend(patterns)
    
    async def handle_error(
        self,
        task_id: str,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[RecoveryAction]]:
        """处理错误"""
        try:
            # 创建错误记录
            error_record = await self._create_error_record(task_id, error, context or {})
            
            # 分类错误
            await self._classify_error(error_record)
            
            # 检查熔断器
            if await self._check_circuit_breaker(error_record):
                logger.warning(f"熔断器开启，跳过任务: {task_id}")
                return False, RecoveryAction.SKIP
            
            # 选择恢复策略
            recovery_strategy = await self._select_recovery_strategy(error_record)
            error_record.recovery_strategy = recovery_strategy
            
            # 执行恢复
            recovery_result = await self._execute_recovery(error_record)
            
            # 更新统计
            await self._update_recovery_metrics(error_record, recovery_result)
            
            # 存储错误记录
            await self._store_error_record(error_record)
            
            # 触发回调
            await self._trigger_recovery_callbacks('error_handled', error_record)
            
            return recovery_result
            
        except Exception as e:
            logger.error(f"处理错误失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _create_error_record(
        self,
        task_id: str,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorRecord:
        """创建错误记录"""
        try:
            error_record = ErrorRecord(
                id=str(uuid.uuid4()),
                task_id=task_id,
                worker_id=context.get('worker_id'),
                error_message=str(error),
                error_type=type(error).__name__,
                category=ErrorCategory.UNKNOWN_ERROR,
                severity=ErrorSeverity.MEDIUM,
                url=context.get('url'),
                platform=context.get('platform'),
                session_id=context.get('session_id'),
                stack_trace=traceback.format_exc(),
                request_headers=context.get('request_headers'),
                response_status=context.get('response_status'),
                response_headers=context.get('response_headers'),
                metadata=context.get('metadata', {})
            )
            
            return error_record
            
        except Exception as e:
            logger.error(f"创建错误记录失败: {str(e)}")
            raise
    
    async def _classify_error(self, error_record: ErrorRecord):
        """分类错误"""
        try:
            error_message = error_record.error_message.lower()
            
            # 匹配错误模式
            for pattern in self.error_patterns:
                if re.search(pattern.pattern, error_message, re.IGNORECASE):
                    error_record.category = pattern.category
                    error_record.severity = pattern.severity
                    break
            
            # 根据HTTP状态码分类
            if error_record.response_status:
                status = error_record.response_status
                if status == 401 or status == 403:
                    error_record.category = ErrorCategory.AUTHENTICATION_ERROR
                    error_record.severity = ErrorSeverity.HIGH
                elif status == 429:
                    error_record.category = ErrorCategory.RATE_LIMIT_ERROR
                    error_record.severity = ErrorSeverity.MEDIUM
                elif status >= 500:
                    error_record.category = ErrorCategory.SYSTEM_ERROR
                    error_record.severity = ErrorSeverity.HIGH
                elif status >= 400:
                    error_record.category = ErrorCategory.CONTENT_ERROR
                    error_record.severity = ErrorSeverity.LOW
            
            # 根据错误类型分类
            error_type = error_record.error_type.lower()
            if 'timeout' in error_type:
                error_record.category = ErrorCategory.TIMEOUT_ERROR
            elif 'connection' in error_type or 'network' in error_type:
                error_record.category = ErrorCategory.NETWORK_ERROR
            elif 'parse' in error_type or 'json' in error_type:
                error_record.category = ErrorCategory.PARSING_ERROR
            
            logger.debug(f"错误分类: {error_record.category.value} (严重程度: {error_record.severity.value})")
            
        except Exception as e:
            logger.error(f"分类错误失败: {str(e)}")
    
    async def _check_circuit_breaker(self, error_record: ErrorRecord) -> bool:
        """检查熔断器状态"""
        try:
            # 根据URL或平台创建熔断器键
            breaker_key = error_record.url or error_record.platform or 'default'
            breaker = self.circuit_breakers[breaker_key]
            
            current_time = datetime.now(timezone.utc)
            
            # 检查熔断器是否开启
            if breaker.is_open:
                # 检查是否可以尝试恢复
                if (breaker.next_attempt_time and 
                    current_time >= breaker.next_attempt_time):
                    # 半开状态，允许一次尝试
                    breaker.is_open = False
                    logger.info(f"熔断器半开状态: {breaker_key}")
                    return False
                else:
                    # 熔断器仍然开启
                    return True
            
            # 更新失败计数
            breaker.failure_count += 1
            breaker.last_failure_time = current_time
            breaker.total_requests += 1
            
            # 检查是否需要开启熔断器
            if breaker.failure_count >= self.config.circuit_breaker_threshold:
                breaker.is_open = True
                breaker.next_attempt_time = current_time + timedelta(
                    seconds=self.config.circuit_breaker_timeout
                )
                logger.warning(f"熔断器开启: {breaker_key} (失败次数: {breaker.failure_count})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查熔断器失败: {str(e)}")
            return False
    
    async def _select_recovery_strategy(self, error_record: ErrorRecord) -> RecoveryStrategy:
        """选择恢复策略"""
        try:
            # 检查缓存
            cache_key = f"{error_record.category.value}_{error_record.severity.value}"
            if cache_key in self.strategy_cache:
                return self.strategy_cache[cache_key]
            
            # 根据错误模式选择策略
            error_message = error_record.error_message.lower()
            for pattern in self.error_patterns:
                if re.search(pattern.pattern, error_message, re.IGNORECASE):
                    strategy = pattern.strategy
                    self.strategy_cache[cache_key] = strategy
                    return strategy
            
            # 根据错误分类和严重程度选择默认策略
            if error_record.severity == ErrorSeverity.CRITICAL:
                strategy = RecoveryStrategy.ESCALATE
            elif error_record.category == ErrorCategory.NETWORK_ERROR:
                strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
            elif error_record.category == ErrorCategory.TIMEOUT_ERROR:
                strategy = RecoveryStrategy.LINEAR_BACKOFF
            elif error_record.category == ErrorCategory.RATE_LIMIT_ERROR:
                strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
            elif error_record.category == ErrorCategory.AUTHENTICATION_ERROR:
                strategy = RecoveryStrategy.FALLBACK
            elif error_record.category == ErrorCategory.PARSING_ERROR:
                strategy = RecoveryStrategy.FALLBACK
            else:
                strategy = RecoveryStrategy.DELAYED_RETRY
            
            self.strategy_cache[cache_key] = strategy
            return strategy
            
        except Exception as e:
            logger.error(f"选择恢复策略失败: {str(e)}")
            return RecoveryStrategy.DELAYED_RETRY
    
    async def _execute_recovery(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """执行恢复策略"""
        try:
            strategy = error_record.recovery_strategy
            
            if strategy == RecoveryStrategy.IMMEDIATE_RETRY:
                return await self._immediate_retry(error_record)
            
            elif strategy == RecoveryStrategy.DELAYED_RETRY:
                return await self._delayed_retry(error_record)
            
            elif strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                return await self._exponential_backoff_retry(error_record)
            
            elif strategy == RecoveryStrategy.LINEAR_BACKOFF:
                return await self._linear_backoff_retry(error_record)
            
            elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                return await self._circuit_breaker_recovery(error_record)
            
            elif strategy == RecoveryStrategy.FALLBACK:
                return await self._fallback_recovery(error_record)
            
            elif strategy == RecoveryStrategy.SKIP:
                return await self._skip_recovery(error_record)
            
            elif strategy == RecoveryStrategy.ESCALATE:
                return await self._escalate_recovery(error_record)
            
            else:
                return await self._delayed_retry(error_record)
                
        except Exception as e:
            logger.error(f"执行恢复策略失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _immediate_retry(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """立即重试"""
        try:
            # 检查重试次数
            if error_record.recovery_attempts >= self.config.max_retry_attempts:
                logger.warning(f"重试次数超限: {error_record.task_id}")
                return False, RecoveryAction.USE_FALLBACK
            
            error_record.recovery_attempts += 1
            error_record.recovery_actions.append(RecoveryAction.RETRY_TASK)
            
            logger.info(f"立即重试任务: {error_record.task_id} (第{error_record.recovery_attempts}次)")
            return True, RecoveryAction.RETRY_TASK
            
        except Exception as e:
            logger.error(f"立即重试失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _delayed_retry(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """延迟重试"""
        try:
            # 检查重试次数
            if error_record.recovery_attempts >= self.config.max_retry_attempts:
                logger.warning(f"重试次数超限: {error_record.task_id}")
                return False, RecoveryAction.USE_FALLBACK
            
            # 计算延迟时间
            delay = self.config.base_retry_delay
            if self.config.jitter_enabled:
                import random
                jitter = random.uniform(-self.config.jitter_factor, self.config.jitter_factor)
                delay *= (1 + jitter)
            
            error_record.recovery_attempts += 1
            error_record.recovery_actions.append(RecoveryAction.RETRY_TASK)
            
            logger.info(f"延迟重试任务: {error_record.task_id} (延迟: {delay:.2f}秒)")
            
            # 异步延迟重试
            asyncio.create_task(self._schedule_delayed_retry(error_record, delay))
            
            return True, RecoveryAction.RETRY_TASK
            
        except Exception as e:
            logger.error(f"延迟重试失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _exponential_backoff_retry(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """指数退避重试"""
        try:
            # 检查重试次数
            if error_record.recovery_attempts >= self.config.max_retry_attempts:
                logger.warning(f"重试次数超限: {error_record.task_id}")
                return False, RecoveryAction.USE_FALLBACK
            
            # 计算指数退避延迟
            delay = self.config.base_retry_delay * (self.config.exponential_base ** error_record.recovery_attempts)
            delay = min(delay, self.config.max_retry_delay)
            
            if self.config.jitter_enabled:
                import random
                jitter = random.uniform(-self.config.jitter_factor, self.config.jitter_factor)
                delay *= (1 + jitter)
            
            error_record.recovery_attempts += 1
            error_record.recovery_actions.append(RecoveryAction.RETRY_TASK)
            
            logger.info(f"指数退避重试: {error_record.task_id} (延迟: {delay:.2f}秒)")
            
            # 异步延迟重试
            asyncio.create_task(self._schedule_delayed_retry(error_record, delay))
            
            return True, RecoveryAction.RETRY_TASK
            
        except Exception as e:
            logger.error(f"指数退避重试失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _linear_backoff_retry(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """线性退避重试"""
        try:
            # 检查重试次数
            if error_record.recovery_attempts >= self.config.max_retry_attempts:
                logger.warning(f"重试次数超限: {error_record.task_id}")
                return False, RecoveryAction.USE_FALLBACK
            
            # 计算线性退避延迟
            delay = self.config.base_retry_delay + (self.config.linear_increment * error_record.recovery_attempts)
            delay = min(delay, self.config.max_retry_delay)
            
            if self.config.jitter_enabled:
                import random
                jitter = random.uniform(-self.config.jitter_factor, self.config.jitter_factor)
                delay *= (1 + jitter)
            
            error_record.recovery_attempts += 1
            error_record.recovery_actions.append(RecoveryAction.RETRY_TASK)
            
            logger.info(f"线性退避重试: {error_record.task_id} (延迟: {delay:.2f}秒)")
            
            # 异步延迟重试
            asyncio.create_task(self._schedule_delayed_retry(error_record, delay))
            
            return True, RecoveryAction.RETRY_TASK
            
        except Exception as e:
            logger.error(f"线性退避重试失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _circuit_breaker_recovery(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """熔断器恢复"""
        try:
            breaker_key = error_record.url or error_record.platform or 'default'
            breaker = self.circuit_breakers[breaker_key]
            
            if breaker.is_open:
                logger.info(f"熔断器开启，跳过任务: {error_record.task_id}")
                error_record.recovery_actions.append(RecoveryAction.SKIP)
                return False, RecoveryAction.SKIP
            
            # 尝试恢复
            error_record.recovery_attempts += 1
            error_record.recovery_actions.append(RecoveryAction.RETRY_TASK)
            
            logger.info(f"熔断器恢复重试: {error_record.task_id}")
            return True, RecoveryAction.RETRY_TASK
            
        except Exception as e:
            logger.error(f"熔断器恢复失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _fallback_recovery(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """降级恢复"""
        try:
            if not self.config.fallback_enabled:
                logger.warning(f"降级功能未启用: {error_record.task_id}")
                return False, RecoveryAction.SKIP
            
            error_record.recovery_actions.append(RecoveryAction.USE_FALLBACK)
            
            logger.info(f"使用降级策略: {error_record.task_id}")
            return True, RecoveryAction.USE_FALLBACK
            
        except Exception as e:
            logger.error(f"降级恢复失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _skip_recovery(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """跳过恢复"""
        try:
            error_record.recovery_actions.append(RecoveryAction.SKIP)
            
            logger.info(f"跳过任务: {error_record.task_id}")
            return False, RecoveryAction.SKIP
            
        except Exception as e:
            logger.error(f"跳过恢复失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _escalate_recovery(self, error_record: ErrorRecord) -> Tuple[bool, Optional[RecoveryAction]]:
        """升级恢复"""
        try:
            error_record.recovery_actions.append(RecoveryAction.ALERT_ADMIN)
            
            # 发送告警
            await self._send_alert(error_record)
            
            logger.critical(f"错误升级处理: {error_record.task_id}")
            return False, RecoveryAction.ALERT_ADMIN
            
        except Exception as e:
            logger.error(f"升级恢复失败: {str(e)}")
            return False, RecoveryAction.ESCALATE
    
    async def _schedule_delayed_retry(self, error_record: ErrorRecord, delay: float):
        """调度延迟重试"""
        try:
            await asyncio.sleep(delay)
            
            # 触发重试回调
            await self._trigger_recovery_callbacks('retry_scheduled', error_record)
            
        except Exception as e:
            logger.error(f"调度延迟重试失败: {str(e)}")
    
    async def _send_alert(self, error_record: ErrorRecord):
        """发送告警"""
        try:
            alert_data = {
                'task_id': error_record.task_id,
                'error_category': error_record.category.value,
                'error_severity': error_record.severity.value,
                'error_message': error_record.error_message,
                'occurred_at': error_record.occurred_at.isoformat(),
                'recovery_attempts': error_record.recovery_attempts
            }
            
            # 这里可以集成实际的告警系统（如邮件、短信、Slack等）
            logger.critical(f"系统告警: {json.dumps(alert_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"发送告警失败: {str(e)}")
    
    async def _store_error_record(self, error_record: ErrorRecord):
        """存储错误记录"""
        try:
            # 添加到内存记录
            self.error_records.append(error_record)
            self.error_history[error_record.task_id].append(error_record)
            
            # 这里可以集成实际的存储系统（如MongoDB、Elasticsearch等）
            logger.debug(f"错误记录已存储: {error_record.id}")
            
        except Exception as e:
            logger.error(f"存储错误记录失败: {str(e)}")
    
    async def _update_recovery_metrics(self, error_record: ErrorRecord, recovery_result: Tuple[bool, Optional[RecoveryAction]]):
        """更新恢复指标"""
        try:
            with self.metrics_lock:
                success, action = recovery_result
                
                # 更新基础统计
                self.metrics.total_errors += 1
                self.metrics.total_recoveries += 1
                
                if success:
                    self.metrics.successful_recoveries += 1
                else:
                    self.metrics.failed_recoveries += 1
                
                # 更新成功率
                if self.metrics.total_recoveries > 0:
                    self.metrics.recovery_success_rate = self.metrics.successful_recoveries / self.metrics.total_recoveries
                
                # 更新分类统计
                category_key = error_record.category.value
                if category_key not in self.metrics.errors_by_category:
                    self.metrics.errors_by_category[category_key] = 0
                self.metrics.errors_by_category[category_key] += 1
                
                severity_key = error_record.severity.value
                if severity_key not in self.metrics.errors_by_severity:
                    self.metrics.errors_by_severity[severity_key] = 0
                self.metrics.errors_by_severity[severity_key] += 1
                
                # 更新策略统计
                if error_record.recovery_strategy:
                    strategy_key = error_record.recovery_strategy.value
                    if strategy_key not in self.metrics.strategy_usage:
                        self.metrics.strategy_usage[strategy_key] = 0
                    self.metrics.strategy_usage[strategy_key] += 1
                    
                    # 更新策略成功率
                    if strategy_key not in self.metrics.strategy_success_rate:
                        self.metrics.strategy_success_rate[strategy_key] = 0.0
                    
                    strategy_total = self.metrics.strategy_usage[strategy_key]
                    strategy_success = strategy_total if success else strategy_total - 1
                    self.metrics.strategy_success_rate[strategy_key] = strategy_success / strategy_total
        
        except Exception as e:
            logger.error(f"更新恢复指标失败: {str(e)}")
    
    async def _trigger_recovery_callbacks(self, event: str, data: Any):
        """触发恢复回调"""
        try:
            callbacks = self.recovery_callbacks.get(event, [])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"恢复回调执行失败: {str(e)}")
        
        except Exception as e:
            logger.error(f"触发恢复回调失败: {str(e)}")
    
    def add_recovery_callback(self, event: str, callback: Callable):
        """添加恢复回调"""
        self.recovery_callbacks[event].append(callback)
    
    def add_error_pattern(self, pattern: ErrorPattern):
        """添加错误模式"""
        self.error_patterns.append(pattern)
    
    async def get_recovery_status(self) -> Dict[str, Any]:
        """获取恢复状态"""
        try:
            status = {
                'metrics': asdict(self.metrics),
                'circuit_breakers': {},
                'active_recoveries': len(self.active_recoveries),
                'error_patterns': len(self.error_patterns),
                'total_error_records': len(self.error_records)
            }
            
            # 熔断器状态
            for key, breaker in self.circuit_breakers.items():
                status['circuit_breakers'][key] = {
                    'is_open': breaker.is_open,
                    'failure_count': breaker.failure_count,
                    'success_count': breaker.success_count,
                    'total_requests': breaker.total_requests
                }
            
            return status
            
        except Exception as e:
            logger.error(f"获取恢复状态失败: {str(e)}")
            return {'error': str(e)}
    
    async def reset_circuit_breaker(self, key: str = None):
        """重置熔断器"""
        try:
            if key:
                if key in self.circuit_breakers:
                    self.circuit_breakers[key] = CircuitBreakerState()
                    logger.info(f"熔断器已重置: {key}")
            else:
                self.circuit_breakers.clear()
                logger.info("所有熔断器已重置")
        
        except Exception as e:
            logger.error(f"重置熔断器失败: {str(e)}")
    
    async def shutdown(self):
        """关闭恢复管理器"""
        try:
            # 取消活跃的恢复任务
            for task in self.active_recoveries.values():
                task.cancel()
            
            # 等待任务完成
            if self.active_recoveries:
                await asyncio.gather(*self.active_recoveries.values(), return_exceptions=True)
            
            # 取消监控任务
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("错误恢复管理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭恢复管理器失败: {str(e)}")

# 全局恢复管理器实例
_recovery_manager = None

async def get_recovery_manager(config: RecoveryConfig = None) -> ErrorRecoveryManager:
    """获取恢复管理器实例"""
    global _recovery_manager
    
    if _recovery_manager is None:
        if config is None:
            config = RecoveryConfig()
        
        _recovery_manager = ErrorRecoveryManager(config)
    
    return _recovery_manager

async def shutdown_recovery_manager():
    """关闭恢复管理器"""
    global _recovery_manager
    
    if _recovery_manager:
        await _recovery_manager.shutdown()
        _recovery_manager = None