#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能爬取系统集成测试脚本
测试核心功能：任务创建、状态查询、数据提取、质量评估等
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List
from datetime import datetime

class IntelligentCrawlTester:
    def __init__(self):
        self.go_api_base = "http://localhost:8081/api/v1"
        self.python_api_base = "http://localhost:8001/api/v1"
        self.test_results = []
        
    async def test_go_backend_health(self) -> bool:
        """测试Go后端健康状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.go_api_base}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Go后端健康检查通过: {data}")
                        return True
                    else:
                        print(f"❌ Go后端健康检查失败: {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Go后端连接失败: {e}")
            return False
    
    async def test_python_crawler_health(self) -> bool:
        """测试Python爬虫服务健康状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.python_api_base}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Python爬虫服务健康检查通过: {data}")
                        return True
                    else:
                        print(f"❌ Python爬虫服务健康检查失败: {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Python爬虫服务连接失败: {e}")
            return False
    
    async def test_create_crawl_task(self) -> str:
        """测试创建爬取任务"""
        test_url = "https://weibo.com/u/1234567890"
        task_data = {
            "url": test_url,
            "platform": "weibo",
            "priority": "high",
            "options": {
                "extract_images": True,
                "extract_videos": False,
                "use_screenshot": True,
                "quality_threshold": 0.8
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.go_api_base}/tasks",
                    json=task_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 201:
                        data = await response.json()
                        task_id = data.get("task_id")
                        print(f"✅ 任务创建成功: {task_id}")
                        return task_id
                    else:
                        error_text = await response.text()
                        print(f"❌ 任务创建失败: {response.status} - {error_text}")
                        return None
        except Exception as e:
            print(f"❌ 任务创建异常: {e}")
            return None
    
    async def test_task_status(self, task_id: str) -> Dict[str, Any]:
        """测试任务状态查询"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.go_api_base}/tasks/{task_id}") as response:
                    if response.status == 200:
                        data = await response.json()
                        status = data.get("status", "unknown")
                        print(f"✅ 任务状态查询成功: {status}")
                        return data
                    else:
                        print(f"❌ 任务状态查询失败: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ 任务状态查询异常: {e}")
            return None
    
    async def test_task_list(self) -> List[Dict[str, Any]]:
        """测试任务列表查询"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.go_api_base}/tasks") as response:
                    if response.status == 200:
                        data = await response.json()
                        tasks = data.get("tasks", [])
                        print(f"✅ 任务列表查询成功: 共{len(tasks)}个任务")
                        return tasks
                    else:
                        print(f"❌ 任务列表查询失败: {response.status}")
                        return []
        except Exception as e:
            print(f"❌ 任务列表查询异常: {e}")
            return []
    
    async def test_worker_status(self) -> Dict[str, Any]:
        """测试Worker状态查询"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.python_api_base}/workers/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Worker状态查询成功: {data}")
                        return data
                    else:
                        print(f"❌ Worker状态查询失败: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Worker状态查询异常: {e}")
            return None
    
    async def test_queue_status(self) -> Dict[str, Any]:
        """测试队列状态查询"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.python_api_base}/queue/status") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 队列状态查询成功: {data}")
                        return data
                    else:
                        print(f"❌ 队列状态查询失败: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ 队列状态查询异常: {e}")
            return None
    
    async def wait_for_task_completion(self, task_id: str, timeout: int = 60) -> bool:
        """等待任务完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            task_data = await self.test_task_status(task_id)
            if task_data:
                status = task_data.get("status")
                if status in ["completed", "failed"]:
                    print(f"✅ 任务{task_id}已完成，状态: {status}")
                    return status == "completed"
            await asyncio.sleep(2)
        
        print(f"❌ 任务{task_id}等待超时")
        return False
    
    async def run_comprehensive_test(self):
        """运行综合测试"""
        print("\n=== 智能爬取系统集成测试开始 ===")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 健康检查
        print("\n[1/7] 服务健康检查...")
        go_health = await self.test_go_backend_health()
        python_health = await self.test_python_crawler_health()
        
        if not go_health or not python_health:
            print("❌ 服务健康检查失败，终止测试")
            return
        
        # 2. Worker和队列状态
        print("\n[2/7] Worker和队列状态检查...")
        await self.test_worker_status()
        await self.test_queue_status()
        
        # 3. 任务列表查询
        print("\n[3/7] 任务列表查询...")
        initial_tasks = await self.test_task_list()
        
        # 4. 创建测试任务
        print("\n[4/7] 创建测试任务...")
        task_id = await self.test_create_crawl_task()
        
        if not task_id:
            print("❌ 任务创建失败，终止测试")
            return
        
        # 5. 任务状态监控
        print("\n[5/7] 任务状态监控...")
        await asyncio.sleep(2)  # 等待任务开始处理
        task_completed = await self.wait_for_task_completion(task_id, timeout=30)
        
        # 6. 最终状态检查
        print("\n[6/7] 最终状态检查...")
        final_task_data = await self.test_task_status(task_id)
        final_tasks = await self.test_task_list()
        
        # 7. 测试结果汇总
        print("\n[7/7] 测试结果汇总...")
        self.print_test_summary({
            "go_health": go_health,
            "python_health": python_health,
            "task_created": bool(task_id),
            "task_completed": task_completed,
            "initial_task_count": len(initial_tasks),
            "final_task_count": len(final_tasks),
            "final_task_data": final_task_data
        })
    
    def print_test_summary(self, results: Dict[str, Any]):
        """打印测试结果汇总"""
        print("\n=== 测试结果汇总 ===")
        print(f"Go后端健康: {'✅' if results['go_health'] else '❌'}")
        print(f"Python爬虫服务健康: {'✅' if results['python_health'] else '❌'}")
        print(f"任务创建: {'✅' if results['task_created'] else '❌'}")
        print(f"任务完成: {'✅' if results['task_completed'] else '❌'}")
        print(f"任务数量变化: {results['initial_task_count']} -> {results['final_task_count']}")
        
        if results['final_task_data']:
            task_data = results['final_task_data']
            print(f"\n最终任务详情:")
            print(f"  状态: {task_data.get('status')}")
            print(f"  URL: {task_data.get('url')}")
            print(f"  平台: {task_data.get('platform')}")
            print(f"  创建时间: {task_data.get('created_at')}")
            print(f"  更新时间: {task_data.get('updated_at')}")
            
            if task_data.get('result'):
                result = task_data['result']
                print(f"  提取内容长度: {len(result.get('content', ''))}")
                print(f"  质量评分: {result.get('quality_score', 'N/A')}")
                print(f"  提取方法: {result.get('extraction_method', 'N/A')}")
        
        # 总体评估
        success_count = sum([
            results['go_health'],
            results['python_health'], 
            results['task_created'],
            results['task_completed']
        ])
        
        print(f"\n总体测试结果: {success_count}/4 项通过")
        if success_count >= 3:
            print("🎉 智能爬取系统集成测试基本通过！")
        else:
            print("⚠️ 智能爬取系统存在问题，需要进一步调试")

async def main():
    """主函数"""
    tester = IntelligentCrawlTester()
    await tester.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())