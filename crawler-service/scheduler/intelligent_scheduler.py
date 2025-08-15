#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能Worker调度器
实现高效的任务分配、闲置检测、负载均衡和性能优化
提供智能调度算法和动态资源管理
"""

import asyncio
import json
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import statistics
import heapq

from worker.worker_manager import WorkerManager, CrawlWorker, CrawlTask
from storage.persistence_manager import get_persistence_manager

logger = logging.getLogger(__name__)

class SchedulingStrategy(Enum):
    """调度策略"""
    ROUND_ROBIN = "round_robin"              # 轮询调度
    LEAST_LOADED = "least_loaded"            # 最少负载优先
    PRIORITY_BASED = "priority_based"        # 基于优先级
    PERFORMANCE_BASED = "performance_based"  # 基于性能
    ADAPTIVE = "adaptive"                    # 自适应调度
    INTELLIGENT = "intelligent"              # 智能调度

class WorkerState(Enum):
    """Worker状态"""
    IDLE = "idle"                    # 空闲
    BUSY = "busy"                    # 忙碌
    OVERLOADED = "overloaded"        # 过载
    FAILED = "failed"                # 失败
    MAINTENANCE = "maintenance"      # 维护中

class TaskPriority(Enum):
    """任务优先级"""
    URGENT = 1      # 紧急
    HIGH = 2        # 高
    NORMAL = 3      # 普通
    LOW = 4         # 低
    BATCH = 5       # 批处理

@dataclass
class WorkerMetrics:
    """Worker性能指标"""
    worker_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    average_processing_time: float = 0.0
    current_load: int = 0
    max_load: int = 1
    last_activity: Optional[datetime] = None
    error_rate: float = 0.0
    performance_score: float = 1.0
    consecutive_failures: int = 0
    idle_time: float = 0.0
    
    def update_metrics(self, processing_time: float, success: bool):
        """更新性能指标"""
        self.total_tasks += 1
        
        if success:
            self.successful_tasks += 1
            self.consecutive_failures = 0
        else:
            self.failed_tasks += 1
            self.consecutive_failures += 1
        
        # 更新平均处理时间
        if self.total_tasks == 1:
            self.average_processing_time = processing_time
        else:
            self.average_processing_time = (
                (self.average_processing_time * (self.total_tasks - 1) + processing_time) / 
                self.total_tasks
            )
        
        # 更新错误率
        self.error_rate = self.failed_tasks / self.total_tasks if self.total_tasks > 0 else 0.0
        
        # 计算性能分数
        self._calculate_performance_score()
        
        self.last_activity = datetime.now(timezone.utc)
    
    def _calculate_performance_score(self):
        """计算性能分数"""
        try:
            # 基础分数
            base_score = 1.0
            
            # 成功率影响 (0.5权重)
            success_rate = self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 1.0
            success_factor = success_rate * 0.5
            
            # 处理速度影响 (0.3权重)
            if self.average_processing_time > 0:
                # 假设理想处理时间为10秒
                ideal_time = 10.0
                speed_factor = min(ideal_time / self.average_processing_time, 2.0) * 0.3
            else:
                speed_factor = 0.3
            
            # 负载影响 (0.2权重)
            load_factor = (1.0 - min(self.current_load / max(self.max_load, 1), 1.0)) * 0.2
            
            # 连续失败惩罚
            failure_penalty = max(0.0, 1.0 - self.consecutive_failures * 0.1)
            
            self.performance_score = (base_score + success_factor + speed_factor + load_factor) * failure_penalty
            self.performance_score = max(0.1, min(2.0, self.performance_score))  # 限制在0.1-2.0之间
            
        except Exception as e:
            logger.error(f"计算性能分数失败: {str(e)}")
            self.performance_score = 1.0

@dataclass
class SchedulingConfig:
    """调度配置"""
    strategy: SchedulingStrategy = SchedulingStrategy.INTELLIGENT
    max_workers: int = 10
    min_workers: int = 2
    idle_timeout: int = 300  # 5分钟
    overload_threshold: float = 0.8
    scale_up_threshold: float = 0.7
    scale_down_threshold: float = 0.3
    performance_window: int = 100  # 性能统计窗口
    health_check_interval: int = 30
    rebalance_interval: int = 60
    adaptive_learning: bool = True
    priority_weights: Dict[TaskPriority, float] = field(default_factory=lambda: {
        TaskPriority.URGENT: 1.0,
        TaskPriority.HIGH: 0.8,
        TaskPriority.NORMAL: 0.6,
        TaskPriority.LOW: 0.4,
        TaskPriority.BATCH: 0.2
    })

@dataclass
class TaskAssignment:
    """任务分配"""
    task: CrawlTask
    worker_id: str
    assigned_time: datetime
    priority: TaskPriority
    estimated_duration: float = 0.0
    retry_count: int = 0

class IntelligentScheduler:
    """智能Worker调度器"""
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
        self.worker_manager = None
        self.persistence_manager = None
        
        # Worker管理
        self.workers: Dict[str, CrawlWorker] = {}
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.worker_states: Dict[str, WorkerState] = {}
        
        # 任务队列管理
        self.task_queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self.active_assignments: Dict[str, TaskAssignment] = {}  # task_id -> assignment
        self.worker_assignments: Dict[str, Set[str]] = defaultdict(set)  # worker_id -> task_ids
        
        # 调度统计
        self.scheduling_stats = {
            'total_assignments': 0,
            'successful_assignments': 0,
            'failed_assignments': 0,
            'average_assignment_time': 0.0,
            'queue_lengths': {priority.name: 0 for priority in TaskPriority},
            'worker_utilization': 0.0,
            'last_rebalance': None
        }
        
        # 性能历史
        self.performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.config.performance_window))
        
        # 控制标志
        self.running = False
        self.scheduler_task = None
        self.health_check_task = None
        self.rebalance_task = None
        
        # 锁
        self.assignment_lock = threading.RLock()
        self.metrics_lock = threading.RLock()
    
    async def initialize(self, worker_manager: WorkerManager) -> bool:
        """初始化调度器"""
        try:
            logger.info("初始化智能Worker调度器...")
            
            self.worker_manager = worker_manager
            self.persistence_manager = await get_persistence_manager()
            
            # 获取现有Workers
            await self._discover_workers()
            
            # 启动调度器
            await self.start()
            
            logger.info(f"智能调度器初始化成功，发现 {len(self.workers)} 个Worker")
            return True
            
        except Exception as e:
            logger.error(f"初始化智能调度器失败: {str(e)}")
            return False
    
    async def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        
        # 启动调度任务
        self.scheduler_task = asyncio.create_task(self._scheduling_loop())
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        self.rebalance_task = asyncio.create_task(self._rebalance_loop())
        
        logger.info("智能调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        self.running = False
        
        # 取消任务
        for task in [self.scheduler_task, self.health_check_task, self.rebalance_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("智能调度器已停止")
    
    async def submit_task(
        self,
        task: CrawlTask,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> bool:
        """提交任务到调度队列"""
        try:
            with self.assignment_lock:
                # 添加到优先级队列
                self.task_queues[priority].append(task)
                
                # 更新统计
                self.scheduling_stats['queue_lengths'][priority.name] += 1
                
                logger.debug(f"任务已提交到调度队列: {task.id}, 优先级: {priority.name}")
                
                # 触发立即调度
                await self._trigger_immediate_scheduling()
                
                return True
                
        except Exception as e:
            logger.error(f"提交任务失败: {str(e)}")
            return False
    
    async def _discover_workers(self):
        """发现可用的Workers"""
        try:
            if not self.worker_manager:
                return
            
            # 获取Worker统计信息
            stats = self.worker_manager.get_stats()
            workers_info = stats.get('workers', [])
            
            for worker_info in workers_info:
                worker_id = worker_info.get('id')
                if worker_id:
                    # 初始化Worker指标
                    self.worker_metrics[worker_id] = WorkerMetrics(
                        worker_id=worker_id,
                        max_load=1,  # 假设每个Worker最多处理1个任务
                        last_activity=datetime.now(timezone.utc)
                    )
                    
                    # 设置初始状态
                    self.worker_states[worker_id] = WorkerState.IDLE
                    
                    logger.debug(f"发现Worker: {worker_id}")
            
        except Exception as e:
            logger.error(f"发现Workers失败: {str(e)}")
    
    async def _scheduling_loop(self):
        """主调度循环"""
        while self.running:
            try:
                await self._process_task_queues()
                await asyncio.sleep(1)  # 1秒调度间隔
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环异常: {str(e)}")
                await asyncio.sleep(5)
    
    async def _process_task_queues(self):
        """处理任务队列"""
        try:
            with self.assignment_lock:
                # 按优先级处理队列
                for priority in TaskPriority:
                    queue = self.task_queues[priority]
                    
                    while queue and self._has_available_workers():
                        task = queue.popleft()
                        self.scheduling_stats['queue_lengths'][priority.name] -= 1
                        
                        # 分配任务
                        success = await self._assign_task(task, priority)
                        
                        if success:
                            self.scheduling_stats['successful_assignments'] += 1
                        else:
                            self.scheduling_stats['failed_assignments'] += 1
                            # 任务分配失败，重新放回队列
                            queue.appendleft(task)
                            self.scheduling_stats['queue_lengths'][priority.name] += 1
                            break
                        
                        self.scheduling_stats['total_assignments'] += 1
        
        except Exception as e:
            logger.error(f"处理任务队列失败: {str(e)}")
    
    def _has_available_workers(self) -> bool:
        """检查是否有可用的Workers"""
        try:
            for worker_id, state in self.worker_states.items():
                if state == WorkerState.IDLE:
                    metrics = self.worker_metrics.get(worker_id)
                    if metrics and metrics.current_load < metrics.max_load:
                        return True
            return False
            
        except Exception as e:
            logger.error(f"检查可用Workers失败: {str(e)}")
            return False
    
    async def _assign_task(self, task: CrawlTask, priority: TaskPriority) -> bool:
        """分配任务给Worker"""
        try:
            # 选择最佳Worker
            worker_id = await self._select_best_worker(task, priority)
            
            if not worker_id:
                logger.warning(f"没有可用的Worker来处理任务: {task.id}")
                return False
            
            # 创建任务分配
            assignment = TaskAssignment(
                task=task,
                worker_id=worker_id,
                assigned_time=datetime.now(timezone.utc),
                priority=priority,
                estimated_duration=self._estimate_task_duration(task, worker_id)
            )
            
            # 记录分配
            self.active_assignments[task.id] = assignment
            self.worker_assignments[worker_id].add(task.id)
            
            # 更新Worker状态
            metrics = self.worker_metrics[worker_id]
            metrics.current_load += 1
            
            if metrics.current_load >= metrics.max_load:
                self.worker_states[worker_id] = WorkerState.BUSY
            
            # 通知Worker处理任务
            await self._notify_worker(worker_id, task)
            
            logger.info(f"任务已分配: {task.id} -> Worker {worker_id}")
            return True
            
        except Exception as e:
            logger.error(f"分配任务失败: {str(e)}")
            return False
    
    async def _select_best_worker(self, task: CrawlTask, priority: TaskPriority) -> Optional[str]:
        """选择最佳Worker"""
        try:
            available_workers = []
            
            for worker_id, state in self.worker_states.items():
                if state in [WorkerState.IDLE, WorkerState.BUSY]:
                    metrics = self.worker_metrics.get(worker_id)
                    if metrics and metrics.current_load < metrics.max_load:
                        available_workers.append((worker_id, metrics))
            
            if not available_workers:
                return None
            
            # 根据调度策略选择Worker
            if self.config.strategy == SchedulingStrategy.ROUND_ROBIN:
                return self._select_round_robin(available_workers)
            elif self.config.strategy == SchedulingStrategy.LEAST_LOADED:
                return self._select_least_loaded(available_workers)
            elif self.config.strategy == SchedulingStrategy.PERFORMANCE_BASED:
                return self._select_performance_based(available_workers)
            elif self.config.strategy == SchedulingStrategy.INTELLIGENT:
                return self._select_intelligent(available_workers, task, priority)
            else:
                # 默认使用最少负载策略
                return self._select_least_loaded(available_workers)
                
        except Exception as e:
            logger.error(f"选择最佳Worker失败: {str(e)}")
            return None
    
    def _select_round_robin(self, available_workers: List[Tuple[str, WorkerMetrics]]) -> str:
        """轮询选择"""
        # 简单的轮询实现
        return available_workers[self.scheduling_stats['total_assignments'] % len(available_workers)][0]
    
    def _select_least_loaded(self, available_workers: List[Tuple[str, WorkerMetrics]]) -> str:
        """最少负载选择"""
        return min(available_workers, key=lambda x: x[1].current_load)[0]
    
    def _select_performance_based(self, available_workers: List[Tuple[str, WorkerMetrics]]) -> str:
        """基于性能选择"""
        return max(available_workers, key=lambda x: x[1].performance_score)[0]
    
    def _select_intelligent(self, available_workers: List[Tuple[str, WorkerMetrics]], task: CrawlTask, priority: TaskPriority) -> str:
        """智能选择"""
        try:
            best_worker = None
            best_score = -1.0
            
            priority_weight = self.config.priority_weights.get(priority, 0.6)
            
            for worker_id, metrics in available_workers:
                # 计算综合评分
                score = 0.0
                
                # 性能分数 (40%权重)
                score += metrics.performance_score * 0.4
                
                # 负载情况 (30%权重)
                load_factor = 1.0 - (metrics.current_load / max(metrics.max_load, 1))
                score += load_factor * 0.3
                
                # 优先级适配 (20%权重)
                score += priority_weight * 0.2
                
                # 历史表现 (10%权重)
                if metrics.total_tasks > 0:
                    success_rate = metrics.successful_tasks / metrics.total_tasks
                    score += success_rate * 0.1
                
                # 连续失败惩罚
                if metrics.consecutive_failures > 0:
                    score *= (1.0 - min(metrics.consecutive_failures * 0.1, 0.5))
                
                if score > best_score:
                    best_score = score
                    best_worker = worker_id
            
            return best_worker
            
        except Exception as e:
            logger.error(f"智能选择Worker失败: {str(e)}")
            # 降级到最少负载策略
            return self._select_least_loaded(available_workers)
    
    def _estimate_task_duration(self, task: CrawlTask, worker_id: str) -> float:
        """估算任务持续时间"""
        try:
            metrics = self.worker_metrics.get(worker_id)
            if metrics and metrics.average_processing_time > 0:
                return metrics.average_processing_time
            
            # 默认估算时间
            return 30.0
            
        except Exception as e:
            logger.debug(f"估算任务持续时间失败: {str(e)}")
            return 30.0
    
    async def _notify_worker(self, worker_id: str, task: CrawlTask):
        """通知Worker处理任务"""
        try:
            # 这里应该调用WorkerManager的方法来通知特定Worker
            # 由于当前架构限制，我们记录日志
            logger.info(f"通知Worker {worker_id} 处理任务 {task.id}")
            
            # 触发WorkerManager的立即任务检查
            if self.worker_manager:
                await self.worker_manager.trigger_immediate_task_check()
                
        except Exception as e:
            logger.error(f"通知Worker失败: {str(e)}")
    
    async def task_completed(self, task_id: str, worker_id: str, success: bool, processing_time: float):
        """任务完成回调"""
        try:
            with self.assignment_lock:
                # 移除任务分配
                assignment = self.active_assignments.pop(task_id, None)
                if assignment:
                    self.worker_assignments[worker_id].discard(task_id)
                
                # 更新Worker指标
                metrics = self.worker_metrics.get(worker_id)
                if metrics:
                    metrics.update_metrics(processing_time, success)
                    metrics.current_load = max(0, metrics.current_load - 1)
                    
                    # 更新Worker状态
                    if metrics.current_load == 0:
                        self.worker_states[worker_id] = WorkerState.IDLE
                    elif metrics.current_load < metrics.max_load:
                        self.worker_states[worker_id] = WorkerState.BUSY
                
                # 记录性能历史
                self.performance_history[worker_id].append({
                    'timestamp': datetime.now(timezone.utc),
                    'processing_time': processing_time,
                    'success': success,
                    'task_id': task_id
                })
                
                logger.debug(f"任务完成: {task_id}, Worker: {worker_id}, 成功: {success}, 耗时: {processing_time:.2f}s")
                
        except Exception as e:
            logger.error(f"处理任务完成回调失败: {str(e)}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查循环异常: {str(e)}")
                await asyncio.sleep(30)
    
    async def _perform_health_check(self):
        """执行健康检查"""
        try:
            current_time = datetime.now(timezone.utc)
            
            with self.metrics_lock:
                for worker_id, metrics in self.worker_metrics.items():
                    # 检查Worker是否长时间无活动
                    if metrics.last_activity:
                        idle_duration = (current_time - metrics.last_activity).total_seconds()
                        metrics.idle_time = idle_duration
                        
                        if idle_duration > self.config.idle_timeout:
                            if self.worker_states.get(worker_id) != WorkerState.MAINTENANCE:
                                logger.warning(f"Worker {worker_id} 长时间无活动: {idle_duration:.1f}s")
                                # 可以考虑重启或标记为维护状态
                    
                    # 检查连续失败
                    if metrics.consecutive_failures >= 5:
                        logger.warning(f"Worker {worker_id} 连续失败 {metrics.consecutive_failures} 次")
                        self.worker_states[worker_id] = WorkerState.FAILED
                    
                    # 检查错误率
                    if metrics.total_tasks >= 10 and metrics.error_rate > 0.5:
                        logger.warning(f"Worker {worker_id} 错误率过高: {metrics.error_rate:.2%}")
                
                # 更新整体利用率
                self._update_utilization_stats()
                
        except Exception as e:
            logger.error(f"执行健康检查失败: {str(e)}")
    
    def _update_utilization_stats(self):
        """更新利用率统计"""
        try:
            if not self.worker_metrics:
                self.scheduling_stats['worker_utilization'] = 0.0
                return
            
            total_capacity = sum(m.max_load for m in self.worker_metrics.values())
            current_load = sum(m.current_load for m in self.worker_metrics.values())
            
            self.scheduling_stats['worker_utilization'] = (
                current_load / total_capacity if total_capacity > 0 else 0.0
            )
            
        except Exception as e:
            logger.error(f"更新利用率统计失败: {str(e)}")
    
    async def _rebalance_loop(self):
        """负载重平衡循环"""
        while self.running:
            try:
                await self._perform_rebalancing()
                await asyncio.sleep(self.config.rebalance_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"重平衡循环异常: {str(e)}")
                await asyncio.sleep(60)
    
    async def _perform_rebalancing(self):
        """执行负载重平衡"""
        try:
            utilization = self.scheduling_stats['worker_utilization']
            
            # 检查是否需要扩容
            if utilization > self.config.scale_up_threshold and len(self.workers) < self.config.max_workers:
                logger.info(f"系统负载过高 ({utilization:.2%})，考虑扩容")
                # 这里可以触发Worker扩容逻辑
            
            # 检查是否需要缩容
            elif utilization < self.config.scale_down_threshold and len(self.workers) > self.config.min_workers:
                logger.info(f"系统负载较低 ({utilization:.2%})，考虑缩容")
                # 这里可以触发Worker缩容逻辑
            
            # 记录重平衡时间
            self.scheduling_stats['last_rebalance'] = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"执行负载重平衡失败: {str(e)}")
    
    async def _trigger_immediate_scheduling(self):
        """触发立即调度"""
        try:
            # 这里可以通过事件或信号量来触发立即调度
            # 当前实现中，调度循环会在1秒内自动处理
            pass
        except Exception as e:
            logger.error(f"触发立即调度失败: {str(e)}")
    
    def get_scheduling_stats(self) -> Dict[str, Any]:
        """获取调度统计信息"""
        try:
            with self.metrics_lock:
                stats = self.scheduling_stats.copy()
                
                # 添加Worker统计
                stats['workers'] = {
                    'total': len(self.worker_metrics),
                    'idle': sum(1 for state in self.worker_states.values() if state == WorkerState.IDLE),
                    'busy': sum(1 for state in self.worker_states.values() if state == WorkerState.BUSY),
                    'failed': sum(1 for state in self.worker_states.values() if state == WorkerState.FAILED),
                    'overloaded': sum(1 for state in self.worker_states.values() if state == WorkerState.OVERLOADED)
                }
                
                # 添加队列统计
                stats['queue_stats'] = {
                    'total_queued': sum(len(queue) for queue in self.task_queues.values()),
                    'by_priority': {priority.name: len(queue) for priority, queue in self.task_queues.items()}
                }
                
                # 添加性能统计
                if self.worker_metrics:
                    performance_scores = [m.performance_score for m in self.worker_metrics.values()]
                    stats['performance'] = {
                        'average_score': statistics.mean(performance_scores),
                        'min_score': min(performance_scores),
                        'max_score': max(performance_scores)
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"获取调度统计失败: {str(e)}")
            return {}
    
    def get_worker_details(self) -> Dict[str, Any]:
        """获取Worker详细信息"""
        try:
            with self.metrics_lock:
                details = {}
                
                for worker_id, metrics in self.worker_metrics.items():
                    state = self.worker_states.get(worker_id, WorkerState.IDLE)
                    assignments = self.worker_assignments.get(worker_id, set())
                    
                    details[worker_id] = {
                        'state': state.value,
                        'metrics': asdict(metrics),
                        'active_tasks': len(assignments),
                        'task_ids': list(assignments),
                        'performance_history': list(self.performance_history.get(worker_id, []))
                    }
                
                return details
                
        except Exception as e:
            logger.error(f"获取Worker详细信息失败: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        try:
            stats = self.get_scheduling_stats()
            worker_details = self.get_worker_details()
            
            # 计算健康分数
            health_score = 1.0
            
            # 检查Worker健康状态
            total_workers = stats['workers']['total']
            failed_workers = stats['workers']['failed']
            
            if total_workers > 0:
                worker_health = 1.0 - (failed_workers / total_workers)
                health_score *= worker_health
            
            # 检查队列积压
            total_queued = stats['queue_stats']['total_queued']
            if total_queued > 100:  # 队列积压阈值
                queue_health = max(0.5, 1.0 - (total_queued - 100) / 1000)
                health_score *= queue_health
            
            # 检查系统利用率
            utilization = stats.get('worker_utilization', 0.0)
            if utilization > 0.9:  # 过载
                utilization_health = max(0.6, 2.0 - utilization * 2)
                health_score *= utilization_health
            
            status = 'healthy'
            if health_score < 0.5:
                status = 'unhealthy'
            elif health_score < 0.8:
                status = 'degraded'
            
            return {
                'status': status,
                'health_score': health_score,
                'scheduler_running': self.running,
                'stats': stats,
                'worker_details': worker_details,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# 全局调度器实例
_scheduler = None

async def get_intelligent_scheduler(config: SchedulingConfig = None) -> IntelligentScheduler:
    """获取智能调度器实例"""
    global _scheduler
    
    if _scheduler is None:
        if config is None:
            config = SchedulingConfig()
        
        _scheduler = IntelligentScheduler(config)
    
    return _scheduler

async def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None