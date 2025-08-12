#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试crawl4ai在中文社交媒体平台上的表现
验证修复后的实现是否能正确处理动态内容
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import UnifiedCrawlerService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_crawl4ai_platforms.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

async def test_platform_crawling():
    """测试各个平台的crawl4ai爬取功能"""
    
    # 初始化爬虫服务
    logger.info("初始化UnifiedCrawlerService...")
    crawler_service = UnifiedCrawlerService()
    
    try:
        # 等待crawl4ai初始化
        await asyncio.sleep(2)
        
        # 测试用例 - 使用一些公开的测试URL
        test_cases = [
            {
                'platform': 'weibo',
                'url': 'https://weibo.com/u/1234567890',  # 示例微博用户页面
                'description': '微博用户页面测试'
            },
            {
                'platform': 'bilibili', 
                'url': 'https://www.bilibili.com/video/BV1xx411c7mu',  # 示例B站视频
                'description': 'B站视频页面测试'
            },
            {
                'platform': 'xiaohongshu',
                'url': 'https://www.xiaohongshu.com/explore/123456',  # 示例小红书页面
                'description': '小红书内容页面测试'
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"测试 {i}/{len(test_cases)}: {test_case['description']}")
            logger.info(f"平台: {test_case['platform']}")
            logger.info(f"URL: {test_case['url']}")
            logger.info(f"{'='*60}")
            
            start_time = datetime.now()
            
            try:
                # 使用crawl4ai提取内容
                posts = await crawler_service._extract_with_crawl4ai(
                    url=test_case['url'],
                    platform=test_case['platform'],
                    max_retries=2  # 减少重试次数以加快测试
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                result = {
                    'platform': test_case['platform'],
                    'url': test_case['url'],
                    'success': len(posts) > 0,
                    'posts_count': len(posts),
                    'duration': duration,
                    'error': None
                }
                
                if posts:
                    logger.info(f"✅ 成功提取到 {len(posts)} 条内容，耗时: {duration:.2f}秒")
                    
                    # 显示第一条内容的详细信息
                    first_post = posts[0]
                    logger.info(f"第一条内容详情:")
                    logger.info(f"  标题: {first_post.title[:100]}...")
                    logger.info(f"  作者: {first_post.author}")
                    logger.info(f"  内容长度: {len(first_post.content)} 字符")
                    logger.info(f"  标签数量: {len(first_post.tags)}")
                    logger.info(f"  图片数量: {len(first_post.images)}")
                    logger.info(f"  视频URL: {'有' if first_post.video_url else '无'}")
                    
                    result['sample_post'] = {
                        'title': first_post.title[:100],
                        'author': first_post.author,
                        'content_length': len(first_post.content),
                        'tags_count': len(first_post.tags),
                        'images_count': len(first_post.images),
                        'has_video': bool(first_post.video_url)
                    }
                else:
                    logger.warning(f"❌ 未能提取到有效内容，耗时: {duration:.2f}秒")
                
                results.append(result)
                
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(f"❌ 测试失败: {str(e)}，耗时: {duration:.2f}秒")
                
                result = {
                    'platform': test_case['platform'],
                    'url': test_case['url'],
                    'success': False,
                    'posts_count': 0,
                    'duration': duration,
                    'error': str(e)
                }
                results.append(result)
            
            # 测试间隔
            if i < len(test_cases):
                logger.info("等待5秒后进行下一个测试...")
                await asyncio.sleep(5)
        
        # 输出测试总结
        logger.info(f"\n{'='*60}")
        logger.info("测试总结")
        logger.info(f"{'='*60}")
        
        successful_tests = sum(1 for r in results if r['success'])
        total_tests = len(results)
        
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"成功测试: {successful_tests}")
        logger.info(f"失败测试: {total_tests - successful_tests}")
        logger.info(f"成功率: {(successful_tests/total_tests)*100:.1f}%")
        
        for result in results:
            status = "✅ 成功" if result['success'] else "❌ 失败"
            logger.info(f"  {result['platform']}: {status} ({result['posts_count']} 条内容, {result['duration']:.2f}秒)")
            if result['error']:
                logger.info(f"    错误: {result['error']}")
        
        return results
        
    finally:
        # 清理资源
        logger.info("清理crawl4ai资源...")
        await crawler_service.cleanup()

async def test_crawl4ai_basic_functionality():
    """测试crawl4ai的基本功能"""
    logger.info("\n测试crawl4ai基本功能...")
    
    from crawl4ai import AsyncWebCrawler
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        # 测试简单的静态页面
        result = await crawler.arun(url="https://httpbin.org/html")
        
        if result.success:
            logger.info("✅ crawl4ai基本功能正常")
            logger.info(f"  HTML长度: {len(result.html or '')}")
            logger.info(f"  清理后HTML长度: {len(result.cleaned_html or '')}")
            return True
        else:
            logger.error(f"❌ crawl4ai基本功能异常: {result.error_message}")
            return False

async def main():
    """主测试函数"""
    logger.info("开始crawl4ai平台测试")
    logger.info(f"测试时间: {datetime.now()}")
    
    try:
        # 1. 测试基本功能
        basic_ok = await test_crawl4ai_basic_functionality()
        if not basic_ok:
            logger.error("crawl4ai基本功能测试失败，跳过平台测试")
            return
        
        # 2. 测试平台爬取
        results = await test_platform_crawling()
        
        # 3. 生成测试报告
        logger.info("\n生成测试报告...")
        
        report = {
            'test_time': datetime.now().isoformat(),
            'basic_functionality': basic_ok,
            'platform_tests': results,
            'summary': {
                'total_tests': len(results),
                'successful_tests': sum(1 for r in results if r['success']),
                'success_rate': (sum(1 for r in results if r['success']) / len(results)) * 100 if results else 0
            }
        }
        
        # 保存测试报告
        import json
        with open('crawl4ai_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info("测试报告已保存到 crawl4ai_test_report.json")
        
    except Exception as e:
        logger.error(f"测试过程中发生异常: {str(e)}")
        logger.exception("详细错误信息:")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())