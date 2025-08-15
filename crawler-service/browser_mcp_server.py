#!/usr/bin/env python3
"""
浏览器MCP服务器

提供基于浏览器的网页抓取功能，支持JavaScript渲染和复杂页面处理。
使用Playwright进行浏览器自动化。
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import json
import time
from urllib.parse import urlparse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP服务器实例
mcp = FastMCP("Browser MCP Server")

# 全局浏览器实例
browser: Optional[Browser] = None
context: Optional[BrowserContext] = None

async def initialize_browser():
    """初始化浏览器实例"""
    global browser, context
    
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled',
                '--exclude-switches=enable-automation',
                '--disable-extensions-except=*',
                '--disable-plugins-discovery',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-infobars',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
                '--allow-running-insecure-content',
                '--disable-popup-blocking'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "max-age=0",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        logger.info("浏览器初始化成功")
        
    except Exception as e:
        logger.error(f"浏览器初始化失败: {e}")
        raise

async def cleanup_browser():
    """清理浏览器资源"""
    global browser, context
    
    try:
        if context:
            await context.close()
        if browser:
            await browser.close()
        logger.info("浏览器资源清理完成")
    except Exception as e:
        logger.error(f"浏览器清理失败: {e}")

@mcp.tool()
async def fetch_page_content(
    url: str,
    wait_for_selector: Optional[str] = None,
    wait_time: int = 3,
    js_code: Optional[str] = None,
    extract_links: bool = False,
    extract_images: bool = False,
    platform: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用浏览器获取网页内容
    
    Args:
        url: 要抓取的网页URL
        wait_for_selector: 等待特定CSS选择器出现
        wait_time: 等待时间（秒）
        js_code: 要执行的JavaScript代码
        extract_links: 是否提取链接
        extract_images: 是否提取图片
        platform: 平台类型（weibo, bilibili, xiaohongshu, douyin等）
    
    Returns:
        包含网页内容的字典
    """
    global context
    
    if not context:
        await initialize_browser()
    
    start_time = time.time()
    
    try:
        page = await context.new_page()
        
        # 平台特定设置
        if platform:
            await _apply_platform_settings(page, platform)
        
        # 导航到页面
        logger.info(f"正在访问: {url}")
        response = await page.goto(url, wait_until='networkidle', timeout=30000)
        
        if not response:
            raise Exception("页面加载失败")
        
        # 等待特定选择器
        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            except Exception as e:
                logger.warning(f"等待选择器超时: {wait_for_selector}, {e}")
        
        # 等待页面稳定
        await asyncio.sleep(wait_time)
        
        # 执行自定义JavaScript
        if js_code:
            try:
                await page.evaluate(js_code)
                await asyncio.sleep(1)  # 等待JS执行完成
            except Exception as e:
                logger.warning(f"JavaScript执行失败: {e}")
        
        # 获取页面内容
        html_content = await page.content()
        title = await page.title()
        
        # 提取链接
        links = []
        if extract_links:
            link_elements = await page.query_selector_all('a[href]')
            for element in link_elements:
                href = await element.get_attribute('href')
                text = await element.inner_text()
                if href:
                    links.append({
                        'url': href,
                        'text': text.strip() if text else ''
                    })
        
        # 提取图片
        images = []
        if extract_images:
            img_elements = await page.query_selector_all('img[src]')
            for element in img_elements:
                src = await element.get_attribute('src')
                alt = await element.get_attribute('alt')
                if src:
                    images.append({
                        'url': src,
                        'alt': alt or ''
                    })
        
        await page.close()
        
        processing_time = time.time() - start_time
        
        return {
            'success': True,
            'url': url,
            'title': title,
            'html_content': html_content,
            'links': links,
            'images': images,
            'status_code': response.status,
            'processing_time': processing_time,
            'metadata': {
                'platform': platform,
                'user_agent': await page.evaluate('navigator.userAgent'),
                'viewport': await page.viewport_size()
            }
        }
        
    except Exception as e:
        logger.error(f"页面抓取失败 {url}: {e}")
        return {
            'success': False,
            'url': url,
            'error_message': str(e),
            'processing_time': time.time() - start_time
        }

async def _apply_platform_settings(page: Page, platform: str):
    """应用平台特定设置"""
    try:
        if platform == 'weibo':
            # 微博特定设置
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en'],
                });
            """)
            
        elif platform == 'bilibili':
            # B站特定设置
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
        elif platform == 'xiaohongshu':
            # 小红书特定设置
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
        elif platform == 'douyin':
            # 抖音特定设置
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
    except Exception as e:
        logger.warning(f"应用平台设置失败 {platform}: {e}")

@mcp.tool()
async def get_server_status() -> Dict[str, Any]:
    """
    获取浏览器MCP服务器状态
    
    Returns:
        服务器状态信息
    """
    global browser, context
    
    return {
        'service_name': 'Browser MCP Server',
        'status': 'running',
        'browser_initialized': browser is not None,
        'context_initialized': context is not None,
        'capabilities': [
            'fetch_page_content',
            'javascript_execution',
            'link_extraction',
            'image_extraction',
            'platform_optimization'
        ]
    }

if __name__ == "__main__":
    import sys
    import uvicorn
    from fastapi import FastAPI
    
    # 创建FastAPI应用
    app = FastAPI(title="Browser MCP Server", version="1.0.0")
    
    @app.on_event("startup")
    async def startup_event():
        """应用启动时初始化浏览器"""
        try:
            await initialize_browser()
            logger.info("浏览器MCP服务器启动成功")
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭时清理浏览器"""
        await cleanup_browser()
        logger.info("浏览器MCP服务器已关闭")
    
    @app.post("/fetch")
    async def fetch_endpoint(request: dict):
        """HTTP端点用于获取页面内容"""
        try:
            url = request.get('url')
            if not url:
                return {'success': False, 'error': 'URL is required'}
            
            result = await fetch_page_content(
                url=url,
                platform=request.get('platform'),
                wait_for_selector=request.get('wait_for_selector'),
                js_code=request.get('js_code'),
                extract_links=request.get('extract_links', False),
                extract_images=request.get('extract_images', False),
                wait_time=request.get('wait_time', 2)
            )
            return result
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @app.get("/status")
    async def status_endpoint():
        """获取服务器状态"""
        return await get_server_status()
    
    # 运行HTTP服务器
    try:
        logger.info("启动浏览器MCP HTTP服务器在端口3001")
        uvicorn.run(app, host="0.0.0.0", port=3001, log_level="info")
    except Exception as e:
        logger.error(f"启动服务器失败: {e}")