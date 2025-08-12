#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawl4ai功能测试脚本
用于验证crawl4ai是否正确工作
"""

import asyncio
import logging
from crawl4ai import AsyncWebCrawler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_crawl():
    """测试基本的crawl4ai功能"""
    try:
        logger.info("开始测试crawl4ai基本功能...")
        
        # 创建异步爬虫实例
        async with AsyncWebCrawler(
            verbose=True,
            headless=True,
            browser_type="chromium"
        ) as crawler:
            
            # 测试简单的网页爬取
            test_url = "https://httpbin.org/html"
            logger.info(f"测试URL: {test_url}")
            
            result = await crawler.arun(
                url=test_url,
                word_count_threshold=10,
                bypass_cache=True
            )
            
            if result.success:
                logger.info("✅ crawl4ai基本功能测试成功")
                logger.info(f"页面标题: {result.metadata.get('title', 'N/A') if result.metadata else 'N/A'}")
                logger.info(f"内容长度: {len(result.cleaned_html or '')} 字符")
                logger.info(f"Markdown长度: {len(result.markdown or '')} 字符")
                return True
            else:
                logger.error(f"❌ crawl4ai爬取失败: {result.error_message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ crawl4ai测试异常: {str(e)}")
        logger.exception("详细错误信息:")
        return False

async def test_dynamic_content():
    """测试动态内容爬取"""
    try:
        logger.info("开始测试crawl4ai动态内容功能...")
        
        async with AsyncWebCrawler(
            verbose=True,
            headless=True,
            browser_type="chromium",
            browser_args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        ) as crawler:
            
            # 测试需要JavaScript渲染的页面
            test_url = "https://quotes.toscrape.com/js/"
            logger.info(f"测试动态内容URL: {test_url}")
            
            result = await crawler.arun(
                url=test_url,
                word_count_threshold=10,
                bypass_cache=True,
                wait_for="networkidle",
                timeout=30000,
                delay_before_return_html=2
            )
            
            if result.success:
                content = result.cleaned_html or result.markdown or ''
                if 'quote' in content.lower() or len(content) > 500:
                    logger.info("✅ crawl4ai动态内容测试成功")
                    logger.info(f"动态内容长度: {len(content)} 字符")
                    return True
                else:
                    logger.warning("⚠️ crawl4ai可能未正确渲染动态内容")
                    logger.info(f"获取的内容: {content[:200]}...")
                    return False
            else:
                logger.error(f"❌ crawl4ai动态内容爬取失败: {result.error_message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ crawl4ai动态内容测试异常: {str(e)}")
        logger.exception("详细错误信息:")
        return False

async def test_chinese_content():
    """测试中文内容爬取"""
    try:
        logger.info("开始测试crawl4ai中文内容功能...")
        
        async with AsyncWebCrawler(
            verbose=True,
            headless=True,
            browser_type="chromium",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ) as crawler:
            
            # 测试中文网站
            test_url = "https://www.baidu.com"
            logger.info(f"测试中文内容URL: {test_url}")
            
            result = await crawler.arun(
                url=test_url,
                word_count_threshold=5,
                bypass_cache=True
            )
            
            if result.success:
                content = result.cleaned_html or result.markdown or ''
                if '百度' in content or len(content) > 100:
                    logger.info("✅ crawl4ai中文内容测试成功")
                    logger.info(f"中文内容长度: {len(content)} 字符")
                    return True
                else:
                    logger.warning("⚠️ crawl4ai可能未正确处理中文内容")
                    return False
            else:
                logger.error(f"❌ crawl4ai中文内容爬取失败: {result.error_message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ crawl4ai中文内容测试异常: {str(e)}")
        logger.exception("详细错误信息:")
        return False

async def main():
    """主测试函数"""
    logger.info("=" * 50)
    logger.info("开始crawl4ai功能测试")
    logger.info("=" * 50)
    
    tests = [
        ("基本功能测试", test_basic_crawl),
        ("动态内容测试", test_dynamic_content),
        ("中文内容测试", test_chinese_content)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"测试 {test_name} 发生异常: {str(e)}")
            results.append((test_name, False))
    
    # 输出测试结果
    logger.info("\n" + "=" * 50)
    logger.info("测试结果汇总")
    logger.info("=" * 50)
    
    success_count = 0
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if success:
            success_count += 1
    
    logger.info(f"\n总体结果: {success_count}/{len(results)} 个测试通过")
    
    if success_count == len(results):
        logger.info("🎉 所有测试通过，crawl4ai功能正常")
    elif success_count > 0:
        logger.warning("⚠️ 部分测试通过，crawl4ai可能存在问题")
    else:
        logger.error("💥 所有测试失败，crawl4ai存在严重问题")

if __name__ == "__main__":
    asyncio.run(main())