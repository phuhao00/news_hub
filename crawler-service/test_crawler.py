#!/usr/bin/env python3
"""
爬虫测试脚本 - 验证真实爬取功能
"""

import asyncio
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(__file__))

from main import UnifiedCrawlerService, PlatformCrawlRequest

async def test_crawler():
    """测试爬虫功能"""
    print("🧪 开始测试真实爬取功能...")
    
    crawler = UnifiedCrawlerService()
    await crawler.initialize()
    
    # 测试案例
    test_cases = [
        {"platform": "news", "query": "人工智能", "limit": 3},
        {"platform": "weibo", "query": "科技新闻", "limit": 3},
        {"platform": "bilibili", "query": "编程教程", "limit": 2},
        {"platform": "xiaohongshu", "query": "美食推荐", "limit": 2},
        {"platform": "douyin", "query": "旅游攻略", "limit": 2},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}/{len(test_cases)}: {test_case['platform']} - {test_case['query']}")
        print("-" * 60)
        
        try:
            request = PlatformCrawlRequest(
                creator_url=test_case['query'],
                platform=test_case['platform'],
                limit=test_case['limit']
            )
            
            posts = await crawler.crawl_platform_posts(request)
            
            if posts:
                print(f"✅ 成功获取 {len(posts)} 条内容:")
                for j, post in enumerate(posts, 1):
                    print(f"  {j}. 标题: {post.title[:80]}...")
                    print(f"     作者: {post.author}")
                    print(f"     内容: {post.content[:100]}...")
                    print(f"     链接: {post.url}")
                    print()
            else:
                print("❌ 未获取到任何内容")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    await crawler.cleanup()
    print("\n🎉 爬虫测试完成!")

if __name__ == "__main__":
    print("=" * 80)
    print("          NewsHub 真实爬虫系统测试")
    print("=" * 80)
    
    asyncio.run(test_crawler()) 