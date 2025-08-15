#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取系统诊断脚本
用于排查"没有爬到任何数据，也没有报错"的问题
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import aiohttp
import pymongo
from pymongo import MongoClient
from bson import ObjectId

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('diagnose_crawl_system.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class CrawlSystemDiagnostic:
    """爬取系统诊断器"""
    
    def __init__(self):
        self.config = self._load_config()
        self.mongo_client = None
        self.db = None
        self.issues = []
        self.recommendations = []
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {
                "mongodb": {
                    "host": "localhost",
                    "port": 27017,
                    "database": "newshub"
                },
                "crawler_service": {
                    "host": "localhost",
                    "port": 8001
                },
                "backend_service": {
                    "host": "localhost",
                    "port": 8081
                }
            }
    
    async def run_diagnosis(self):
        """运行完整诊断"""
        logger.info("=" * 60)
        logger.info("开始爬取系统诊断")
        logger.info("=" * 60)
        
        # 1. 检查数据库连接
        await self._check_database_connection()
        
        # 2. 检查数据库集合状态
        await self._check_database_collections()
        
        # 3. 检查爬虫服务状态
        await self._check_crawler_service()
        
        # 4. 检查后端服务状态
        await self._check_backend_service()
        
        # 5. 检查任务执行状态
        await self._check_task_execution()
        
        # 6. 测试创建爬取任务
        await self._test_create_crawl_task()
        
        # 7. 检查Worker线程状态
        await self._check_worker_status()
        
        # 8. 检查MCP服务状态
        await self._check_mcp_service()
        
        # 9. 生成诊断报告
        self._generate_diagnosis_report()
        
        # 清理资源
        if self.mongo_client:
            self.mongo_client.close()
    
    async def _check_database_connection(self):
        """检查数据库连接"""
        logger.info("\n1. 检查数据库连接...")
        try:
            mongo_config = self.config.get('mongodb', {})
            connection_string = f"mongodb://{mongo_config.get('host', 'localhost')}:{mongo_config.get('port', 27017)}"
            
            self.mongo_client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            
            # 测试连接
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client[mongo_config.get('database', 'newshub')]
            
            logger.info("✅ 数据库连接正常")
            logger.info(f"   连接字符串: {connection_string}")
            logger.info(f"   数据库名称: {mongo_config.get('database', 'newshub')}")
            
        except Exception as e:
            error_msg = f"❌ 数据库连接失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
            self.recommendations.append("检查MongoDB服务是否启动，端口是否正确")
    
    async def _check_database_collections(self):
        """检查数据库集合状态"""
        logger.info("\n2. 检查数据库集合状态...")
        
        if self.db is None:
            logger.error("❌ 数据库未连接，跳过集合检查")
            return
        
        try:
            collections = self.db.list_collection_names()
            logger.info(f"   现有集合: {collections}")
            
            # 检查关键集合
            key_collections = ['crawl_tasks', 'continuous_tasks', 'platform_configs']
            for collection_name in key_collections:
                if collection_name in collections:
                    count = self.db[collection_name].count_documents({})
                    logger.info(f"✅ {collection_name}: {count} 条记录")
                    
                    # 显示最近的记录
                    if count > 0:
                        recent_docs = list(self.db[collection_name].find().sort('_id', -1).limit(3))
                        for i, doc in enumerate(recent_docs):
                            doc_id = str(doc.get('_id', 'N/A'))
                            status = doc.get('status', 'N/A')
                            created_at = doc.get('created_at', 'N/A')
                            logger.info(f"     记录{i+1}: ID={doc_id[:8]}..., Status={status}, Created={created_at}")
                else:
                    logger.warning(f"⚠️  {collection_name}: 集合不存在")
                    self.issues.append(f"集合 {collection_name} 不存在")
            
        except Exception as e:
            error_msg = f"❌ 检查数据库集合失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _check_crawler_service(self):
        """检查爬虫服务状态"""
        logger.info("\n3. 检查爬虫服务状态...")
        
        try:
            crawler_config = self.config.get('crawler_service', {})
            base_url = f"http://{crawler_config.get('host', 'localhost')}:{crawler_config.get('port', 8001)}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # 检查健康状态
                try:
                    async with session.get(f"{base_url}/health") as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"✅ 爬虫服务健康检查通过")
                            logger.info(f"   服务地址: {base_url}")
                            logger.info(f"   响应数据: {data}")
                        else:
                            logger.warning(f"⚠️  爬虫服务健康检查异常: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"❌ 爬虫服务健康检查失败: {e}")
                    self.issues.append(f"爬虫服务不可访问: {e}")
                    self.recommendations.append("检查爬虫服务是否启动，端口8001是否可用")
                
                # 检查API端点
                endpoints = ["/docs", "/api/login-state/crawl", "/status"]
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{base_url}{endpoint}") as response:
                            logger.info(f"   {endpoint}: HTTP {response.status}")
                    except Exception as e:
                        logger.warning(f"   {endpoint}: 访问失败 - {e}")
                        
        except Exception as e:
            error_msg = f"❌ 检查爬虫服务失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _check_backend_service(self):
        """检查后端服务状态"""
        logger.info("\n4. 检查后端服务状态...")
        
        try:
            backend_config = self.config.get('backend_service', {})
            base_url = f"http://{backend_config.get('host', 'localhost')}:{backend_config.get('port', 8081)}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # 检查健康状态
                try:
                    async with session.get(f"{base_url}/health") as response:
                        if response.status == 200:
                            logger.info(f"✅ 后端服务健康检查通过")
                            logger.info(f"   服务地址: {base_url}")
                        else:
                            logger.warning(f"⚠️  后端服务健康检查异常: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"❌ 后端服务健康检查失败: {e}")
                    self.issues.append(f"后端服务不可访问: {e}")
                    self.recommendations.append("检查后端服务是否启动，端口8081是否可用")
                
                # 检查API端点
                endpoints = ["/api/tasks", "/api/platforms"]
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{base_url}{endpoint}") as response:
                            logger.info(f"   {endpoint}: HTTP {response.status}")
                            if response.status == 200:
                                data = await response.json()
                                if isinstance(data, list):
                                    logger.info(f"     返回 {len(data)} 条记录")
                    except Exception as e:
                        logger.warning(f"   {endpoint}: 访问失败 - {e}")
                        
        except Exception as e:
            error_msg = f"❌ 检查后端服务失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _check_task_execution(self):
        """检查任务执行状态"""
        logger.info("\n5. 检查任务执行状态...")
        
        if self.db is None:
            logger.error("❌ 数据库未连接，跳过任务执行检查")
            return
        
        try:
            # 检查最近24小时的任务
            yesterday = datetime.now() - timedelta(days=1)
            
            # 检查爬取任务
            crawl_tasks = self.db.crawl_tasks
            recent_tasks = list(crawl_tasks.find({
                'created_at': {'$gte': yesterday.isoformat()}
            }).sort('created_at', -1).limit(10))
            
            logger.info(f"   最近24小时爬取任务: {len(recent_tasks)} 个")
            
            if recent_tasks:
                status_count = {}
                for task in recent_tasks:
                    status = task.get('status', 'unknown')
                    status_count[status] = status_count.get(status, 0) + 1
                    
                    # 显示任务详情
                    task_id = str(task.get('_id', 'N/A'))[:8]
                    url = task.get('url', 'N/A')
                    created_at = task.get('created_at', 'N/A')
                    logger.info(f"     任务 {task_id}: {status} - {url} ({created_at})")
                
                logger.info(f"   任务状态统计: {status_count}")
                
                # 检查是否有卡住的任务
                stuck_tasks = list(crawl_tasks.find({
                    'status': 'processing',
                    'created_at': {'$lt': (datetime.now() - timedelta(hours=1)).isoformat()}
                }))
                
                if stuck_tasks:
                    logger.warning(f"⚠️  发现 {len(stuck_tasks)} 个可能卡住的任务（处理中超过1小时）")
                    self.issues.append(f"有 {len(stuck_tasks)} 个任务可能卡住")
                    self.recommendations.append("检查Worker线程是否正常工作，考虑重启爬虫服务")
            else:
                logger.warning("⚠️  最近24小时没有爬取任务")
                self.issues.append("最近24小时没有创建爬取任务")
                self.recommendations.append("检查MCP服务是否正常触发爬取任务")
            
            # 检查持续爬取任务
            continuous_tasks = self.db.continuous_tasks
            active_continuous = list(continuous_tasks.find({'status': 'active'}))
            logger.info(f"   活跃的持续爬取任务: {len(active_continuous)} 个")
            
            for task in active_continuous:
                task_id = str(task.get('_id', 'N/A'))[:8]
                platform = task.get('platform', 'N/A')
                last_crawl = task.get('last_crawl_time', 'N/A')
                logger.info(f"     持续任务 {task_id}: {platform} - 最后爬取: {last_crawl}")
                
        except Exception as e:
            error_msg = f"❌ 检查任务执行状态失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _test_create_crawl_task(self):
        """测试创建爬取任务"""
        logger.info("\n6. 测试创建爬取任务...")
        
        try:
            crawler_config = self.config.get('crawler_service', {})
            base_url = f"http://{crawler_config.get('host', 'localhost')}:{crawler_config.get('port', 8001)}"
            
            # 测试URL
            test_url = "https://weibo.com/u/1234567890"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                payload = {
                    "session_id": "test-session",
                    "url": test_url,
                    "extract_content": True,
                    "extract_links": True,
                    "wait_time": 3
                }
                
                headers = {"X-User-ID": "test-user"}
                
                try:
                    async with session.post(f"{base_url}/api/login-state/crawl/create", json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            task_id = data.get('task_id')
                            logger.info(f"✅ 测试任务创建成功")
                            logger.info(f"   任务ID: {task_id}")
                            logger.info(f"   测试URL: {test_url}")
                            
                            # 等待一段时间后检查任务状态
                            await asyncio.sleep(5)
                            
                            async with session.get(f"{base_url}/api/login-state/crawl/{task_id}") as status_response:
                                if status_response.status == 200:
                                    status_data = await status_response.json()
                                    logger.info(f"   任务状态: {status_data.get('status')}")
                                    logger.info(f"   任务详情: {status_data}")
                                else:
                                    logger.warning(f"⚠️  获取任务状态失败: HTTP {status_response.status}")
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ 测试任务创建失败: HTTP {response.status}")
                            logger.error(f"   错误信息: {error_text}")
                            self.issues.append(f"无法创建测试任务: HTTP {response.status}")
                            
                except Exception as e:
                    logger.error(f"❌ 测试任务创建请求失败: {e}")
                    self.issues.append(f"测试任务创建请求失败: {e}")
                    
        except Exception as e:
            error_msg = f"❌ 测试创建爬取任务失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _check_worker_status(self):
        """检查Worker线程状态"""
        logger.info("\n7. 检查Worker线程状态...")
        
        try:
            crawler_config = self.config.get('crawler_service', {})
            base_url = f"http://{crawler_config.get('host', 'localhost')}:{crawler_config.get('port', 8001)}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                try:
                    async with session.get(f"{base_url}/status") as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"✅ 爬虫服务状态获取成功")
                            logger.info(f"   活跃Worker数量: {data.get('active_workers', 0)}")
                            logger.info(f"   队列中任务数量: {data.get('queue_size', 0)}")
                            logger.info(f"   服务详情: {data}")
                            
                            if data.get('active_workers', 0) == 0:
                                logger.warning("⚠️  没有活跃的Worker线程")
                                self.issues.append("没有活跃的Worker线程")
                                self.recommendations.append("检查Worker管理器是否正常启动")
                        else:
                            logger.warning(f"⚠️  获取爬虫服务状态失败: HTTP {response.status}")
                            self.issues.append(f"无法获取爬虫服务状态: HTTP {response.status}")
                            
                except Exception as e:
                    logger.error(f"❌ 检查爬虫服务状态失败: {e}")
                    self.issues.append(f"爬虫服务状态检查失败: {e}")
                    self.recommendations.append("检查爬虫服务的Worker管理模块")
                    
        except Exception as e:
            error_msg = f"❌ 检查Worker线程状态失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    async def _check_mcp_service(self):
        """检查MCP服务状态"""
        logger.info("\n8. 检查MCP服务状态...")
        
        try:
            # 检查MCP服务端口（通常是不同的端口）
            mcp_ports = [8002, 8003]  # 假设的MCP服务端口
            
            for port in mcp_ports:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                        async with session.get(f"http://localhost:{port}/health") as response:
                            if response.status == 200:
                                logger.info(f"✅ MCP服务 (端口{port}) 运行正常")
                            else:
                                logger.warning(f"⚠️  MCP服务 (端口{port}) 响应异常: HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"⚠️  MCP服务 (端口{port}) 不可访问: {e}")
            
            # 检查MCP相关的数据库记录
            if self.db is not None:
                # 检查是否有MCP触发的任务
                mcp_tasks = list(self.db.crawl_tasks.find({
                    'source': 'mcp',
                    'created_at': {'$gte': (datetime.now() - timedelta(hours=24)).isoformat()}
                }).limit(5))
                
                logger.info(f"   最近24小时MCP触发的任务: {len(mcp_tasks)} 个")
                
                if len(mcp_tasks) == 0:
                    logger.warning("⚠️  最近24小时没有MCP触发的任务")
                    self.issues.append("MCP服务可能没有正常触发爬取任务")
                    self.recommendations.append("检查MCP浏览器集成和页面导航监听")
                    
        except Exception as e:
            error_msg = f"❌ 检查MCP服务状态失败: {e}"
            logger.error(error_msg)
            self.issues.append(error_msg)
    
    def _generate_diagnosis_report(self):
        """生成诊断报告"""
        logger.info("\n" + "=" * 60)
        logger.info("诊断报告")
        logger.info("=" * 60)
        
        if not self.issues:
            logger.info("🎉 恭喜！没有发现明显问题")
            logger.info("\n可能的原因：")
            logger.info("1. 系统刚启动，还没有触发爬取任务")
            logger.info("2. MCP浏览器没有访问目标网站")
            logger.info("3. 爬取任务正在队列中等待处理")
            logger.info("\n建议操作：")
            logger.info("1. 使用MCP浏览器访问微博、小红书等目标网站")
            logger.info("2. 点击具体的内容页面触发爬取")
            logger.info("3. 等待几分钟后检查数据库中的任务记录")
        else:
            logger.error(f"\n❌ 发现 {len(self.issues)} 个问题：")
            for i, issue in enumerate(self.issues, 1):
                logger.error(f"{i}. {issue}")
            
            logger.info(f"\n💡 建议解决方案：")
            for i, recommendation in enumerate(self.recommendations, 1):
                logger.info(f"{i}. {recommendation}")
        
        logger.info("\n" + "=" * 60)
        logger.info("诊断完成")
        logger.info("=" * 60)
        
        # 保存诊断结果到文件
        report = {
            "timestamp": datetime.now().isoformat(),
            "issues": self.issues,
            "recommendations": self.recommendations,
            "status": "healthy" if not self.issues else "issues_found"
        }
        
        try:
            with open('diagnosis_report.json', 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info("📄 诊断报告已保存到 diagnosis_report.json")
        except Exception as e:
            logger.error(f"保存诊断报告失败: {e}")

async def main():
    """主函数"""
    diagnostic = CrawlSystemDiagnostic()
    await diagnostic.run_diagnosis()

if __name__ == "__main__":
    asyncio.run(main())