#!/usr/bin/env python3
"""
启动脚本 - NewsHub Crawler Service
"""

import asyncio
import uvicorn
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def main():
    """启动爬虫服务"""
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting NewsHub Crawler Service on {host}:{port}")
    print(f"📖 API Documentation: http://{host}:{port}/docs")
    print(f"🔍 Health Check: http://{host}:{port}/health")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()