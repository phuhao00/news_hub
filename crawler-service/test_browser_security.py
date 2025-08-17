#!/usr/bin/env python3
"""
浏览器安全配置测试脚本
测试 Playwright 浏览器配置是否能避免安全警告
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.browser_config import get_secure_browser_config, get_minimal_browser_config, get_stealth_browser_config
from crawl4ai import AsyncWebCrawler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 测试网站列表
TEST_URLS = [
    "https://x.com",  # 之前出现安全警告的网站
    "https://www.google.com",
    "https://www.baidu.com",
    "https://www.bilibili.com",
    "https://weibo.com"
]

async def test_browser_config(config_name: str, browser_config, test_urls: list):
    """测试特定的浏览器配置"""
    logger.info(f"开始测试 {config_name} 配置...")
    
    try:
        # 初始化爬虫
        crawler = AsyncWebCrawler(config=browser_config)
        await crawler.start()
        
        logger.info(f"{config_name} 浏览器启动成功")
        
        # 测试访问网站
        for url in test_urls:
            try:
                logger.info(f"测试访问: {url}")
                
                # 设置超时
                result = await asyncio.wait_for(
                    crawler.arun(url=url),
                    timeout=30.0
                )
                
                if result.success:
                    logger.info(f"✓ {url} - 访问成功")
                    logger.info(f"  标题: {result.metadata.get('title', 'N/A')[:50]}...")
                    logger.info(f"  内容长度: {len(result.html) if result.html else 0}")
                else:
                    logger.warning(f"✗ {url} - 访问失败: {result.error_message}")
                    
            except asyncio.TimeoutError:
                logger.error(f"✗ {url} - 访问超时")
            except Exception as e:
                logger.error(f"✗ {url} - 访问异常: {str(e)}")
        
        # 清理资源
        await crawler.close()
        logger.info(f"{config_name} 测试完成")
        
    except Exception as e:
        logger.error(f"{config_name} 配置测试失败: {str(e)}")

async def main():
    """主测试函数"""
    logger.info("开始浏览器安全配置测试...")
    
    # 测试不同的配置
    configs = [
        ("安全配置", get_secure_browser_config()),
        ("最小化配置", get_minimal_browser_config()),
        ("隐身配置", get_stealth_browser_config())
    ]
    
    for config_name, browser_config in configs:
        await test_browser_config(config_name, browser_config, TEST_URLS)
        logger.info("-" * 50)
    
    logger.info("所有测试完成!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        sys.exit(1)

