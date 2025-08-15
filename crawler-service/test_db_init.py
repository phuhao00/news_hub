#!/usr/bin/env python3
"""
测试数据库初始化功能
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from login_state.database import create_database_manager

async def test_database_initialization():
    """测试数据库初始化功能"""
    try:
        # 连接MongoDB
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client.newshub
        
        print("=== Python爬虫服务数据库初始化测试 ===")
        print("正在连接MongoDB...")
        
        # 测试连接
        await client.admin.command('ping')
        print("✓ MongoDB连接成功")
        
        # 创建数据库管理器并初始化
        print("正在初始化数据库...")
        manager = await create_database_manager(db)
        print("✓ 数据库初始化完成")
        
        # 执行健康检查
        print("正在执行健康检查...")
        health_status = await manager.health_check()
        
        print("\n=== 健康检查结果 ===")
        for check, status in health_status.items():
            status_str = "✓" if status else "✗"
            print(f"  {status_str} {check}: {'正常' if status else '异常'}")
        
        # 显示collection状态
        print("\n=== Collection状态 ===")
        for collection_name in manager.collections.keys():
            try:
                count = await manager.collections[collection_name].count_documents({})
                print(f"  {collection_name}: {count} 条记录")
            except Exception as e:
                print(f"  {collection_name}: 获取数量失败 ({e})")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"✗ 数据库初始化测试失败: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = asyncio.run(test_database_initialization())
    sys.exit(0 if success else 1)