#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态内容提取功能
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import UnifiedCrawlerService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_weibo_dynamic_extraction():
    """测试微博动态内容提取"""
    logger.info("开始测试微博动态内容提取功能")
    
    # 创建爬虫服务实例
    crawler_service = UnifiedCrawlerService()
    
    # 测试URL列表
    test_urls = [
        {
            'url': 'https://weibo.com/周杰伦中文网JayCn',
            'platform': 'weibo',
            'description': '周杰伦微博用户页面'
        },
        {
            'url': 'https://weibo.com/u/1195230310',
            'platform': 'weibo', 
            'description': '微博用户ID页面'
        }
    ]
    
    results = []
    
    for test_case in test_urls:
        logger.info(f"\n{'='*60}")
        logger.info(f"测试案例: {test_case['description']}")
        logger.info(f"原始URL: {test_case['url']}")
        logger.info(f"平台: {test_case['platform']}")
        logger.info(f"{'='*60}")
        
        try:
            # 生成平台特定的URL
            generated_urls = crawler_service._generate_platform_urls(
                test_case['url'], 
                test_case['platform']
            )
            
            logger.info(f"生成的URL列表: {generated_urls}")
            
            # 测试每个生成的URL
            for i, url in enumerate(generated_urls):
                logger.info(f"\n--- 测试URL {i+1}: {url} ---")
                
                # 使用crawl4ai提取内容
                posts = await crawler_service._extract_with_crawl4ai(
                    url, 
                    test_case['platform']
                )
                
                result = {
                    'original_url': test_case['url'],
                    'generated_url': url,
                    'platform': test_case['platform'],
                    'description': test_case['description'],
                    'success': len(posts) > 0,
                    'posts_count': len(posts),
                    'posts': posts,
                    'timestamp': datetime.now().isoformat()
                }
                
                if posts:
                    logger.info(f"✅ 成功提取到 {len(posts)} 条内容")
                    for j, post in enumerate(posts):
                        logger.info(f"  内容 {j+1}:")
                        logger.info(f"    标题: {post.title[:100]}...")
                        logger.info(f"    作者: {post.author}")
                        logger.info(f"    内容长度: {len(post.content)} 字符")
                        logger.info(f"    内容预览: {post.content[:200]}...")
                        logger.info(f"    图片数量: {len(post.images)}")
                        logger.info(f"    标签: {post.tags}")
                else:
                    logger.warning(f"❌ 未能提取到有效内容")
                
                results.append(result)
                
                # 避免请求过于频繁
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"测试失败: {str(e)}")
            logger.exception("详细错误信息:")
            
            result = {
                'original_url': test_case['url'],
                'generated_url': test_case['url'],
                'platform': test_case['platform'],
                'description': test_case['description'],
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            results.append(result)
    
    # 输出测试总结
    logger.info(f"\n{'='*60}")
    logger.info("测试总结")
    logger.info(f"{'='*60}")
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
    
    logger.info(f"总测试数: {total_tests}")
    logger.info(f"成功数: {successful_tests}")
    logger.info(f"成功率: {success_rate:.1f}%")
    
    for result in results:
        status = "✅ 成功" if result['success'] else "❌ 失败"
        logger.info(f"{status} - {result['description']} - {result.get('posts_count', 0)} 条内容")
    
    return results

async def main():
    """主函数"""
    logger.info("开始动态内容提取测试")
    
    try:
        results = await test_weibo_dynamic_extraction()
        logger.info("测试完成")
        return results
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        logger.exception("详细错误信息:")
        return []

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())