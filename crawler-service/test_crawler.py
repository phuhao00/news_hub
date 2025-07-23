#!/usr/bin/env python3
"""
测试脚本 - 验证爬虫服务功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawl4ai import AsyncWebCrawler
from crawlers.platforms import CrawlerFactory, NewsCrawler

async def test_basic_crawl():
    """测试基础爬取功能"""
    print("🧪 测试基础爬取功能...")
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
        )
        
        print(f"✅ 成功爬取页面")
        print(f"📄 标题: {result.metadata.get('title', 'N/A') if result.metadata else 'N/A'}")
        print(f"📝 内容长度: {len(result.markdown) if result.markdown else 0} 字符")
        print(f"🔗 链接数量: {len(result.links.get('internal', [])) if result.links else 0}")
        
        # 显示部分内容
        if result.markdown:
            preview = result.markdown[:200] + "..." if len(result.markdown) > 200 else result.markdown
            print(f"📖 内容预览:\n{preview}")

async def test_news_crawler():
    """测试新闻爬虫"""
    print("\n🧪 测试新闻爬虫...")
    
    news_crawler = NewsCrawler()
    try:
        # 这里使用一个简单的新闻网站进行测试
        articles = await news_crawler.crawl_news_articles("https://www.bbc.com/news", limit=3)
        
        print(f"✅ 成功爬取 {len(articles)} 篇文章")
        
        for i, article in enumerate(articles, 1):
            print(f"\n📰 文章 {i}:")
            print(f"   标题: {article.title}")
            print(f"   平台: {article.platform}")
            print(f"   URL: {article.url}")
            print(f"   内容长度: {len(article.content)} 字符")
            
    except Exception as e:
        print(f"❌ 新闻爬虫测试失败: {e}")
    finally:
        await news_crawler.cleanup()

async def test_platform_crawlers():
    """测试平台爬虫"""
    print("\n🧪 测试平台爬虫...")
    
    platforms = CrawlerFactory.get_supported_platforms()
    print(f"📱 支持的平台: {', '.join(platforms)}")
    
    # 测试每个平台的爬虫初始化
    for platform in platforms:
        try:
            crawler = CrawlerFactory.get_crawler(platform)
            print(f"✅ {platform} 爬虫初始化成功")
            await crawler.cleanup()
        except Exception as e:
            print(f"❌ {platform} 爬虫初始化失败: {e}")

async def test_example_from_docs():
    """测试文档中的示例代码"""
    print("\n🧪 测试文档示例...")
    
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url="https://www.nbcnews.com/business",
            )
            print("✅ 文档示例运行成功")
            print(f"📊 结果类型: {type(result)}")
            print(f"📄 是否有内容: {'是' if result.markdown else '否'}")
            
    except Exception as e:
        print(f"❌ 文档示例运行失败: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始测试 NewsHub Crawler Service")
    print("=" * 50)
    
    try:
        # 测试基础爬取
        await test_basic_crawl()
        
        # 测试新闻爬虫
        await test_news_crawler()
        
        # 测试平台爬虫
        await test_platform_crawlers()
        
        # 测试文档示例
        await test_example_from_docs()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())