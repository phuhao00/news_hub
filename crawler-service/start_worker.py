#!/usr/bin/env python3
"""
NewsHub 爬虫Worker服务启动脚本

这个脚本用于启动异步爬虫Worker服务，该服务会：
1. 从Go后端获取爬取任务
2. 使用多个Worker并发处理任务
3. 将结果返回给Go后端
4. 提供健康检查和统计信息API
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入Worker服务
from worker.worker_service import main
from logging_config import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting NewsHub Crawler Worker Service...")
        logger.info(f"Project root: {project_root}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # 运行Worker服务
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Worker service interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start worker service: {e}")
        sys.exit(1)