#!/usr/bin/env python3
"""
爬虫测试脚本 - 验证真实爬取功能
更新版本：增强测试覆盖度和错误处理
"""

import asyncio
import sys
import os
import time
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(__file__))

from main import UnifiedCrawlerService, PlatformCrawlRequest

class CrawlerTester:
    """爬虫测试器"""
    
    def __init__(self):
        self.crawler = None
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
    
    async def setup(self):
        """设置测试环境"""
        print("🔧 初始化爬虫测试环境...")
        self.crawler = UnifiedCrawlerService()
        await self.crawler.initialize()
        print("✅ 爬虫服务初始化完成")
    
    async def cleanup(self):
        """清理测试环境"""
        if self.crawler:
            await self.crawler.cleanup()
        print("🧹 测试环境清理完成")
    
    def log_test_result(self, test_name: str, success: bool, duration: float, posts_count: int = 0, error: str = None):
        """记录测试结果"""
        self.total_tests += 1
        if success:
            self.passed_tests += 1
            status = "✅ PASS"
        else:
            self.failed_tests += 1
            status = "❌ FAIL"
        
        self.test_results[test_name] = {
            'success': success,
            'duration': duration,
            'posts_count': posts_count,
            'error': error
        }
        
        print(f"{status} {test_name} ({duration:.2f}s, {posts_count} posts)")
        if error:
            print(f"    Error: {error}")
    
    async def test_platform(self, platform: str, query: str, limit: int = 3):
        """测试单个平台爬虫"""
        test_name = f"{platform.upper()}_{query}"
        start_time = time.time()
        
        try:
            request = PlatformCrawlRequest(
                creator_url=query,
                platform=platform,
                limit=limit
            )
            
            posts = await self.crawler.crawl_platform_posts(request)
            duration = time.time() - start_time
            
            if posts and len(posts) > 0:
                # 验证数据质量
                valid_posts = 0
                for post in posts:
                    if (post.title and len(post.title) > 5 and 
                        post.content and len(post.content) > 10 and
                        post.author and post.platform == platform):
                        valid_posts += 1
                
                success = valid_posts > 0
                self.log_test_result(test_name, success, duration, len(posts))
                
                if success:
                    # 显示第一个帖子的详细信息
                    first_post = posts[0]
                    print(f"    示例: {first_post.title[:50]}...")
                    print(f"    作者: {first_post.author}")
                    print(f"    标签: {', '.join(first_post.tags[:3])}")
                
            else:
                self.log_test_result(test_name, False, duration, 0, "未获取到任何内容")
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, duration, 0, str(e))
    
    async def test_news_crawler(self, query: str, limit: int = 3):
        """测试新闻爬虫"""
        test_name = f"NEWS_{query}"
        start_time = time.time()
        
        try:
            posts = await self.crawler.search_and_crawl_news(query, limit)
            duration = time.time() - start_time
            
            if posts and len(posts) > 0:
                # 验证新闻质量
                valid_news = 0
                for post in posts:
                    if (post.title and len(post.title) > 10 and 
                        post.content and len(post.content) > 20 and
                        '新闻' in post.tags):
                        valid_news += 1
                
                success = valid_news > 0
                self.log_test_result(test_name, success, duration, len(posts))
                
                if success:
                    first_post = posts[0]
                    print(f"    新闻: {first_post.title[:60]}...")
                    print(f"    来源: {first_post.author}")
                
            else:
                self.log_test_result(test_name, False, duration, 0, "未获取到新闻内容")
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result(test_name, False, duration, 0, str(e))
    
    async def test_search_functionality(self):
        """测试搜索功能"""
        print("\n🔍 测试搜索引擎爬取功能...")
        print("-" * 60)
        
        search_test_cases = [
            {"platform": "weibo", "query": "人工智能", "limit": 3},
            {"platform": "weibo", "query": "科技新闻", "limit": 2},
            {"platform": "douyin", "query": "编程教程", "limit": 2},
            {"platform": "xiaohongshu", "query": "美食推荐", "limit": 2},
            {"platform": "bilibili", "query": "学习方法", "limit": 2},
        ]
        
        for test_case in search_test_cases:
            await self.test_platform(
                test_case['platform'], 
                test_case['query'], 
                test_case['limit']
            )
            await asyncio.sleep(1)  # 避免请求过快
    
    async def test_news_functionality(self):
        """测试新闻爬取功能"""
        print("\n📰 测试新闻爬取功能...")
        print("-" * 60)
        
        news_test_cases = [
            {"query": "人工智能", "limit": 3},
            {"query": "科技发展", "limit": 2},
            {"query": "经济新闻", "limit": 2},
        ]
        
        for test_case in news_test_cases:
            await self.test_news_crawler(test_case['query'], test_case['limit'])
            await asyncio.sleep(1)
    
    async def test_performance(self):
        """性能测试"""
        print("\n⚡ 性能测试...")
        print("-" * 60)
        
        start_time = time.time()
        
        # 并发测试
        tasks = []
        concurrent_requests = [
            {"platform": "weibo", "query": "热门话题", "limit": 2},
            {"platform": "douyin", "query": "短视频", "limit": 2},
            {"platform": "news", "query": "最新消息", "limit": 2},
        ]
        
        for req in concurrent_requests:
            if req["platform"] == "news":
                task = asyncio.create_task(self.test_news_crawler(req["query"], req["limit"]))
            else:
                task = asyncio.create_task(self.test_platform(req["platform"], req["query"], req["limit"]))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_duration = time.time() - start_time
        print(f"🏃‍♂️ 并发测试完成，总耗时: {total_duration:.2f}秒")
    
    async def test_edge_cases(self):
        """边界情况测试"""
        print("\n🧪 边界情况测试...")
        print("-" * 60)
        
        edge_cases = [
            {"platform": "weibo", "query": "", "limit": 1},  # 空查询
            {"platform": "douyin", "query": "不存在的内容xyzabc123", "limit": 1},  # 无结果查询
            {"platform": "bilibili", "query": "测试", "limit": 0},  # 零限制
        ]
        
        for case in edge_cases:
            await self.test_platform(case['platform'], case['query'], case['limit'])
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("📊 测试摘要报告")
        print("=" * 80)
        
        print(f"总测试数: {self.total_tests}")
        print(f"通过测试: {self.passed_tests}")
        print(f"失败测试: {self.failed_tests}")
        print(f"成功率: {(self.passed_tests / self.total_tests * 100):.1f}%")
        
        print("\n📈 详细结果:")
        for test_name, result in self.test_results.items():
            status = "✅" if result['success'] else "❌"
            print(f"{status} {test_name}: {result['duration']:.2f}s, {result['posts_count']} posts")
        
        # 性能统计
        total_duration = sum(r['duration'] for r in self.test_results.values())
        total_posts = sum(r['posts_count'] for r in self.test_results.values())
        avg_duration = total_duration / len(self.test_results) if self.test_results else 0
        
        print(f"\n⏱️  性能统计:")
        print(f"总耗时: {total_duration:.2f}秒")
        print(f"平均耗时: {avg_duration:.2f}秒/测试")
        print(f"总爬取数: {total_posts} 条")
        print(f"爬取效率: {total_posts/total_duration:.1f} 条/秒" if total_duration > 0 else "N/A")
        
        if self.failed_tests > 0:
            print(f"\n⚠️  {self.failed_tests} 个测试失败，请检查网络连接和爬虫实现")
        else:
            print(f"\n🎉 所有测试通过！爬虫系统运行正常")

async def main():
    """主测试函数"""
    print("=" * 80)
    print("          NewsHub 增强爬虫系统测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = CrawlerTester()
    
    try:
        await tester.setup()
        
        # 执行所有测试
        await tester.test_search_functionality()
        await tester.test_news_functionality()
        await tester.test_performance()
        await tester.test_edge_cases()
        
    except Exception as e:
        print(f"❌ 测试过程中发生严重错误: {e}")
    finally:
        await tester.cleanup()
        tester.print_summary()

if __name__ == "__main__":
    print("🚀 启动爬虫系统测试...")
    asyncio.run(main()) 