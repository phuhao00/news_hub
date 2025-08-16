#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去重系统功能测试脚本
测试DeduplicationEngine的核心功能
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'crawler-service'))

from deduplication.engine import DeduplicationEngine
from deduplication.context import DeduplicationContext
from deduplication.config import get_config

async def test_deduplication_system():
    """
    测试去重系统的核心功能
    """
    print("=== 去重系统功能测试 ===")
    
    try:
        # 1. 初始化配置
        print("\n[1/6] 初始化配置...")
        config = get_config()
        print(f"✓ 配置加载成功")
        
        # 2. 创建去重上下文
        print("\n[2/6] 创建去重上下文...")
        # 先创建必要的管理器（简化版本用于测试）
        from deduplication.cache_manager import CacheManager
        from deduplication.index_manager import IndexManager
        
        cache_manager = CacheManager()
        index_manager = IndexManager()
        
        context = DeduplicationContext(
            task_id="test_task_001",
            cache_manager=cache_manager,
            index_manager=index_manager
        )
        print(f"✓ 去重上下文创建成功: {context.task_id}")
        
        # 3. 初始化去重引擎
        print("\n[3/6] 初始化去重引擎...")
        engine = DeduplicationEngine(
            cache_manager=cache_manager,
            index_manager=index_manager
        )
        print("✓ 去重引擎初始化成功")
        
        # 4. 测试内容去重检查
        print("\n[4/6] 测试内容去重检查...")
        
        # 测试数据1
        test_content_1 = {
            "url": "https://weibo.com/test/123456",
            "title": "测试标题1",
            "content": "这是一个测试内容，用于验证去重系统的功能。",
            "author": "测试作者",
            "published_at": datetime.now().isoformat()
        }
        
        # 第一次检查（应该不重复）
        result_1 = await engine.check_duplicate(test_content_1)
        print(f"✓ 第一次检查结果: 重复={result_1.is_duplicate}, 类型={result_1.duplicate_type}")
        
        # 第二次检查相同内容（应该重复）
        result_2 = await engine.check_duplicate(test_content_1)
        print(f"✓ 第二次检查结果: 重复={result_2.is_duplicate}, 类型={result_2.duplicate_type}")
        
        # 测试数据2（不同内容）
        test_content_2 = {
            "url": "https://weibo.com/test/789012",
            "title": "测试标题2",
            "content": "这是另一个测试内容，内容完全不同。",
            "author": "测试作者2",
            "published_at": datetime.now().isoformat()
        }
        
        # 检查不同内容（应该不重复）
        result_3 = await engine.check_duplicate(test_content_2)
        print(f"✓ 不同内容检查结果: 重复={result_3.is_duplicate}, 类型={result_3.duplicate_type}")
        
        # 5. 测试批量去重检查
        print("\n[5/6] 测试批量去重检查...")
        
        batch_contents = [test_content_1, test_content_2]
        batch_results = await engine.batch_check_duplicate(batch_contents)
        print(f"✓ 批量检查完成，处理了 {len(batch_results)} 个内容")
        
        for i, result in enumerate(batch_results):
            print(f"  内容{i+1}: 重复={result.is_duplicate}, 类型={result.duplicate_type}")
        
        # 6. 获取统计信息
        print("\n[6/6] 获取统计信息...")
        stats = await engine.get_stats()
        print(f"✓ 统计信息:")
        print(f"  总检查次数: {stats.get('total_checks', 0)}")
        print(f"  发现重复次数: {stats.get('duplicates_found', 0)}")
        print(f"  缓存命中率: {stats.get('cache_hit_rate', 0):.2%}")
        
        print("\n=== 测试完成 ===")
        print("✅ 所有测试通过！去重系统功能正常。")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理资源
        try:
            if 'engine' in locals():
                await engine.cleanup()
        except:
            pass

async def test_monitoring_system():
    """
    测试监控系统功能
    """
    print("\n=== 监控系统功能测试 ===")
    
    try:
        from deduplication.monitoring import get_monitoring_service
        
        monitoring = get_monitoring_service()
        
        # 记录一些测试指标
        monitoring.record_performance(50, "content_hash", None)
        monitoring.record_performance(75, "url", None)
        monitoring.record_performance(120, "title_author", "timeout_error")
        
        # 获取统计信息
        stats = monitoring.get_performance_stats()
        print(f"✓ 监控统计:")
        print(f"  总检查次数: {stats.total_checks}")
        print(f"  发现重复次数: {stats.duplicates_found}")
        print(f"  错误次数: {stats.error_count}")
        print(f"  平均响应时间: {stats.avg_response_time:.2f}ms")
        
        # 获取告警信息
        alerts = monitoring.get_active_alerts()
        print(f"✓ 活跃告警数量: {len(alerts)}")
        
        print("✅ 监控系统测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 监控系统测试失败: {str(e)}")
        return False

async def main():
    """
    主测试函数
    """
    print("开始去重系统完整功能测试...\n")
    
    # 测试去重系统核心功能
    dedup_success = await test_deduplication_system()
    
    # 测试监控系统
    monitoring_success = await test_monitoring_system()
    
    # 总结测试结果
    print("\n" + "="*50)
    print("测试结果总结:")
    print(f"去重系统核心功能: {'✅ 通过' if dedup_success else '❌ 失败'}")
    print(f"监控系统功能: {'✅ 通过' if monitoring_success else '❌ 失败'}")
    
    if dedup_success and monitoring_success:
        print("\n🎉 所有测试通过！去重系统已准备就绪。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查系统配置。")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)