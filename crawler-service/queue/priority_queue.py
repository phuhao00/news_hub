#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis优先级队列系统
实现高优先级任务调度、任务分发机制和负载均衡
支持多种队列策略、死信队列和任务监控
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
import hashlib
from urllib.parse import urlparse

# Redis相关库
try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis库未安装，队列功能将不可用")

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0    # 紧急任务
    HIGH = 1        # 高优先级
    NORMAL = 2      # 普通优先级
    LOW = 3         # 低优先级
    BATCH = 4       # 批处理任务

class QueueStrategy(Enum):
    """队列策略"""
    PRIORITY_FIRST = "priority_first"       # 优先级优先
    FIFO = "fifo"                          # 先进先出
    LIFO = "lifo"                          # 后进先出
    ROUND_ROBIN = "round_robin"            # 轮询
    WEIGHTED_ROUND_ROBIN = "weighted_rr"   # 加权轮询
    LEAST_CONNECTIONS = "least_conn"       # 最少连接
    FAIR_SHARE = "fair_share"              # 公平共享

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"         # 待处理
    QUEUED = "queued"           # 已入队
    PROCESSING = "processing"   # 处理中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    RETRYING = "retrying"       # 重试中
    EXPIRED = "expired"         # 已过期
    CANCELLED = "cancelled"     # 已取消

@dataclass
class QueueTask:
    """队列任务"""
    id: str
    url: str
    platform: str
    priority: TaskPriority
    payload: Dict[str, Any]
    
    # 时间相关
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # 重试相关
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 1.0
    
    # 元数据
    session_id: Optional[str] = None
    worker_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理datetime序列化
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif key in ['priority', 'status'] and hasattr(value, 'value'):
                data[key] = value.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueTask':
        """从字典创建"""
        # 处理datetime反序列化
        for key in ['created_at', 'scheduled_at', 'expires_at']:
            if key in data and data[key]:
                if isinstance(data[key], str):
                    data[key] = datetime.fromisoformat(data[key])
        
        # 处理枚举
        if 'priority' in data:
            if isinstance(data['priority'], (int, str)):
                data['priority'] = TaskPriority(data['priority'])
        
        if 'status' in data:
            if isinstance(data['status'], str):
                data['status'] = TaskStatus(data['status'])
        
        return cls(**data)

@dataclass
class QueueConfig:
    """队列配置"""
    # Redis连接
    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 10
    redis_timeout: float = 5.0
    
    # 队列设置
    queue_prefix: str = "crawl_queue"
    priority_queues: Dict[TaskPriority, str] = field(default_factory=lambda: {
        TaskPriority.CRITICAL: "critical",
        TaskPriority.HIGH: "high",
        TaskPriority.NORMAL: "normal",
        TaskPriority.LOW: "low",
        TaskPriority.BATCH: "batch"
    })
    
    # 调度策略
    default_strategy: QueueStrategy = QueueStrategy.PRIORITY_FIRST
    strategy_weights: Dict[TaskPriority, float] = field(default_factory=lambda: {
        TaskPriority.CRITICAL: 1.0,
        TaskPriority.HIGH: 0.8,
        TaskPriority.NORMAL: 0.6,
        TaskPriority.LOW: 0.4,
        TaskPriority.BATCH: 0.2
    })
    
    # 超时设置
    task_timeout: float = 300.0  # 5分钟
    queue_timeout: float = 30.0
    processing_timeout: float = 600.0  # 10分钟
    
    # 重试设置
    max_retries: int = 3
    retry_delay: float = 2.0
    retry_backoff: float = 2.0
    
    # 死信队列
    dead_letter_queue: str = "dead_letter"
    dead_letter_ttl: int = 86400  # 24小时
    
    # 监控设置
    monitoring_enabled: bool = True
    metrics_interval: float = 60.0
    health_check_interval: float = 30.0
    
    # 批处理设置
    batch_size: int = 100
    batch_timeout: float = 10.0
    
    # 负载均衡
    load_balancing: bool = True
    worker_capacity: Dict[str, int] = field(default_factory=dict)
    
@dataclass
class QueueMetrics:
    """队列指标"""
    # 基础统计
    total_tasks: int = 0
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # 优先级分布
    priority_distribution: Dict[str, int] = field(default_factory=dict)
    
    # 性能指标
    avg_processing_time: float = 0.0
    avg_queue_time: float = 0.0
    throughput: float = 0.0  # 任务/秒
    
    # 错误统计
    error_rate: float = 0.0
    retry_rate: float = 0.0
    
    # 队列健康
    queue_depth: Dict[str, int] = field(default_factory=dict)
    worker_utilization: Dict[str, float] = field(default_factory=dict)
    
    # 时间戳
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class PriorityQueue:
    """Redis优先级队列"""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        
        # Redis连接
        self.redis_pool = None
        self.async_redis = None
        
        # 队列状态
        self.active_workers: Set[str] = set()
        self.worker_tasks: Dict[str, Set[str]] = defaultdict(set)
        self.task_assignments: Dict[str, str] = {}  # task_id -> worker_id
        
        # 统计信息
        self.metrics = QueueMetrics()
        self.metrics_history: deque = deque(maxlen=1000)
        
        # 调度状态
        self.round_robin_index: Dict[TaskPriority, int] = defaultdict(int)
        self.worker_connections: Dict[str, int] = defaultdict(int)
        
        # 监控
        self.monitoring_task = None
        self.health_check_task = None
        
        # 锁
        self.assignment_lock = threading.RLock()
        self.metrics_lock = threading.RLock()
        
        # 回调函数
        self.task_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        if not REDIS_AVAILABLE:
            logger.error("Redis不可用，队列功能将无法正常工作")
    
    async def initialize(self) -> bool:
        """初始化队列"""
        try:
            if not REDIS_AVAILABLE:
                logger.error("Redis库未安装")
                return False
            
            # 创建Redis连接池
            self.redis_pool = aioredis.ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.redis_pool_size,
                socket_timeout=self.config.redis_timeout,
                socket_connect_timeout=self.config.redis_timeout
            )
            
            self.async_redis = aioredis.Redis(connection_pool=self.redis_pool)
            
            # 测试连接
            await self.async_redis.ping()
            
            # 初始化队列
            await self._initialize_queues()
            
            # 启动监控
            if self.config.monitoring_enabled:
                await self._start_monitoring()
            
            logger.info("优先级队列初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化优先级队列失败: {str(e)}")
            return False
    
    async def _initialize_queues(self):
        """初始化队列结构"""
        try:
            # 创建优先级队列
            for priority, queue_name in self.config.priority_queues.items():
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                await self.async_redis.exists(queue_key)  # 确保队列存在
            
            # 创建死信队列
            dead_letter_key = f"{self.config.queue_prefix}:{self.config.dead_letter_queue}"
            await self.async_redis.exists(dead_letter_key)
            
            # 创建任务状态哈希
            task_status_key = f"{self.config.queue_prefix}:task_status"
            await self.async_redis.exists(task_status_key)
            
            # 创建Worker注册表
            worker_registry_key = f"{self.config.queue_prefix}:workers"
            await self.async_redis.exists(worker_registry_key)
            
            logger.info("队列结构初始化完成")
            
        except Exception as e:
            logger.error(f"初始化队列结构失败: {str(e)}")
            raise
    
    async def enqueue(
        self,
        task: QueueTask,
        delay: float = 0.0
    ) -> bool:
        """入队任务"""
        try:
            # 设置任务状态
            task.status = TaskStatus.QUEUED
            if delay > 0:
                task.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            
            # 选择队列
            queue_name = self.config.priority_queues.get(task.priority, "normal")
            queue_key = f"{self.config.queue_prefix}:{queue_name}"
            
            # 序列化任务
            task_data = json.dumps(task.to_dict(), ensure_ascii=False)
            
            # 计算优先级分数（用于有序集合）
            priority_score = self._calculate_priority_score(task)
            
            # 使用Redis事务确保原子性
            async with self.async_redis.pipeline(transaction=True) as pipe:
                # 添加到优先级队列（有序集合）
                await pipe.zadd(queue_key, {task_data: priority_score})
                
                # 更新任务状态
                task_status_key = f"{self.config.queue_prefix}:task_status"
                await pipe.hset(task_status_key, task.id, json.dumps({
                    'status': task.status.value,
                    'queue': queue_name,
                    'created_at': task.created_at.isoformat(),
                    'priority': task.priority.value
                }))
                
                # 设置过期时间
                if task.expires_at:
                    expire_seconds = int((task.expires_at - datetime.now(timezone.utc)).total_seconds())
                    if expire_seconds > 0:
                        await pipe.expire(f"{self.config.queue_prefix}:task:{task.id}", expire_seconds)
                
                # 执行事务
                await pipe.execute()
            
            # 更新统计
            await self._update_enqueue_metrics(task)
            
            # 触发回调
            await self._trigger_callbacks('enqueue', task)
            
            logger.debug(f"任务入队成功: {task.id} (优先级: {task.priority.value})")
            return True
            
        except Exception as e:
            logger.error(f"任务入队失败: {str(e)}")
            return False
    
    async def dequeue(
        self,
        worker_id: str,
        strategy: QueueStrategy = None,
        timeout: float = None
    ) -> Optional[QueueTask]:
        """出队任务"""
        try:
            if strategy is None:
                strategy = self.config.default_strategy
            
            if timeout is None:
                timeout = self.config.queue_timeout
            
            # 注册Worker
            await self._register_worker(worker_id)
            
            # 根据策略选择任务
            task = await self._dequeue_by_strategy(worker_id, strategy, timeout)
            
            if task:
                # 分配任务给Worker
                await self._assign_task_to_worker(task.id, worker_id)
                
                # 更新任务状态
                task.status = TaskStatus.PROCESSING
                task.worker_id = worker_id
                
                # 更新统计
                await self._update_dequeue_metrics(task)
                
                # 触发回调
                await self._trigger_callbacks('dequeue', task)
                
                logger.debug(f"任务出队成功: {task.id} -> {worker_id}")
            
            return task
            
        except Exception as e:
            logger.error(f"任务出队失败: {str(e)}")
            return None
    
    async def _dequeue_by_strategy(
        self,
        worker_id: str,
        strategy: QueueStrategy,
        timeout: float
    ) -> Optional[QueueTask]:
        """根据策略出队任务"""
        try:
            if strategy == QueueStrategy.PRIORITY_FIRST:
                return await self._dequeue_priority_first(worker_id, timeout)
            
            elif strategy == QueueStrategy.FIFO:
                return await self._dequeue_fifo(worker_id, timeout)
            
            elif strategy == QueueStrategy.LIFO:
                return await self._dequeue_lifo(worker_id, timeout)
            
            elif strategy == QueueStrategy.ROUND_ROBIN:
                return await self._dequeue_round_robin(worker_id, timeout)
            
            elif strategy == QueueStrategy.WEIGHTED_ROUND_ROBIN:
                return await self._dequeue_weighted_round_robin(worker_id, timeout)
            
            elif strategy == QueueStrategy.LEAST_CONNECTIONS:
                return await self._dequeue_least_connections(worker_id, timeout)
            
            elif strategy == QueueStrategy.FAIR_SHARE:
                return await self._dequeue_fair_share(worker_id, timeout)
            
            else:
                return await self._dequeue_priority_first(worker_id, timeout)
                
        except Exception as e:
            logger.error(f"策略出队失败: {str(e)}")
            return None
    
    async def _dequeue_priority_first(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """优先级优先出队"""
        try:
            # 按优先级顺序检查队列
            for priority in TaskPriority:
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                # 从有序集合中获取最高优先级任务
                result = await self.async_redis.zpopmin(queue_key, count=1)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    task = QueueTask.from_dict(task_dict)
                    return task
            
            return None
            
        except Exception as e:
            logger.error(f"优先级优先出队失败: {str(e)}")
            return None
    
    async def _dequeue_fifo(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """先进先出出队"""
        try:
            # 检查所有队列，选择最早的任务
            earliest_task = None
            earliest_time = None
            selected_queue = None
            
            for priority in TaskPriority:
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                # 获取队列中最早的任务
                result = await self.async_redis.zrange(queue_key, 0, 0, withscores=True)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    task_time = datetime.fromisoformat(task_dict['created_at'])
                    
                    if earliest_time is None or task_time < earliest_time:
                        earliest_time = task_time
                        earliest_task = task_dict
                        selected_queue = queue_key
            
            if earliest_task and selected_queue:
                # 从队列中移除任务
                task_data = json.dumps(earliest_task, ensure_ascii=False)
                await self.async_redis.zrem(selected_queue, task_data)
                return QueueTask.from_dict(earliest_task)
            
            return None
            
        except Exception as e:
            logger.error(f"FIFO出队失败: {str(e)}")
            return None
    
    async def _dequeue_lifo(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """后进先出出队"""
        try:
            # 检查所有队列，选择最新的任务
            latest_task = None
            latest_time = None
            selected_queue = None
            
            for priority in TaskPriority:
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                # 获取队列中最新的任务
                result = await self.async_redis.zrevrange(queue_key, 0, 0, withscores=True)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    task_time = datetime.fromisoformat(task_dict['created_at'])
                    
                    if latest_time is None or task_time > latest_time:
                        latest_time = task_time
                        latest_task = task_dict
                        selected_queue = queue_key
            
            if latest_task and selected_queue:
                # 从队列中移除任务
                task_data = json.dumps(latest_task, ensure_ascii=False)
                await self.async_redis.zrem(selected_queue, task_data)
                return QueueTask.from_dict(latest_task)
            
            return None
            
        except Exception as e:
            logger.error(f"LIFO出队失败: {str(e)}")
            return None
    
    async def _dequeue_round_robin(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """轮询出队"""
        try:
            priorities = list(TaskPriority)
            start_index = self.round_robin_index[TaskPriority.NORMAL] % len(priorities)
            
            # 轮询检查队列
            for i in range(len(priorities)):
                priority_index = (start_index + i) % len(priorities)
                priority = priorities[priority_index]
                
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                result = await self.async_redis.zpopmin(queue_key, count=1)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    task = QueueTask.from_dict(task_dict)
                    
                    # 更新轮询索引
                    self.round_robin_index[TaskPriority.NORMAL] = priority_index + 1
                    
                    return task
            
            return None
            
        except Exception as e:
            logger.error(f"轮询出队失败: {str(e)}")
            return None
    
    async def _dequeue_weighted_round_robin(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """加权轮询出队"""
        try:
            # 根据权重选择优先级
            total_weight = sum(self.config.strategy_weights.values())
            import random
            rand_weight = random.uniform(0, total_weight)
            
            current_weight = 0
            selected_priority = TaskPriority.NORMAL
            
            for priority, weight in self.config.strategy_weights.items():
                current_weight += weight
                if rand_weight <= current_weight:
                    selected_priority = priority
                    break
            
            # 从选中的队列获取任务
            queue_name = self.config.priority_queues.get(selected_priority, "normal")
            queue_key = f"{self.config.queue_prefix}:{queue_name}"
            
            result = await self.async_redis.zpopmin(queue_key, count=1)
            
            if result:
                task_data, score = result[0]
                task_dict = json.loads(task_data)
                return QueueTask.from_dict(task_dict)
            
            # 如果选中队列为空，尝试其他队列
            return await self._dequeue_priority_first(worker_id, timeout)
            
        except Exception as e:
            logger.error(f"加权轮询出队失败: {str(e)}")
            return None
    
    async def _dequeue_least_connections(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """最少连接出队"""
        try:
            # 检查Worker连接数
            worker_connections = self.worker_connections.get(worker_id, 0)
            
            # 如果当前Worker连接数过多，降低优先级
            if worker_connections > 5:
                # 优先从低优先级队列获取任务
                priorities = [TaskPriority.BATCH, TaskPriority.LOW, TaskPriority.NORMAL, TaskPriority.HIGH, TaskPriority.CRITICAL]
            else:
                # 正常优先级顺序
                priorities = [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW, TaskPriority.BATCH]
            
            for priority in priorities:
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                result = await self.async_redis.zpopmin(queue_key, count=1)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    return QueueTask.from_dict(task_dict)
            
            return None
            
        except Exception as e:
            logger.error(f"最少连接出队失败: {str(e)}")
            return None
    
    async def _dequeue_fair_share(self, worker_id: str, timeout: float) -> Optional[QueueTask]:
        """公平共享出队"""
        try:
            # 计算Worker的公平份额
            total_workers = len(self.active_workers)
            if total_workers == 0:
                return await self._dequeue_priority_first(worker_id, timeout)
            
            worker_share = 1.0 / total_workers
            current_tasks = len(self.worker_tasks.get(worker_id, set()))
            
            # 如果当前Worker任务数超过公平份额，降低优先级
            if current_tasks > worker_share * 10:  # 假设总任务数为10
                priorities = [TaskPriority.LOW, TaskPriority.BATCH]
            else:
                priorities = [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.NORMAL]
            
            for priority in priorities:
                queue_name = self.config.priority_queues.get(priority, "normal")
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                
                result = await self.async_redis.zpopmin(queue_key, count=1)
                
                if result:
                    task_data, score = result[0]
                    task_dict = json.loads(task_data)
                    return QueueTask.from_dict(task_dict)
            
            return None
            
        except Exception as e:
            logger.error(f"公平共享出队失败: {str(e)}")
            return None
    
    def _calculate_priority_score(self, task: QueueTask) -> float:
        """计算优先级分数"""
        try:
            # 基础优先级分数
            base_score = task.priority.value * 1000
            
            # 时间因子（越早创建分数越低，优先级越高）
            time_factor = task.created_at.timestamp()
            
            # 重试因子（重试次数越多分数越低）
            retry_factor = task.retry_count * 10
            
            # 最终分数（分数越低优先级越高）
            final_score = base_score + time_factor + retry_factor
            
            return final_score
            
        except Exception as e:
            logger.error(f"计算优先级分数失败: {str(e)}")
            return float('inf')
    
    async def _register_worker(self, worker_id: str):
        """注册Worker"""
        try:
            self.active_workers.add(worker_id)
            
            # 在Redis中注册Worker
            worker_registry_key = f"{self.config.queue_prefix}:workers"
            worker_info = {
                'id': worker_id,
                'registered_at': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'status': 'active'
            }
            
            await self.async_redis.hset(
                worker_registry_key,
                worker_id,
                json.dumps(worker_info, ensure_ascii=False)
            )
            
            # 设置Worker心跳过期时间
            await self.async_redis.expire(f"{self.config.queue_prefix}:worker:{worker_id}:heartbeat", 60)
            
        except Exception as e:
            logger.error(f"注册Worker失败: {str(e)}")
    
    async def _assign_task_to_worker(self, task_id: str, worker_id: str):
        """分配任务给Worker"""
        try:
            with self.assignment_lock:
                self.task_assignments[task_id] = worker_id
                self.worker_tasks[worker_id].add(task_id)
                self.worker_connections[worker_id] += 1
            
            # 在Redis中记录分配
            assignment_key = f"{self.config.queue_prefix}:assignments"
            await self.async_redis.hset(assignment_key, task_id, json.dumps({
                'worker_id': worker_id,
                'assigned_at': datetime.now(timezone.utc).isoformat()
            }))
            
        except Exception as e:
            logger.error(f"分配任务失败: {str(e)}")
    
    async def complete_task(
        self,
        task_id: str,
        result: Dict[str, Any] = None,
        worker_id: str = None
    ) -> bool:
        """完成任务"""
        try:
            # 更新任务状态
            task_status_key = f"{self.config.queue_prefix}:task_status"
            status_data = {
                'status': TaskStatus.COMPLETED.value,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'result': result or {}
            }
            
            if worker_id:
                status_data['worker_id'] = worker_id
            
            await self.async_redis.hset(
                task_status_key,
                task_id,
                json.dumps(status_data, ensure_ascii=False)
            )
            
            # 清理分配记录
            await self._cleanup_task_assignment(task_id, worker_id)
            
            # 更新统计
            await self._update_completion_metrics(task_id, True)
            
            # 触发回调
            await self._trigger_callbacks('complete', {'task_id': task_id, 'result': result})
            
            logger.debug(f"任务完成: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"完成任务失败: {str(e)}")
            return False
    
    async def fail_task(
        self,
        task_id: str,
        error: str,
        worker_id: str = None,
        retry: bool = True
    ) -> bool:
        """任务失败"""
        try:
            # 获取任务信息
            task_status_key = f"{self.config.queue_prefix}:task_status"
            task_data = await self.async_redis.hget(task_status_key, task_id)
            
            if not task_data:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            task_info = json.loads(task_data)
            retry_count = task_info.get('retry_count', 0)
            
            # 判断是否需要重试
            if retry and retry_count < self.config.max_retries:
                # 重试任务
                await self._retry_task(task_id, error, retry_count + 1)
            else:
                # 任务彻底失败，移到死信队列
                await self._move_to_dead_letter_queue(task_id, error)
                
                # 更新任务状态
                status_data = {
                    'status': TaskStatus.FAILED.value,
                    'failed_at': datetime.now(timezone.utc).isoformat(),
                    'error': error,
                    'retry_count': retry_count
                }
                
                if worker_id:
                    status_data['worker_id'] = worker_id
                
                await self.async_redis.hset(
                    task_status_key,
                    task_id,
                    json.dumps(status_data, ensure_ascii=False)
                )
            
            # 清理分配记录
            await self._cleanup_task_assignment(task_id, worker_id)
            
            # 更新统计
            await self._update_completion_metrics(task_id, False)
            
            # 触发回调
            await self._trigger_callbacks('fail', {'task_id': task_id, 'error': error})
            
            logger.debug(f"任务失败: {task_id} - {error}")
            return True
            
        except Exception as e:
            logger.error(f"处理任务失败失败: {str(e)}")
            return False
    
    async def _retry_task(self, task_id: str, error: str, retry_count: int):
        """重试任务"""
        try:
            # 计算重试延迟
            delay = self.config.retry_delay * (self.config.retry_backoff ** (retry_count - 1))
            
            # 更新任务状态
            task_status_key = f"{self.config.queue_prefix}:task_status"
            task_data = await self.async_redis.hget(task_status_key, task_id)
            
            if task_data:
                task_info = json.loads(task_data)
                task_info.update({
                    'status': TaskStatus.RETRYING.value,
                    'retry_count': retry_count,
                    'last_error': error,
                    'retry_at': (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
                })
                
                await self.async_redis.hset(
                    task_status_key,
                    task_id,
                    json.dumps(task_info, ensure_ascii=False)
                )
                
                # 重新入队（延迟执行）
                # 这里可以使用Redis的延迟队列或定时任务
                await asyncio.sleep(delay)  # 简化处理
                
                # 重新构造任务并入队
                task = QueueTask.from_dict(task_info)
                task.retry_count = retry_count
                task.status = TaskStatus.PENDING
                
                await self.enqueue(task)
                
                logger.info(f"任务重试: {task_id} (第{retry_count}次)")
            
        except Exception as e:
            logger.error(f"重试任务失败: {str(e)}")
    
    async def _move_to_dead_letter_queue(self, task_id: str, error: str):
        """移动到死信队列"""
        try:
            dead_letter_key = f"{self.config.queue_prefix}:{self.config.dead_letter_queue}"
            
            # 获取任务数据
            task_status_key = f"{self.config.queue_prefix}:task_status"
            task_data = await self.async_redis.hget(task_status_key, task_id)
            
            if task_data:
                task_info = json.loads(task_data)
                task_info.update({
                    'moved_to_dlq_at': datetime.now(timezone.utc).isoformat(),
                    'final_error': error
                })
                
                # 添加到死信队列
                await self.async_redis.lpush(
                    dead_letter_key,
                    json.dumps(task_info, ensure_ascii=False)
                )
                
                # 设置死信队列TTL
                await self.async_redis.expire(dead_letter_key, self.config.dead_letter_ttl)
                
                logger.info(f"任务移至死信队列: {task_id}")
            
        except Exception as e:
            logger.error(f"移动到死信队列失败: {str(e)}")
    
    async def _cleanup_task_assignment(self, task_id: str, worker_id: str = None):
        """清理任务分配"""
        try:
            with self.assignment_lock:
                # 从内存中清理
                if task_id in self.task_assignments:
                    assigned_worker = self.task_assignments.pop(task_id)
                    if assigned_worker in self.worker_tasks:
                        self.worker_tasks[assigned_worker].discard(task_id)
                    if assigned_worker in self.worker_connections:
                        self.worker_connections[assigned_worker] = max(0, self.worker_connections[assigned_worker] - 1)
                
                # 从Redis中清理
                assignment_key = f"{self.config.queue_prefix}:assignments"
                await self.async_redis.hdel(assignment_key, task_id)
            
        except Exception as e:
            logger.error(f"清理任务分配失败: {str(e)}")
    
    async def _update_enqueue_metrics(self, task: QueueTask):
        """更新入队指标"""
        try:
            with self.metrics_lock:
                self.metrics.total_tasks += 1
                self.metrics.pending_tasks += 1
                
                priority_key = task.priority.value
                if priority_key not in self.metrics.priority_distribution:
                    self.metrics.priority_distribution[priority_key] = 0
                self.metrics.priority_distribution[priority_key] += 1
                
                queue_name = self.config.priority_queues.get(task.priority, "normal")
                if queue_name not in self.metrics.queue_depth:
                    self.metrics.queue_depth[queue_name] = 0
                self.metrics.queue_depth[queue_name] += 1
        
        except Exception as e:
            logger.error(f"更新入队指标失败: {str(e)}")
    
    async def _update_dequeue_metrics(self, task: QueueTask):
        """更新出队指标"""
        try:
            with self.metrics_lock:
                self.metrics.pending_tasks = max(0, self.metrics.pending_tasks - 1)
                self.metrics.processing_tasks += 1
                
                queue_name = self.config.priority_queues.get(task.priority, "normal")
                if queue_name in self.metrics.queue_depth:
                    self.metrics.queue_depth[queue_name] = max(0, self.metrics.queue_depth[queue_name] - 1)
        
        except Exception as e:
            logger.error(f"更新出队指标失败: {str(e)}")
    
    async def _update_completion_metrics(self, task_id: str, success: bool):
        """更新完成指标"""
        try:
            with self.metrics_lock:
                self.metrics.processing_tasks = max(0, self.metrics.processing_tasks - 1)
                
                if success:
                    self.metrics.completed_tasks += 1
                else:
                    self.metrics.failed_tasks += 1
                
                # 计算错误率
                total_completed = self.metrics.completed_tasks + self.metrics.failed_tasks
                if total_completed > 0:
                    self.metrics.error_rate = self.metrics.failed_tasks / total_completed
        
        except Exception as e:
            logger.error(f"更新完成指标失败: {str(e)}")
    
    async def _trigger_callbacks(self, event: str, data: Any):
        """触发回调函数"""
        try:
            callbacks = self.task_callbacks.get(event, [])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"回调函数执行失败: {str(e)}")
        
        except Exception as e:
            logger.error(f"触发回调失败: {str(e)}")
    
    def add_callback(self, event: str, callback: Callable):
        """添加回调函数"""
        self.task_callbacks[event].append(callback)
    
    async def _start_monitoring(self):
        """启动监控"""
        try:
            # 启动指标收集任务
            self.monitoring_task = asyncio.create_task(self._metrics_collection_loop())
            
            # 启动健康检查任务
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info("队列监控启动成功")
            
        except Exception as e:
            logger.error(f"启动监控失败: {str(e)}")
    
    async def _metrics_collection_loop(self):
        """指标收集循环"""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self._collect_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"指标收集失败: {str(e)}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查失败: {str(e)}")
    
    async def _collect_metrics(self):
        """收集指标"""
        try:
            # 更新时间戳
            self.metrics.timestamp = datetime.now(timezone.utc)
            
            # 计算吞吐量
            if len(self.metrics_history) > 0:
                prev_metrics = self.metrics_history[-1]
                time_diff = (self.metrics.timestamp - prev_metrics.timestamp).total_seconds()
                if time_diff > 0:
                    completed_diff = self.metrics.completed_tasks - prev_metrics.completed_tasks
                    self.metrics.throughput = completed_diff / time_diff
            
            # 保存历史记录
            self.metrics_history.append(self.metrics)
            
            # 持久化指标到Redis
            metrics_key = f"{self.config.queue_prefix}:metrics"
            await self.async_redis.lpush(
                metrics_key,
                json.dumps(asdict(self.metrics), default=str, ensure_ascii=False)
            )
            
            # 限制历史记录长度
            await self.async_redis.ltrim(metrics_key, 0, 999)
            
        except Exception as e:
            logger.error(f"收集指标失败: {str(e)}")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        try:
            # 检查Redis连接
            await self.async_redis.ping()
            
            # 检查队列深度
            total_depth = sum(self.metrics.queue_depth.values())
            if total_depth > 10000:  # 队列积压过多
                logger.warning(f"队列积压严重: {total_depth}")
            
            # 检查错误率
            if self.metrics.error_rate > 0.5:  # 错误率过高
                logger.warning(f"错误率过高: {self.metrics.error_rate:.2%}")
            
            # 检查Worker状态
            inactive_workers = []
            for worker_id in list(self.active_workers):
                heartbeat_key = f"{self.config.queue_prefix}:worker:{worker_id}:heartbeat"
                if not await self.async_redis.exists(heartbeat_key):
                    inactive_workers.append(worker_id)
            
            # 清理非活跃Worker
            for worker_id in inactive_workers:
                await self._cleanup_inactive_worker(worker_id)
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
    
    async def _cleanup_inactive_worker(self, worker_id: str):
        """清理非活跃Worker"""
        try:
            # 从活跃列表中移除
            self.active_workers.discard(worker_id)
            
            # 重新分配该Worker的任务
            worker_tasks = self.worker_tasks.get(worker_id, set())
            for task_id in list(worker_tasks):
                await self._reassign_task(task_id)
            
            # 清理Worker记录
            if worker_id in self.worker_tasks:
                del self.worker_tasks[worker_id]
            if worker_id in self.worker_connections:
                del self.worker_connections[worker_id]
            
            # 从Redis中清理
            worker_registry_key = f"{self.config.queue_prefix}:workers"
            await self.async_redis.hdel(worker_registry_key, worker_id)
            
            logger.info(f"清理非活跃Worker: {worker_id}")
            
        except Exception as e:
            logger.error(f"清理非活跃Worker失败: {str(e)}")
    
    async def _reassign_task(self, task_id: str):
        """重新分配任务"""
        try:
            # 获取任务信息
            task_status_key = f"{self.config.queue_prefix}:task_status"
            task_data = await self.async_redis.hget(task_status_key, task_id)
            
            if task_data:
                task_info = json.loads(task_data)
                
                # 重新构造任务
                task = QueueTask.from_dict(task_info)
                task.status = TaskStatus.PENDING
                task.worker_id = None
                
                # 重新入队
                await self.enqueue(task)
                
                logger.info(f"任务重新分配: {task_id}")
            
        except Exception as e:
            logger.error(f"重新分配任务失败: {str(e)}")
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            status = {
                'metrics': asdict(self.metrics),
                'active_workers': len(self.active_workers),
                'worker_list': list(self.active_workers),
                'queue_depths': {},
                'total_assignments': len(self.task_assignments),
                'redis_connected': True
            }
            
            # 获取实时队列深度
            for priority, queue_name in self.config.priority_queues.items():
                queue_key = f"{self.config.queue_prefix}:{queue_name}"
                depth = await self.async_redis.zcard(queue_key)
                status['queue_depths'][queue_name] = depth
            
            # 获取死信队列深度
            dead_letter_key = f"{self.config.queue_prefix}:{self.config.dead_letter_queue}"
            dlq_depth = await self.async_redis.llen(dead_letter_key)
            status['dead_letter_queue_depth'] = dlq_depth
            
            return status
            
        except Exception as e:
            logger.error(f"获取队列状态失败: {str(e)}")
            return {
                'error': str(e),
                'redis_connected': False
            }
    
    async def shutdown(self):
        """关闭队列"""
        try:
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
            
            # 关闭Redis连接
            if self.async_redis:
                await self.async_redis.close()
            
            if self.redis_pool:
                await self.redis_pool.disconnect()
            
            logger.info("优先级队列已关闭")
            
        except Exception as e:
            logger.error(f"关闭队列失败: {str(e)}")

# 全局队列实例
_queue = None

async def get_priority_queue(config: QueueConfig = None) -> PriorityQueue:
    """获取优先级队列实例"""
    global _queue
    
    if _queue is None:
        if config is None:
            config = QueueConfig()
        
        _queue = PriorityQueue(config)
        await _queue.initialize()
    
    return _queue

async def shutdown_queue():
    """关闭队列"""
    global _queue
    
    if _queue:
        await _queue.shutdown()
        _queue = None