#!/usr/bin/env python3
"""
修复Windows上Playwright NotImplementedError的启动脚本
确保在任何异步操作之前设置正确的事件循环策略
"""

import asyncio
import platform
import sys
import os

# 在导入任何其他模块之前设置Windows事件循环策略
if platform.system() == 'Windows':
    # 设置Windows兼容的事件循环策略
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[INFO] Windows事件循环策略已设置为WindowsProactorEventLoopPolicy")

# 现在可以安全地导入其他模块
import uvicorn
from main import app

def main():
    """主函数"""
    try:
        print("[INFO] 启动NewsHub爬虫服务...")
        print(f"[INFO] 操作系统: {platform.system()}")
        print(f"[INFO] Python版本: {sys.version}")
        print(f"[INFO] 当前事件循环策略: {asyncio.get_event_loop_policy().__class__.__name__}")
        
        # 启动uvicorn服务器
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,  # 禁用reload以避免事件循环冲突
            log_level="info"
        )
        
    except Exception as e:
        print(f"[ERROR] 服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()