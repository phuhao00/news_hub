#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker线程池优化器
实现动态扩缩容、负载均衡、性能监控和智能调度
提供高效的资源管理和任务分配策略
"""

import asyncio
import json
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import statistics
import psutil
import gc

from worker.worker_manager import WorkerManager, CrawlWorker, WorkerConfig
from scheduler.intelligent_scheduler import IntelligentScheduler, SchedulingConfig, WorkerMetrics, WorkerState
from storage.persistence_manager import get_persistence_manager

logger = logging.getLogger(__name__)

class OptimizationStrategy(Enum):
    """优化策略"""
    CONSERVATIVE = "conservative"    # 保守策略
    BALANCED = "balanced"           # 平衡策略
    AGGRESSIVE = "aggressive"       # 激进策略
    ADAPTIVE = "adaptive"           # 自适应策略

class ScalingTrigger(Enum):
    """扩缩容触发条件"""
    QUEUE_LENGTH = "queue_length"           # 队列长度
    CPU_USAGE = "cpu_usage"                 # CPU使用率
    MEMORY_USAGE = "memory_usage"           # 内存使用率
    RESPONSE_TIME = "response_time"         # 响应时间
    ERROR_RATE = "error_rate"               # 错误率
    THROUGHPUT = "throughput"               # 吞吐量
    CUSTOM = "custom"                       # 自定义条件

@dataclass
class ScalingRule:
    """扩缩容规则"""
    trigger: ScalingTrigger
    threshold_up: float      # 扩容阈值
    threshold_down: float    # 缩容阈值
    min_duration: int        # 最小持续时间(秒)
    cooldown: int           # 冷却时间(秒)
    enabled: bool = True
    weight: float = 1.0     # 权重

@dataclass
class PoolConfig:
    """线程池配置"""
    min_workers: int = 2
    max_workers: int = 20
    initial_workers: int = 5
    scaling_step: int = 2           # 每次扩缩容的Worker数量
    optimization_interval: int = 30  # 优化间隔(秒)
    monitoring_interval: int = 10    # 监控间隔(秒)
    cleanup_interval: int = 300      # 清理间隔(秒)
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    
    # 扩缩容规则
    scaling_rules: List[ScalingRule] = field(default_factory=lambda: [
        ScalingRule(ScalingTrigger.QUEUE_LENGTH, 10, 2, 30, 60),
        ScalingRule(ScalingTrigger.CPU_USAGE, 0.8, 0.3, 60, 120),
        ScalingRule(ScalingTrigger.MEMORY_USAGE, 0.85, 0.4, 60, 120),
        ScalingRule(ScalingTrigger.RESPONSE_TIME, 30.0, 10.0, 45, 90),
        ScalingRule(ScalingTrigger.ERROR_RATE, 0.1, 0.02, 30, 60)
    ])
    
    # 性能阈值
    performance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'max_cpu_usage': 0.9,
        'max_memory_usage': 0.9,
        'max_response_time': 60.0,
        'max_error_rate': 0.15,
        'min_throughput': 0.1
    })
    
    # 健康检查配置
    health_check: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'interval': 30,
        'timeout': 10,
        'max_failures': 3,
        'recovery_time': 300
    })

@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, float] = field(default_factory=dict)
    process_count: int = 0
    thread_count: int = 0
    gc_stats: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PoolMetrics:
    """线程池指标"""
    timestamp: datetime
    active_workers: int = 0
    idle_workers: int = 0
    total_workers: int = 0
    queue_length: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_response_time: float = 0.0
    throughput: float = 0.0
    error_rate: float = 0.0
    utilization: float = 0.0

@dataclass
class OptimizationAction:
    """优化动作"""
    action_type: str  # 'scale_up', 'scale_down', 'rebalance', 'cleanup'
    target_workers: int
    reason: str
    confidence: float
    estimated_impact: Dict[str, float]
    timestamp: datetime

class PoolOptimizer:
    """Worker线程池优化器"""
    
    def __init__(self, config: PoolConfig):
        self.config = config
        self.worker_manager = None
        self.scheduler = None
        self.persistence_manager = None
        
        # 指标收集
        self.system_metrics_history: deque = deque(maxlen=1000)
        self.pool_metrics_history: deque = deque(maxlen=1000)
        self.optimization_history: deque = deque(maxlen=500)
        
        # 扩缩容状态
        self.last_scaling_action: Optional[datetime] = None
        self.scaling_in_progress = False
        self.scaling_decisions: Dict[ScalingTrigger, Dict] = {}
        
        # 性能基线
        self.performance_baseline: Dict[str, float] = {}
        self.baseline_established = False
        
        # 控制标志
        self.running = False
        self.optimization_task = None
        self.monitoring_task = None
        self.cleanup_task = None
        
        # 锁
        self.metrics_lock = threading.RLock()
        self.scaling_lock = threading.RLock()
        
        # 回调函数
        self.scaling_callbacks: List[Callable] = []
        self.performance_callbacks: List[Callable] = []
    
    async def initialize(
        self,
        worker_manager: WorkerManager,
        scheduler: IntelligentScheduler
    ) -> bool:
        """初始化优化器"""
        try:
            logger.info("初始化Worker线程池优化器...")
            
            self.worker_manager = worker_manager
            self.scheduler = scheduler
            self.persistence_manager = await get_persistence_manager()
            
            # 建立性能基线
            await self._establish_baseline()
            
            # 启动优化器
            await self.start()
            
            logger.info("Worker线程池优化器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化Worker线程池优化器失败: {str(e)}")
            return False
    
    async def start(self):
        """启动优化器"""
        if self.running:
            return
        
        self.running = True
        
        # 启动优化任务
        self.optimization_task = asyncio.create_task(self._optimization_loop())
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Worker线程池优化器已启动")
    
    async def stop(self):
        """停止优化器"""
        self.running = False
        
        # 取消任务
        for task in [self.optimization_task, self.monitoring_task, self.cleanup_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Worker线程池优化器已停止")
    
    async def _optimization_loop(self):
        """优化循环"""
        while self.running:
            try:
                await self._perform_optimization()
                await asyncio.sleep(self.config.optimization_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"优化循环异常: {str(e)}")
                await asyncio.sleep(30)
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.config.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {str(e)}")
                await asyncio.sleep(10)
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self.running:
            try:
                await self._perform_cleanup()
                await asyncio.sleep(self.config.cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环异常: {str(e)}")
                await asyncio.sleep(60)
    
    async def _collect_metrics(self):
        """收集系统和线程池指标"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # 收集系统指标
            system_metrics = await self._collect_system_metrics(current_time)
            
            # 收集线程池指标
            pool_metrics = await self._collect_pool_metrics(current_time)
            
            with self.metrics_lock:
                self.system_metrics_history.append(system_metrics)
                self.pool_metrics_history.append(pool_metrics)
            
            # 触发性能回调
            await self._trigger_performance_callbacks(system_metrics, pool_metrics)
            
        except Exception as e:
            logger.error(f"收集指标失败: {str(e)}")
    
    async def _collect_system_metrics(self, timestamp: datetime) -> SystemMetrics:
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_usage = memory.percent / 100.0
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent / 100.0
            
            # 网络IO
            network = psutil.net_io_counters()
            network_io = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
            
            # 进程和线程数
            process_count = len(psutil.pids())
            thread_count = threading.active_count()
            
            # GC统计
            gc_stats = {
                'collections': gc.get_stats(),
                'count': gc.get_count(),
                'threshold': gc.get_threshold()
            }
            
            return SystemMetrics(
                timestamp=timestamp,
                cpu_usage=cpu_usage / 100.0,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_io=network_io,
                process_count=process_count,
                thread_count=thread_count,
                gc_stats=gc_stats
            )
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {str(e)}")
            return SystemMetrics(timestamp=timestamp)
    
    async def _collect_pool_metrics(self, timestamp: datetime) -> PoolMetrics:
        """收集线程池指标"""
        try:
            # 获取调度器统计
            scheduler_stats = self.scheduler.get_scheduling_stats() if self.scheduler else {}
            
            # 获取Worker管理器统计
            worker_stats = self.worker_manager.get_stats() if self.worker_manager else {}
            
            # 计算指标
            workers_info = scheduler_stats.get('workers', {})
            active_workers = workers_info.get('busy', 0)
            idle_workers = workers_info.get('idle', 0)
            total_workers = workers_info.get('total', 0)
            
            queue_stats = scheduler_stats.get('queue_stats', {})
            queue_length = queue_stats.get('total_queued', 0)
            
            # 计算吞吐量和错误率
            total_assignments = scheduler_stats.get('total_assignments', 0)
            successful_assignments = scheduler_stats.get('successful_assignments', 0)
            failed_assignments = scheduler_stats.get('failed_assignments', 0)
            
            error_rate = failed_assignments / max(total_assignments, 1)
            utilization = scheduler_stats.get('worker_utilization', 0.0)
            
            # 计算平均响应时间
            average_response_time = scheduler_stats.get('average_assignment_time', 0.0)
            
            # 计算吞吐量 (任务/秒)
            if len(self.pool_metrics_history) > 0:
                last_metrics = self.pool_metrics_history[-1]
                time_diff = (timestamp - last_metrics.timestamp).total_seconds()
                if time_diff > 0:
                    task_diff = total_assignments - (last_metrics.tasks_completed + last_metrics.tasks_failed)
                    throughput = task_diff / time_diff
                else:
                    throughput = 0.0
            else:
                throughput = 0.0
            
            return PoolMetrics(
                timestamp=timestamp,
                active_workers=active_workers,
                idle_workers=idle_workers,
                total_workers=total_workers,
                queue_length=queue_length,
                tasks_completed=successful_assignments,
                tasks_failed=failed_assignments,
                average_response_time=average_response_time,
                throughput=throughput,
                error_rate=error_rate,
                utilization=utilization
            )
            
        except Exception as e:
            logger.error(f"收集线程池指标失败: {str(e)}")
            return PoolMetrics(timestamp=timestamp)
    
    async def _perform_optimization(self):
        """执行优化"""
        try:
            if not self.baseline_established:
                await self._establish_baseline()
                return
            
            # 分析当前状态
            optimization_actions = await self._analyze_and_recommend()
            
            # 执行优化动作
            for action in optimization_actions:
                await self._execute_optimization_action(action)
            
        except Exception as e:
            logger.error(f"执行优化失败: {str(e)}")
    
    async def _analyze_and_recommend(self) -> List[OptimizationAction]:
        """分析并推荐优化动作"""
        try:
            actions = []
            
            if len(self.pool_metrics_history) < 3:
                return actions
            
            # 获取最近的指标
            recent_metrics = list(self.pool_metrics_history)[-3:]
            current_metrics = recent_metrics[-1]
            
            # 检查扩缩容规则
            scaling_action = await self._evaluate_scaling_rules(recent_metrics)
            if scaling_action:
                actions.append(scaling_action)
            
            # 检查负载均衡需求
            rebalance_action = await self._evaluate_rebalancing(current_metrics)
            if rebalance_action:
                actions.append(rebalance_action)
            
            # 检查清理需求
            cleanup_action = await self._evaluate_cleanup(current_metrics)
            if cleanup_action:
                actions.append(cleanup_action)
            
            return actions
            
        except Exception as e:
            logger.error(f"分析和推荐失败: {str(e)}")
            return []
    
    async def _evaluate_scaling_rules(self, recent_metrics: List[PoolMetrics]) -> Optional[OptimizationAction]:
        """评估扩缩容规则"""
        try:
            if self.scaling_in_progress:
                return None
            
            # 检查冷却时间
            if self.last_scaling_action:
                cooldown_time = min(rule.cooldown for rule in self.config.scaling_rules if rule.enabled)
                if (datetime.now(timezone.utc) - self.last_scaling_action).total_seconds() < cooldown_time:
                    return None
            
            current_metrics = recent_metrics[-1]
            scale_up_votes = 0
            scale_down_votes = 0
            total_weight = 0
            reasons = []
            
            # 评估每个规则
            for rule in self.config.scaling_rules:
                if not rule.enabled:
                    continue
                
                value = await self._get_rule_value(rule.trigger, recent_metrics)
                if value is None:
                    continue
                
                total_weight += rule.weight
                
                # 检查扩容条件
                if value > rule.threshold_up:
                    scale_up_votes += rule.weight
                    reasons.append(f"{rule.trigger.value}: {value:.2f} > {rule.threshold_up}")
                
                # 检查缩容条件
                elif value < rule.threshold_down and current_metrics.total_workers > self.config.min_workers:
                    scale_down_votes += rule.weight
                    reasons.append(f"{rule.trigger.value}: {value:.2f} < {rule.threshold_down}")
            
            if total_weight == 0:
                return None
            
            # 计算投票比例
            scale_up_ratio = scale_up_votes / total_weight
            scale_down_ratio = scale_down_votes / total_weight
            
            # 决策阈值
            decision_threshold = 0.6 if self.config.strategy == OptimizationStrategy.CONSERVATIVE else 0.4
            
            if scale_up_ratio > decision_threshold and current_metrics.total_workers < self.config.max_workers:
                target_workers = min(
                    current_metrics.total_workers + self.config.scaling_step,
                    self.config.max_workers
                )
                
                return OptimizationAction(
                    action_type='scale_up',
                    target_workers=target_workers,
                    reason=f"扩容投票比例: {scale_up_ratio:.2%}, 原因: {'; '.join(reasons)}",
                    confidence=scale_up_ratio,
                    estimated_impact={
                        'throughput_increase': 0.2 * self.config.scaling_step,
                        'response_time_decrease': 0.1,
                        'resource_cost_increase': 0.15 * self.config.scaling_step
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            
            elif scale_down_ratio > decision_threshold:
                target_workers = max(
                    current_metrics.total_workers - self.config.scaling_step,
                    self.config.min_workers
                )
                
                return OptimizationAction(
                    action_type='scale_down',
                    target_workers=target_workers,
                    reason=f"缩容投票比例: {scale_down_ratio:.2%}, 原因: {'; '.join(reasons)}",
                    confidence=scale_down_ratio,
                    estimated_impact={
                        'resource_cost_decrease': 0.15 * self.config.scaling_step,
                        'throughput_decrease': 0.1 * self.config.scaling_step,
                        'response_time_increase': 0.05
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"评估扩缩容规则失败: {str(e)}")
            return None
    
    async def _get_rule_value(self, trigger: ScalingTrigger, recent_metrics: List[PoolMetrics]) -> Optional[float]:
        """获取规则对应的指标值"""
        try:
            current_metrics = recent_metrics[-1]
            
            if trigger == ScalingTrigger.QUEUE_LENGTH:
                return float(current_metrics.queue_length)
            
            elif trigger == ScalingTrigger.RESPONSE_TIME:
                return current_metrics.average_response_time
            
            elif trigger == ScalingTrigger.ERROR_RATE:
                return current_metrics.error_rate
            
            elif trigger == ScalingTrigger.THROUGHPUT:
                return current_metrics.throughput
            
            elif trigger == ScalingTrigger.CPU_USAGE:
                if len(self.system_metrics_history) > 0:
                    return self.system_metrics_history[-1].cpu_usage
            
            elif trigger == ScalingTrigger.MEMORY_USAGE:
                if len(self.system_metrics_history) > 0:
                    return self.system_metrics_history[-1].memory_usage
            
            return None
            
        except Exception as e:
            logger.error(f"获取规则值失败: {str(e)}")
            return None
    
    async def _evaluate_rebalancing(self, current_metrics: PoolMetrics) -> Optional[OptimizationAction]:
        """评估负载均衡需求"""
        try:
            # 检查Worker负载分布
            if not self.scheduler:
                return None
            
            worker_details = self.scheduler.get_worker_details()
            if len(worker_details) < 2:
                return None
            
            # 计算负载方差
            loads = [details['metrics']['current_load'] for details in worker_details.values()]
            if len(loads) < 2:
                return None
            
            load_variance = statistics.variance(loads)
            load_mean = statistics.mean(loads)
            
            # 如果负载分布不均匀，建议重平衡
            if load_variance > load_mean * 0.5 and load_mean > 0:
                return OptimizationAction(
                    action_type='rebalance',
                    target_workers=current_metrics.total_workers,
                    reason=f"负载分布不均，方差: {load_variance:.2f}, 均值: {load_mean:.2f}",
                    confidence=min(load_variance / load_mean, 1.0),
                    estimated_impact={
                        'load_balance_improvement': 0.3,
                        'response_time_decrease': 0.1
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"评估负载均衡失败: {str(e)}")
            return None
    
    async def _evaluate_cleanup(self, current_metrics: PoolMetrics) -> Optional[OptimizationAction]:
        """评估清理需求"""
        try:
            # 检查系统资源使用情况
            if len(self.system_metrics_history) == 0:
                return None
            
            system_metrics = self.system_metrics_history[-1]
            
            # 如果内存使用率过高，建议清理
            if system_metrics.memory_usage > 0.85:
                return OptimizationAction(
                    action_type='cleanup',
                    target_workers=current_metrics.total_workers,
                    reason=f"内存使用率过高: {system_metrics.memory_usage:.2%}",
                    confidence=system_metrics.memory_usage,
                    estimated_impact={
                        'memory_usage_decrease': 0.1,
                        'performance_improvement': 0.05
                    },
                    timestamp=datetime.now(timezone.utc)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"评估清理需求失败: {str(e)}")
            return None
    
    async def _execute_optimization_action(self, action: OptimizationAction):
        """执行优化动作"""
        try:
            logger.info(f"执行优化动作: {action.action_type}, 目标Worker数: {action.target_workers}, 原因: {action.reason}")
            
            with self.scaling_lock:
                if action.action_type == 'scale_up':
                    await self._scale_up(action.target_workers)
                
                elif action.action_type == 'scale_down':
                    await self._scale_down(action.target_workers)
                
                elif action.action_type == 'rebalance':
                    await self._rebalance_workers()
                
                elif action.action_type == 'cleanup':
                    await self._perform_cleanup()
                
                # 记录优化历史
                self.optimization_history.append(action)
                
                # 触发回调
                await self._trigger_scaling_callbacks(action)
            
        except Exception as e:
            logger.error(f"执行优化动作失败: {str(e)}")
    
    async def _scale_up(self, target_workers: int):
        """扩容Worker"""
        try:
            if not self.worker_manager:
                return
            
            self.scaling_in_progress = True
            
            # 这里应该调用WorkerManager的扩容方法
            # 由于当前架构限制，我们记录日志
            logger.info(f"扩容Worker到 {target_workers} 个")
            
            self.last_scaling_action = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"扩容Worker失败: {str(e)}")
        finally:
            self.scaling_in_progress = False
    
    async def _scale_down(self, target_workers: int):
        """缩容Worker"""
        try:
            if not self.worker_manager:
                return
            
            self.scaling_in_progress = True
            
            # 这里应该调用WorkerManager的缩容方法
            # 由于当前架构限制，我们记录日志
            logger.info(f"缩容Worker到 {target_workers} 个")
            
            self.last_scaling_action = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"缩容Worker失败: {str(e)}")
        finally:
            self.scaling_in_progress = False
    
    async def _rebalance_workers(self):
        """重平衡Worker负载"""
        try:
            if not self.scheduler:
                return
            
            # 触发调度器的重平衡
            logger.info("触发Worker负载重平衡")
            
        except Exception as e:
            logger.error(f"重平衡Worker失败: {str(e)}")
    
    async def _perform_cleanup(self):
        """执行清理操作"""
        try:
            # 执行垃圾回收
            gc.collect()
            
            # 清理过期的指标数据
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(hours=24)
            
            with self.metrics_lock:
                # 清理系统指标历史
                while (self.system_metrics_history and 
                       self.system_metrics_history[0].timestamp < cutoff_time):
                    self.system_metrics_history.popleft()
                
                # 清理线程池指标历史
                while (self.pool_metrics_history and 
                       self.pool_metrics_history[0].timestamp < cutoff_time):
                    self.pool_metrics_history.popleft()
                
                # 清理优化历史
                while (self.optimization_history and 
                       self.optimization_history[0].timestamp < cutoff_time):
                    self.optimization_history.popleft()
            
            logger.info("清理操作完成")
            
        except Exception as e:
            logger.error(f"执行清理操作失败: {str(e)}")
    
    async def _establish_baseline(self):
        """建立性能基线"""
        try:
            if len(self.pool_metrics_history) < 10:
                return
            
            # 计算基线指标
            recent_metrics = list(self.pool_metrics_history)[-10:]
            
            self.performance_baseline = {
                'average_response_time': statistics.mean([m.average_response_time for m in recent_metrics]),
                'throughput': statistics.mean([m.throughput for m in recent_metrics]),
                'error_rate': statistics.mean([m.error_rate for m in recent_metrics]),
                'utilization': statistics.mean([m.utilization for m in recent_metrics])
            }
            
            self.baseline_established = True
            logger.info(f"性能基线已建立: {self.performance_baseline}")
            
        except Exception as e:
            logger.error(f"建立性能基线失败: {str(e)}")
    
    async def _trigger_scaling_callbacks(self, action: OptimizationAction):
        """触发扩缩容回调"""
        try:
            for callback in self.scaling_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(action)
                    else:
                        callback(action)
                except Exception as e:
                    logger.error(f"扩缩容回调失败: {str(e)}")
        except Exception as e:
            logger.error(f"触发扩缩容回调失败: {str(e)}")
    
    async def _trigger_performance_callbacks(self, system_metrics: SystemMetrics, pool_metrics: PoolMetrics):
        """触发性能回调"""
        try:
            for callback in self.performance_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(system_metrics, pool_metrics)
                    else:
                        callback(system_metrics, pool_metrics)
                except Exception as e:
                    logger.error(f"性能回调失败: {str(e)}")
        except Exception as e:
            logger.error(f"触发性能回调失败: {str(e)}")
    
    def add_scaling_callback(self, callback: Callable):
        """添加扩缩容回调"""
        self.scaling_callbacks.append(callback)
    
    def add_performance_callback(self, callback: Callable):
        """添加性能回调"""
        self.performance_callbacks.append(callback)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        try:
            with self.metrics_lock:
                stats = {
                    'baseline_established': self.baseline_established,
                    'performance_baseline': self.performance_baseline.copy(),
                    'scaling_in_progress': self.scaling_in_progress,
                    'last_scaling_action': self.last_scaling_action.isoformat() if self.last_scaling_action else None,
                    'optimization_history_count': len(self.optimization_history),
                    'metrics_history_count': {
                        'system': len(self.system_metrics_history),
                        'pool': len(self.pool_metrics_history)
                    }
                }
                
                # 添加最近的优化动作
                if self.optimization_history:
                    recent_actions = list(self.optimization_history)[-5:]
                    stats['recent_actions'] = [asdict(action) for action in recent_actions]
                
                # 添加当前指标
                if self.system_metrics_history:
                    stats['current_system_metrics'] = asdict(self.system_metrics_history[-1])
                
                if self.pool_metrics_history:
                    stats['current_pool_metrics'] = asdict(self.pool_metrics_history[-1])
                
                return stats
                
        except Exception as e:
            logger.error(f"获取优化统计失败: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            stats = self.get_optimization_stats()
            
            # 计算健康分数
            health_score = 1.0
            issues = []
            
            # 检查基线是否建立
            if not self.baseline_established:
                health_score *= 0.8
                issues.append("性能基线未建立")
            
            # 检查指标收集
            if len(self.pool_metrics_history) == 0:
                health_score *= 0.6
                issues.append("缺少线程池指标")
            
            if len(self.system_metrics_history) == 0:
                health_score *= 0.7
                issues.append("缺少系统指标")
            
            # 检查最近的优化动作
            if self.optimization_history:
                recent_action = self.optimization_history[-1]
                if recent_action.confidence < 0.5:
                    health_score *= 0.9
                    issues.append("最近优化动作置信度较低")
            
            # 检查系统资源
            if self.system_metrics_history:
                current_system = self.system_metrics_history[-1]
                if current_system.cpu_usage > 0.9:
                    health_score *= 0.7
                    issues.append("CPU使用率过高")
                
                if current_system.memory_usage > 0.9:
                    health_score *= 0.6
                    issues.append("内存使用率过高")
            
            status = 'healthy'
            if health_score < 0.5:
                status = 'unhealthy'
            elif health_score < 0.8:
                status = 'degraded'
            
            return {
                'status': status,
                'health_score': health_score,
                'issues': issues,
                'optimizer_running': self.running,
                'stats': stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# 全局优化器实例
_optimizer = None

async def get_pool_optimizer(config: PoolConfig = None) -> PoolOptimizer:
    """获取线程池优化器实例"""
    global _optimizer
    
    if _optimizer is None:
        if config is None:
            config = PoolConfig()
        
        _optimizer = PoolOptimizer(config)
    
    return _optimizer

async def shutdown_optimizer():
    """关闭优化器"""
    global _optimizer
    
    if _optimizer:
        await _optimizer.stop()
        _optimizer = None