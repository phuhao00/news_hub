#!/usr/bin/env python3
"""
持续爬取功能测试脚本
暂时禁用Playwright，只测试持续爬取的核心逻辑
"""

import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import json
from typing import Optional, List

# 导入持续爬取相关模块（不包含Playwright依赖）
from manual_crawl import ContinuousCrawlService
from logging_config import setup_logging, get_logger

# 配置日志
setup_logging()
logger = get_logger(__name__)

# 创建FastAPI应用
app = FastAPI(title="持续爬取测试服务", version="1.0.0")

# 全局变量
continuous_crawl_service = None

class TestCrawlRequest(BaseModel):
    url: str
    interval_seconds: int = 30
    max_crawls: int = 10
    max_duration_minutes: int = 60
    content_change_threshold: float = 0.1

class TestCrawlResponse(BaseModel):
    task_id: str
    message: str
    success: bool

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global continuous_crawl_service
    
    logger.info("启动持续爬取测试服务...")
    
    # 初始化持续爬取服务（不需要数据库连接）
    continuous_crawl_service = ContinuousCrawlService(db=None)
    
    logger.info("持续爬取测试服务启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global continuous_crawl_service
    
    logger.info("关闭持续爬取测试服务...")
    
    if continuous_crawl_service:
        # 停止所有持续爬取任务
        tasks = continuous_crawl_service.list_continuous_tasks()
        for task in tasks:
            if task.get('status') == 'running':
                await continuous_crawl_service.stop_continuous_crawl(task['task_id'])
        
        # 清理已停止的任务
        await continuous_crawl_service.cleanup_stopped_tasks()
    
    logger.info("持续爬取测试服务已关闭")

@app.get("/")
async def root():
    """根路径"""
    return {"message": "持续爬取测试服务运行中", "timestamp": datetime.now()}

@app.post("/test/start_continuous_crawl", response_model=TestCrawlResponse)
async def start_continuous_crawl(request: TestCrawlRequest):
    """启动持续爬取测试"""
    try:
        logger.info(f"启动持续爬取测试: {request.url}")
        
        # 模拟浏览器实例ID
        instance_id = "test_instance_123"
        
        # 启动持续爬取
        task_id = await continuous_crawl_service.start_continuous_crawl(
            url=request.url,
            instance_id=instance_id,
            interval_seconds=request.interval_seconds,
            max_crawls=request.max_crawls,
            max_duration_minutes=request.max_duration_minutes,
            content_change_threshold=request.content_change_threshold
        )
        
        return TestCrawlResponse(
            task_id=task_id,
            message=f"持续爬取任务已启动，任务ID: {task_id}",
            success=True
        )
        
    except Exception as e:
        logger.error(f"启动持续爬取失败: {e}")
        return TestCrawlResponse(
            task_id="",
            message=f"启动失败: {str(e)}",
            success=False
        )

@app.post("/test/stop_continuous_crawl")
async def stop_continuous_crawl(task_id: str):
    """停止持续爬取测试"""
    try:
        logger.info(f"停止持续爬取任务: {task_id}")
        
        success = await continuous_crawl_service.stop_continuous_crawl(task_id)
        
        if success:
            return {"message": f"任务 {task_id} 已停止", "success": True}
        else:
            return {"message": f"任务 {task_id} 停止失败或不存在", "success": False}
            
    except Exception as e:
        logger.error(f"停止持续爬取失败: {e}")
        return {"message": f"停止失败: {str(e)}", "success": False}

@app.get("/test/list_tasks")
async def list_continuous_tasks():
    """列出所有持续爬取任务"""
    try:
        tasks = continuous_crawl_service.list_continuous_tasks()
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return {"error": str(e), "tasks": [], "count