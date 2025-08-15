import asyncio
import threading
import time
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
import redis
from queue import Queue, Empty
import uuid

# 导入现有的爬虫服务
# 避免循环导入，使用类型注解
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import UnifiedCrawlerService
from logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class CrawlTask:
    """爬取任务数据结构"""
    id: str
    url: str
    platform: Optional[str] = None
    priority: str = "medium"
    timeout: int = 30
    extract_content: bool = True
    extract_links: bool = False
    extract_images: bool = False
    css_selector: Optional[str] = None
    word_count_threshold: int = 10
    created_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class CrawlResult:
    """爬取结果数据结构"""
    task_id: str
    url: str
    title: str
    content: str
    markdown: str
    links: List[Dict[str, str]] = None
    images: List[Dict[str, str]] = None
    metadata: Dict[str, Any] = None
    success: bool = True
    error_message: Optional[str] = None
    processing_time: float = 0.0
    crawled_at: Optional[str] = None
    worker_id: str = ""

    def __post_init__(self):
        if self.links is None:
            self.links = []
        if self.images is None:
            self.images = []
        if self.metadata is None:
            self.metadata = {}
        if self.crawled_at is None:
            self.crawled_at = datetime.now().isoformat()

class WorkerConfig:
    """Worker配置类"""
    def __init__(self, config_dict: Dict[str, Any] = None):
        config = config_dict or {}
        
        # Redis配置
        self.redis_host = config.get('redis_host', 'localhost')
        self.redis_port = config.get('redis_port', 6379)
        self.redis_db = config.get('redis_db', 0)
        self.redis_password = config.get('redis_password', None)
        
        # Go后端API配置
        self.backend_api_url = config.get('backend_api_url', 'http://localhost:8081')
        self.api_timeout = config.get('api_timeout', 10)
        
        # Worker配置
        self.worker_count = config.get('worker_count', 3)
        self.max_concurrent_tasks = config.get('max_concurrent_tasks', 5)
        self.task_timeout = config.get('task_timeout', 60)
        self.heartbeat_interval = config.get('heartbeat_interval', 30)
        self.queue_check_interval = config.get('queue_check_interval', 1)
        
        # 队列配置
        self.task_queue_key = config.get('task_queue_key', 'crawl_tasks')
        self.priority_queues = {
            'high': f"{self.task_queue_key}:high",
            'medium': f"{self.task_queue_key}:medium", 
            'low': f"{self.task_queue_key}:low"
        }

class CrawlWorker:
    """单个爬虫Worker"""
    
    def __init__(self, worker_id: str, config: WorkerConfig):
        self.worker_id = worker_id
        self.config = config
        self.running = False
        self.current_task: Optional[CrawlTask] = None
        self.crawler_service = None  # 动态导入，避免循环导入
        self.redis_client = None
        self.task_queue = Queue()
        self.stats = {
            'tasks_processed': 0,
            'tasks_succeeded': 0,
            'tasks_failed': 0,
            'start_time': None,
            'last_task_time': None
        }
        
    async def initialize(self):
        """初始化Worker"""
        try:
            # 初始化Redis客户端
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True
            )
            
            # 初始化爬虫服务
            # 动态导入避免循环导入
            from main import UnifiedCrawlerService
            self.crawler_service = UnifiedCrawlerService()
            await self.crawler_service.ensure_initialized()
            
            self.stats['start_time'] = datetime.now().isoformat()
            logger.info(f"Worker {self.worker_id} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize worker {self.worker_id}: {e}")
            raise
    
    async def start(self):
        """启动Worker"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Worker {self.worker_id} started")
        
        try:
            while self.running:
                try:
                    # 从Go后端获取下一个任务
                    task = await self._get_next_task()
                    if task:
                        await self._process_task(task)
                    else:
                        # 没有任务时短暂休眠
                        await asyncio.sleep(self.config.queue_check_interval)
                        
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error: {e}")
                    await asyncio.sleep(5)  # 错误后等待5秒再继续
                    
        except asyncio.CancelledError:
            logger.info(f"Worker {self.worker_id} cancelled")
        finally:
            await self._cleanup()
    
    async def stop(self):
        """停止Worker"""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopping")
    
    async def _trigger_immediate_check(self):
        """触发立即任务检查 - 跳过等待直接检查任务"""
        if not self.running or self.current_task is not None:
            return
            
        try:
            # 立即尝试获取任务
            task = await self._get_next_task()
            if task:
                logger.info(f"Worker {self.worker_id} got immediate task: {task.id}")
                await self._process_task(task)
            else:
                logger.debug(f"Worker {self.worker_id} no immediate task available")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} error in immediate check: {e}")
    
    async def _get_next_task(self) -> Optional[CrawlTask]:
        """从Go后端获取下一个任务"""
        try:
            url = f"{self.config.backend_api_url}/api/v1/tasks/next"
            params = {'worker_id': self.worker_id}
            
            response = requests.get(url, params=params, timeout=self.config.api_timeout)
            
            if response.status_code == 200:
                task_data = response.json()
                if task_data and 'data' in task_data:
                    return CrawlTask(**task_data['data'])
            elif response.status_code == 404:
                # 没有可用任务
                return None
            else:
                logger.warning(f"Failed to get next task: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error getting next task: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting next task: {e}")
            return None
    
    async def _process_task(self, task: CrawlTask):
        """处理爬取任务"""
        start_time = time.time()
        self.current_task = task
        self.stats['last_task_time'] = datetime.now().isoformat()
        
        logger.info(f"Worker {self.worker_id} processing task {task.id}: {task.url}")
        
        try:
            # 更新任务状态为处理中
            await self._update_task_status(task.id, 'processing')
            
            # 执行爬取
            result = await self._crawl_url(task)
            
            # 计算处理时间
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            result.worker_id = self.worker_id
            
            # 发送结果到Go后端
            await self._send_result(result)
            
            self.stats['tasks_processed'] += 1
            self.stats['tasks_succeeded'] += 1
            
            logger.info(f"Worker {self.worker_id} completed task {task.id} in {processing_time:.2f}s")
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            # 创建失败结果
            result = CrawlResult(
                task_id=task.id,
                url=task.url,
                title="",
                content="",
                markdown="",
                success=False,
                error_message=error_msg,
                processing_time=processing_time,
                worker_id=self.worker_id
            )
            
            # 发送失败结果
            await self._send_result(result)
            
            self.stats['tasks_processed'] += 1
            self.stats['tasks_failed'] += 1
            
            logger.error(f"Worker {self.worker_id} failed to process task {task.id}: {error_msg}")
            
        finally:
            self.current_task = None
    
    async def _crawl_url(self, task: CrawlTask) -> CrawlResult:
        """执行URL爬取"""
        try:
            # 使用MCP服务进行爬取
            if self.crawler_service.mcp_enabled:
                mcp_result = await self.crawler_service.crawl_with_mcp(
                    task.url, 
                    platform=task.platform
                )
                
                return CrawlResult(
                    task_id=task.id,
                    url=task.url,
                    title=mcp_result.title,
                    content=mcp_result.content,
                    markdown=mcp_result.markdown,
                    links=mcp_result.links,
                    images=mcp_result.images,
                    metadata=mcp_result.metadata,
                    success=mcp_result.success,
                    error_message=mcp_result.error_message
                )
            else:
                # 使用传统爬取方式
                # 这里可以实现传统的爬取逻辑作为备用
                raise NotImplementedError("Traditional crawling not implemented yet")
                
        except Exception as e:
            logger.error(f"Crawling failed for {task.url}: {e}")
            raise
    
    async def _update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        try:
            url = f"{self.config.backend_api_url}/api/v1/tasks/{task_id}/status"
            data = {
                'status': status,
                'worker_id': self.worker_id
            }
            
            response = requests.put(url, json=data, timeout=self.config.api_timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to update task status: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            logger.error(f"Error updating task status: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating task status: {e}")
    
    async def _send_result(self, result: CrawlResult):
        """发送爬取结果到Go后端"""
        try:
            url = f"{self.config.backend_api_url}/api/v1/tasks/{result.task_id}/status"
            
            if result.success:
                data = {
                    'status': 'completed',
                    'result': asdict(result),
                    'execution_time': result.processing_time,
                    'worker_id': self.worker_id
                }
            else:
                data = {
                    'status': 'failed',
                    'error_message': result.error_message,
                    'worker_id': self.worker_id
                }
            
            response = requests.put(url, json=data, timeout=self.config.api_timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to send result: {response.status_code} - {response.text}")
            else:
                logger.debug(f"Result sent successfully for task {result.task_id}")
                
        except requests.RequestException as e:
            logger.error(f"Error sending result: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending result: {e}")
    
    async def _cleanup(self):
        """清理资源"""
        try:
            if self.crawler_service:
                await self.crawler_service.cleanup()
            if self.redis_client:
                self.redis_client.close()
            logger.info(f"Worker {self.worker_id} cleanup completed")
        except Exception as e:
            logger.error(f"Error during worker cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取Worker统计信息"""
        stats = self.stats.copy()
        stats['worker_id'] = self.worker_id
        stats['running'] = self.running
        stats['current_task'] = self.current_task.id if self.current_task else None
        return stats
    
    async def _trigger_immediate_check(self):
        """触发立即检查任务队列"""
        if not self.running or self.current_task is not None:
            return
            
        logger.debug(f"Worker {self.worker_id} triggered immediate task check")
        
        # 立即尝试获取任务
        task = await self._get_next_task()
        if task:
            logger.info(f"Worker {self.worker_id} found immediate task: {task.id}")
            await self._process_task(task)

class WorkerManager:
    """Worker管理器"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.workers: Dict[str, CrawlWorker] = {}
        self.worker_tasks: Dict[str, asyncio.Task] = {}
        self.running = False
        self.manager_id = f"manager_{uuid.uuid4().hex[:8]}"
        
    async def start(self):
        """启动Worker管理器"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Worker manager {self.manager_id} starting with {self.config.worker_count} workers")
        
        # 创建并启动Workers
        for i in range(self.config.worker_count):
            worker_id = f"worker_{self.manager_id}_{i}"
            worker = CrawlWorker(worker_id, self.config)
            
            try:
                await worker.initialize()
                self.workers[worker_id] = worker
                
                # 启动Worker任务
                task = asyncio.create_task(worker.start())
                self.worker_tasks[worker_id] = task
                
                logger.info(f"Worker {worker_id} started")
                
            except Exception as e:
                logger.error(f"Failed to start worker {worker_id}: {e}")
        
        logger.info(f"Worker manager started with {len(self.workers)} workers")
        
        # 启动空闲监控
        self.idle_monitoring_task = asyncio.create_task(self.start_idle_monitoring())
        logger.info("Idle monitoring started")
    
    async def stop(self):
        """停止Worker管理器"""
        if not self.running:
            return
            
        self.running = False
        logger.info(f"Worker manager {self.manager_id} stopping")
        
        # 停止所有Workers
        for worker_id, worker in self.workers.items():
            try:
                await worker.stop()
            except Exception as e:
                logger.error(f"Error stopping worker {worker_id}: {e}")
        
        # 停止空闲监控
        if hasattr(self, 'idle_monitoring_task'):
            try:
                self.idle_monitoring_task.cancel()
                await self.idle_monitoring_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling idle monitoring task: {e}")
        
        # 取消所有Worker任务
        for worker_id, task in self.worker_tasks.items():
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling worker task {worker_id}: {e}")
        
        self.workers.clear()
        self.worker_tasks.clear()
        
        logger.info(f"Worker manager {self.manager_id} stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        worker_stats = [worker.get_stats() for worker in self.workers.values()]
        
        total_processed = sum(stats['tasks_processed'] for stats in worker_stats)
        total_succeeded = sum(stats['tasks_succeeded'] for stats in worker_stats)
        total_failed = sum(stats['tasks_failed'] for stats in worker_stats)
        
        return {
            'manager_id': self.manager_id,
            'running': self.running,
            'worker_count': len(self.workers),
            'total_tasks_processed': total_processed,
            'total_tasks_succeeded': total_succeeded,
            'total_tasks_failed': total_failed,
            'success_rate': (total_succeeded / total_processed * 100) if total_processed > 0 else 0,
            'workers': worker_stats
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        healthy_workers = 0
        unhealthy_workers = 0
        
        for worker in self.workers.values():
            if worker.running:
                healthy_workers += 1
            else:
                unhealthy_workers += 1
        
        return {
            'manager_healthy': self.running,
            'total_workers': len(self.workers),
            'healthy_workers': healthy_workers,
            'unhealthy_workers': unhealthy_workers,
            'health_status': 'healthy' if unhealthy_workers == 0 else 'degraded'
        }
    
    async def trigger_immediate_check(self) -> Dict[str, Any]:
        """触发立即检查队列 - 对外API接口"""
        if not self.running:
            return {
                'success': False,
                'message': 'Worker manager is not running',
                'idle_workers': 0
            }
        
        idle_workers = self.get_idle_workers()
        
        if not idle_workers:
            return {
                'success': True,
                'message': 'No idle workers available',
                'idle_workers': 0
            }
        
        # 触发立即任务检查
        await self.trigger_immediate_task_check()
        
        return {
            'success': True,
            'message': f'Triggered immediate check for {len(idle_workers)} idle workers',
            'idle_workers': len(idle_workers),
            'worker_ids': idle_workers
        }
    
    def get_idle_workers(self) -> List[str]:
        """获取空闲Worker列表"""
        idle_workers = []
        for worker_id, worker in self.workers.items():
            if worker.running and worker.current_task is None:
                idle_workers.append(worker_id)
        return idle_workers
    
    async def trigger_immediate_task_check(self):
        """触发立即任务检查 - 让空闲Worker主动获取任务"""
        if not self.running:
            return
            
        idle_workers = self.get_idle_workers()
        if idle_workers:
            logger.info(f"Found {len(idle_workers)} idle workers, triggering immediate task check")
            
            # 通知空闲Worker立即检查任务
            for worker_id in idle_workers:
                worker = self.workers.get(worker_id)
                if worker and hasattr(worker, '_trigger_immediate_check'):
                    try:
                        await worker._trigger_immediate_check()
                    except Exception as e:
                        logger.error(f"Error triggering immediate check for worker {worker_id}: {e}")
    
    async def start_idle_monitoring(self, check_interval: float = 1.0):
        """启动空闲监控 - 定期检查是否有空闲Worker可以处理任务"""
        if not self.running:
            return
            
        logger.info(f"Starting idle monitoring with {check_interval}s interval")
        
        while self.running:
            try:
                await self.trigger_immediate_task_check()
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle monitoring: {e}")
                await asyncio.sleep(check_interval)