#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP与crawl4ai集成模块
将MCP服务获取的HTML内容传递给crawl4ai进行信息提取和处理
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from bs4 import BeautifulSoup
import html2text

# crawl4ai imports
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from utils.browser_config import get_minimal_browser_config
from crawl4ai.extraction_strategy import LLMExtractionStrategy, CosineStrategy
from crawl4ai.chunking_strategy import RegexChunking

# 本地imports
from mcp_service import MCPResponse, MCPServiceManager, get_mcp_manager

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class MCPCrawl4AIResult:
    """MCP + crawl4ai 处理结果"""
    success: bool
    url: str
    title: str = ""
    content: str = ""
    cleaned_html: str = ""
    markdown: str = ""
    links: List[Dict[str, str]] = None
    images: List[Dict[str, str]] = None
    metadata: Dict[str, Any] = None
    extracted_content: List[Dict[str, Any]] = None
    error_message: str = ""
    processing_time: float = 0.0
    mcp_response: MCPResponse = None
    
    def __post_init__(self):
        if self.links is None:
            self.links = []
        if self.images is None:
            self.images = []
        if self.metadata is None:
            self.metadata = {}
        if self.extracted_content is None:
            self.extracted_content = []

class MCPCrawl4AIProcessor:
    """MCP与crawl4ai集成处理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.mcp_manager: Optional[MCPServiceManager] = None
        self.crawler: Optional[AsyncWebCrawler] = None
        self.html2text_converter = html2text.HTML2Text()
        self.html2text_converter.ignore_links = False
        self.html2text_converter.ignore_images = False
        
        # 配置参数
        self.content_validation = self.config.get('content_validation', {})
        self.extraction_config = self.config.get('extraction_config', {})
        self.platform_extraction = self.config.get('platform_extraction', {})
        
    async def initialize(self) -> bool:
        """初始化MCP管理器和crawl4ai"""
        try:
            # 初始化MCP管理器
            mcp_config = self.config.get('mcp_services', {})
            self.mcp_manager = await get_mcp_manager(mcp_config)
            
            # 初始化crawl4ai（用于内容处理，不用于网页获取）
            browser_config = get_minimal_browser_config(
                headless=True,
                browser_type="chromium"
            )
            self.crawler = AsyncWebCrawler(config=browser_config)
            await self.crawler.start()
            
            logger.info("MCP-crawl4ai集成处理器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化MCP-crawl4ai处理器失败: {str(e)}")
            return False
    
    def _detect_platform(self, url: str) -> str:
        """检测URL对应的平台"""
        platform_patterns = {
            'weibo': ['weibo.com', 'weibo.cn'],
            'bilibili': ['bilibili.com', 'b23.tv'],
            'xiaohongshu': ['xiaohongshu.com', 'xhslink.com'],
            'douyin': ['douyin.com', 'iesdouyin.com']
        }
        
        for platform, patterns in platform_patterns.items():
            if any(pattern in url for pattern in patterns):
                return platform
        
        return 'general'
    
    def _get_platform_mcp_config(self, platform: str, url: str) -> Dict[str, Any]:
        """获取平台特定的MCP配置"""
        browser_config = self.config.get('browser_mcp', {}).get('platform_configs', {})
        local_config = self.config.get('local_mcp', {}).get('platform_configs', {})
        
        # 合并配置
        mcp_config = {}
        
        # 浏览器MCP配置
        if platform in browser_config:
            platform_config = browser_config[platform]
            mcp_config.update({
                'wait_for': platform_config.get('wait_for'),
                'page_timeout': platform_config.get('timeout'),
                'viewport': platform_config.get('viewport'),
                'headers': platform_config.get('headers', {}),
                'js_code': platform_config.get('javascript', [])
            })
        
        # 本地MCP配置
        elif platform in local_config:
            platform_config = local_config[platform]
            mcp_config.update({
                'timeout': platform_config.get('timeout'),
                'headers': platform_config.get('headers', {})
            })
        
        return mcp_config
    
    def _validate_content(self, html_content: str, url: str) -> bool:
        """验证HTML内容的有效性"""
        if not html_content or len(html_content.strip()) == 0:
            logger.warning(f"HTML内容为空: {url}")
            return False
        
        min_length = self.content_validation.get('min_content_length', 100)
        if len(html_content) < min_length:
            logger.warning(f"HTML内容过短 ({len(html_content)} < {min_length}): {url}")
            return False
        
        # 检查必需的HTML标签
        required_tags = self.content_validation.get('required_tags', [])
        if required_tags:
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in required_tags:
                if not soup.find(tag):
                    logger.warning(f"缺少必需的HTML标签 '{tag}': {url}")
                    return False
        
        return True
    
    def _extract_content_with_selectors(self, html_content: str, platform: str) -> str:
        """使用CSS选择器提取平台特定内容"""
        platform_config = self.platform_extraction.get(platform, {})
        css_selectors = platform_config.get('css_selectors', [])
        exclude_selectors = platform_config.get('exclude_selectors', [])
        
        if not css_selectors:
            return html_content
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除排除的元素
        for exclude_selector in exclude_selectors:
            for element in soup.select(exclude_selector):
                element.decompose()
        
        # 提取目标内容
        extracted_elements = []
        for selector in css_selectors:
            elements = soup.select(selector)
            extracted_elements.extend(elements)
        
        if extracted_elements:
            # 创建新的HTML结构
            new_soup = BeautifulSoup('<html><body></body></html>', 'html.parser')
            body = new_soup.body
            
            for element in extracted_elements:
                body.append(element)
            
            return str(new_soup)
        
        return html_content
    
    def _process_html_with_crawl4ai(self, html_content: str, url: str, platform: str) -> Dict[str, Any]:
        """使用crawl4ai处理HTML内容（不进行网络请求）"""
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取基本信息
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # 提取文本内容
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 获取文本内容
            text_content = soup.get_text()
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)
            
            # 转换为Markdown
            markdown_content = self.html2text_converter.handle(html_content)
            
            # 提取链接
            links = []
            for link in soup.find_all('a', href=True):
                links.append({
                    'url': link['href'],
                    'text': link.get_text().strip(),
                    'title': link.get('title', '')
                })
            
            # 提取图片
            images = []
            for img in soup.find_all('img', src=True):
                images.append({
                    'url': img['src'],
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
            
            # 提取元数据
            metadata = {
                'title': title,
                'url': url,
                'platform': platform,
                'content_length': len(content),
                'link_count': len(links),
                'image_count': len(images)
            }
            
            # 添加meta标签信息
            for meta in soup.find_all('meta'):
                name = meta.get('name') or meta.get('property')
                content_attr = meta.get('content')
                if name and content_attr:
                    metadata[f'meta_{name}'] = content_attr
            
            return {
                'success': True,
                'title': title,
                'content': content,
                'cleaned_html': str(soup),
                'markdown': markdown_content,
                'links': links,
                'images': images,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"crawl4ai处理HTML内容失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def process_url(self, url: str, **kwargs) -> MCPCrawl4AIResult:
        """处理URL：通过MCP获取内容，然后用crawl4ai提取信息"""
        start_time = time.time()
        
        try:
            # 检测平台
            platform = self._detect_platform(url)
            logger.info(f"检测到平台: {platform} for URL: {url}")
            
            # 获取平台特定的MCP配置
            mcp_config = self._get_platform_mcp_config(platform, url)
            mcp_config.update(kwargs)  # 合并用户提供的参数
            
            # 通过MCP获取网页内容
            logger.info(f"通过MCP获取网页内容: {url}")
            mcp_response = await self.mcp_manager.fetch_page(url, **mcp_config)
            
            if not mcp_response.success:
                return MCPCrawl4AIResult(
                    success=False,
                    url=url,
                    error_message=f"MCP获取失败: {mcp_response.error_message}",
                    processing_time=time.time() - start_time,
                    mcp_response=mcp_response
                )
            
            # 验证内容
            if not self._validate_content(mcp_response.html_content, url):
                return MCPCrawl4AIResult(
                    success=False,
                    url=url,
                    error_message="HTML内容验证失败",
                    processing_time=time.time() - start_time,
                    mcp_response=mcp_response
                )
            
            # 使用平台特定的选择器提取内容
            processed_html = self._extract_content_with_selectors(
                mcp_response.html_content, platform
            )
            
            # 使用crawl4ai处理HTML内容
            logger.info(f"使用crawl4ai处理HTML内容: {url}")
            crawl4ai_result = self._process_html_with_crawl4ai(processed_html, url, platform)
            
            if not crawl4ai_result.get('success'):
                return MCPCrawl4AIResult(
                    success=False,
                    url=url,
                    error_message=f"crawl4ai处理失败: {crawl4ai_result.get('error')}",
                    processing_time=time.time() - start_time,
                    mcp_response=mcp_response
                )
            
            # 构建最终结果
            processing_time = time.time() - start_time
            
            # 合并元数据
            final_metadata = crawl4ai_result['metadata'].copy()
            final_metadata.update({
                'mcp_service': mcp_response.metadata.get('service'),
                'mcp_response_time': mcp_response.response_time,
                'total_processing_time': processing_time,
                'platform': platform
            })
            
            result = MCPCrawl4AIResult(
                success=True,
                url=url,
                title=crawl4ai_result['title'],
                content=crawl4ai_result['content'],
                cleaned_html=crawl4ai_result['cleaned_html'],
                markdown=crawl4ai_result['markdown'],
                links=crawl4ai_result['links'],
                images=crawl4ai_result['images'],
                metadata=final_metadata,
                processing_time=processing_time,
                mcp_response=mcp_response
            )
            
            logger.info(f"MCP-crawl4ai处理成功: {url} (耗时: {processing_time:.2f}秒)")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"MCP-crawl4ai处理异常: {url} - {str(e)}")
            
            return MCPCrawl4AIResult(
                success=False,
                url=url,
                error_message=f"处理异常: {str(e)}",
                processing_time=processing_time
            )
    
    async def process_multiple_urls(self, urls: List[str], **kwargs) -> List[MCPCrawl4AIResult]:
        """批量处理多个URL"""
        logger.info(f"开始批量处理 {len(urls)} 个URL")
        
        # 并发处理
        max_concurrent = kwargs.pop('max_concurrent', 5)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_url(url: str) -> MCPCrawl4AIResult:
            async with semaphore:
                return await self.process_url(url, **kwargs)
        
        tasks = [process_single_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(MCPCrawl4AIResult(
                    success=False,
                    url=urls[i],
                    error_message=f"处理异常: {str(result)}"
                ))
            else:
                final_results.append(result)
        
        success_count = sum(1 for r in final_results if r.success)
        logger.info(f"批量处理完成: {success_count}/{len(urls)} 成功")
        
        return final_results
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.crawler:
                await self.crawler.close()
                logger.info("crawl4ai爬虫已关闭")
            
            if self.mcp_manager:
                await self.mcp_manager.cleanup()
                logger.info("MCP管理器已清理")
                
        except Exception as e:
            logger.error(f"清理资源时出错: {str(e)}")

# 全局处理器实例
mcp_crawl4ai_processor: Optional[MCPCrawl4AIProcessor] = None

async def get_mcp_crawl4ai_processor(config: Dict[str, Any] = None) -> MCPCrawl4AIProcessor:
    """获取全局MCP-crawl4ai处理器实例"""
    global mcp_crawl4ai_processor
    
    if mcp_crawl4ai_processor is None:
        mcp_crawl4ai_processor = MCPCrawl4AIProcessor(config)
        await mcp_crawl4ai_processor.initialize()
    
    return mcp_crawl4ai_processor

async def cleanup_mcp_crawl4ai_processor():
    """清理全局MCP-crawl4ai处理器"""
    global mcp_crawl4ai_processor
    
    if mcp_crawl4ai_processor:
        await mcp_crawl4ai_processor.cleanup()
        mcp_crawl4ai_processor = None
        logger.info("全局MCP-crawl4ai处理器已清理")