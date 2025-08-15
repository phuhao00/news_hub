import asyncio
import signal
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# 导入Worker管理器
from .worker_manager import WorkerManager, WorkerConfig
from logging_config import get_logger

logger = get_logger(__name__)

# 全局Worker管理器实例
worker_manager: WorkerManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global worker_manager
    
    # 启动时初始化
    try:
        # 加载配置
        config = load_worker_config()
        worker_manager = WorkerManager(config)
        
        # 启动Worker管理器
        await worker_manager.start()
        logger.info("Worker service started successfully")
        
        # 设置BrowserInstanceManager的WorkerManager引用
        try:
            from login_state.api import browser_manager as global_browser_manager
            if global_browser_manager:
                global_browser_manager.set_worker_manager(worker_manager)
                logger.info("成功设置BrowserInstanceManager的WorkerManager引用")
            else:
                logger.warning("全局BrowserInstanceManager实例未初始化")
        except Exception as e:
            logger.error(f"设置BrowserInstanceManager的WorkerManager引用失败: {e}")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start worker service: {e}")
        raise
    finally:
        # 关闭时清理
        if worker_manager:
            try:
                await worker_manager.stop()
                logger.info("Worker service stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping worker service: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="NewsHub Crawler Worker Service",
    description="异步爬虫Worker服务",
    version="1.0.0",
    lifespan=lifespan
)

def load_worker_config() -> WorkerConfig:
    """加载Worker配置"""
    try:
        # 尝试从配置文件加载
        config_path = Path(__file__).parent.parent / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # 提取Worker相关配置
            worker_config = config_data.get('worker', {})
            
            # 合并Redis配置
            redis_config = config_data.get('redis', {})
            worker_config.update({
                'redis_host': redis_config.get('host', 'localhost'),
                'redis_port': redis_config.get('port', 6379),
                'redis_db': redis_config.get('db', 0),
                'redis_password': redis_config.get('password')
            })
            
            # 合并后端API配置
            backend_config = config_data.get('backend', {})
            worker_config.update({
                'backend_api_url': backend_config.get('api_url', 'http://localhost:8081')
            })
            
            return WorkerConfig(worker_config)
        else:
            logger.warning(f"Config file not found at {config_path}, using default configuration")
            return WorkerConfig()
            
    except Exception as e:
        logger.error(f"Error loading worker config: {e}")
        return WorkerConfig()

@app.get("/")
async def root():
    """根路径"""
    return {"message": "NewsHub Crawler Worker Service", "status": "running"}

@app.get("/health")
async def health_check():
    """健康检查"""
    global worker_manager
    
    if not worker_manager:
        raise HTTPException(status_code=503, detail="Worker manager not initialized")
    
    try:
        health_status = await worker_manager.health_check()
        
        if health_status['health_status'] == 'healthy':
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "data": health_status
                }
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "data": health_status
                }
            )
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/stats")
async def get_stats():
    """获取Worker统计信息"""
    global worker_manager
    
    if not worker_manager:
        raise HTTPException(status_code=503, detail="Worker manager not initialized")
    
    try:
        stats = worker_manager.get_stats()
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": stats
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/workers/restart")
async def restart_workers():
    """重启所有Workers"""
    global worker_manager
    
    if not worker_manager:
        raise HTTPException(status_code=503, detail="Worker manager not initialized")
    
    try:
        logger.info("Restarting all workers...")
        
        # 停止当前Workers
        await worker_manager.stop()
        
        # 重新启动Workers
        await worker_manager.start()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "All workers restarted successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to restart workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart workers: {str(e)}")

@app.get("/workers/{worker_id}/stats")
async def get_worker_stats(worker_id: str):
    """获取特定Worker的统计信息"""
    global worker_manager
    
    if not worker_manager:
        raise HTTPException(status_code=503, detail="Worker manager not initialized")
    
    try:
        if worker_id not in worker_manager.workers:
            raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
        
        worker = worker_manager.workers[worker_id]
        stats = worker.get_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": stats
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker stats: {str(e)}")

@app.post("/api/v1/worker/trigger-immediate-check")
async def trigger_immediate_check():
    """触发Worker立即检查队列并处理任务"""
    global worker_manager
    
    if not worker_manager:
        raise HTTPException(status_code=503, detail="Worker manager not initialized")
    
    try:
        logger.info("Received immediate worker check trigger request")
        
        # 触发所有Worker立即检查队列
        triggered_count = await worker_manager.trigger_immediate_check()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "triggered": True,
                "message": f"Triggered immediate check for {triggered_count} workers",
                "data": {
                    "triggered_workers": triggered_count,
                    "total_workers": len(worker_manager.workers)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger immediate worker check: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "triggered": False,
                "message": f"Failed to trigger immediate check: {str(e)}"
            }
        )

# 信号处理
def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    
    # 创建新的事件循环来处理关闭
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        if worker_manager:
            loop.run_until_complete(worker_manager.stop())
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")
    finally:
        loop.close()
        sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """主函数"""
    try:
        # Windows平台事件循环策略修复
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # 配置uvicorn
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8002,  # Worker服务使用8002端口
            log_level="info",
            reload=False,  # 生产环境禁用reload
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        logger.info("Starting NewsHub Crawler Worker Service on port 8002")
        await server.serve()
        
    except Exception as e:
        logger.error(f"Failed to start worker service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())