#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP服务集成模块
支持通过浏览器MCP和本地MCP服务获取网页内容，然后使用crawl4ai进行信息提取
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import aiohttp
import requests
from bs4 import BeautifulSoup

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class MCPResponse:
    """MCP服务响应数据结构"""
    success: bool
    html_content: str
    url: str
    status_code: int = 200
    headers: Dict[str, str] = None
    error_message: str = None
    response_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.metadata is None:
            self.metadata = {}

class BaseMCPService(ABC):
    """MCP服务基类"""
    
    def __init__(self, service_name: str, config: Dict[str, Any] = None):
        self.service_name = service_name
        self.config = config or {}
        self.session = None
        
    @abstractmethod
    async def fetch_page(self, url: str, **kwargs) -> MCPResponse:
        """获取网页内容"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化服务"""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """清理资源"""
        pass

class BrowserMCPService(BaseMCPService):
    """浏览器MCP服务
    
    通过MCP协议与浏览器服务通信，获取完整渲染的网页内容
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("browser_mcp", config)
        self.mcp_endpoint = self.config.get('mcp_endpoint', 'http://localhost:3001')
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        
    async def initialize(self) -> bool:
        """初始化浏览器MCP服务"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            # 测试连接
            async with self.session.get(f"{self.mcp_endpoint}/status") as response:
                if response.status == 200:
                    logger.info(f"浏览器MCP服务连接成功: {self.mcp_endpoint}")
                    return True
                else:
                    logger.error(f"浏览器MCP服务连接失败: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"初始化浏览器MCP服务失败: {str(e)}")
            return False
    
    async def fetch_page(self, url: str, **kwargs) -> MCPResponse:
        """通过浏览器MCP获取网页内容"""
        start_time = time.time()
        
        # 构建MCP请求参数
        mcp_params = {
            'url': url,
            'wait_for': kwargs.get('wait_for', 'networkidle'),
            'timeout': kwargs.get('page_timeout', 30000),
            'viewport': kwargs.get('viewport', {'width': 1920, 'height': 1080}),
            'user_agent': kwargs.get('user_agent'),
            'headers': kwargs.get('headers', {}),
            'javascript': kwargs.get('js_code', []),
            'wait_for_selector': kwargs.get('wait_for_selector'),
            'screenshot': kwargs.get('screenshot', False),
            'pdf': kwargs.get('pdf', False)
        }
        
        # 移除None值
        mcp_params = {k: v for k, v in mcp_params.items() if v is not None}
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"浏览器MCP获取页面 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                
                async with self.session.post(
                    f"{self.mcp_endpoint}/fetch",
                    json=mcp_params,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('success'):
                            logger.info(f"浏览器MCP获取成功: {url} (耗时: {response_time:.2f}秒)")
                            return MCPResponse(
                                success=True,
                                html_content=result.get('html', ''),
                                url=url,
                                status_code=result.get('status_code', 200),
                                headers=result.get('headers', {}),
                                response_time=response_time,
                                metadata={
                                    'service': 'browser_mcp',
                                    'attempt': attempt + 1,
                                    'screenshot': result.get('screenshot'),
                                    'pdf': result.get('pdf')
                                }
                            )
                        else:
                            error_msg = result.get('error', '未知错误')
                            logger.warning(f"浏览器MCP返回错误: {error_msg}")
                            
                    else:
                        error_msg = f"HTTP错误: {response.status}"
                        logger.warning(f"浏览器MCP请求失败: {error_msg}")
                        
            except asyncio.TimeoutError:
                error_msg = "请求超时"
                logger.warning(f"浏览器MCP超时: {url}")
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                logger.error(f"浏览器MCP异常: {error_msg}")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
        
        response_time = time.time() - start_time
        return MCPResponse(
            success=False,
            html_content='',
            url=url,
            error_message=f"浏览器MCP获取失败，重试 {self.max_retries} 次后仍然失败",
            response_time=response_time,
            metadata={'service': 'browser_mcp', 'attempts': self.max_retries}
        )
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            logger.info("浏览器MCP服务会话已关闭")

class LocalMCPService(BaseMCPService):
    """本地MCP服务
    
    通过本地MCP服务获取网页内容，适用于简单的HTTP请求
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("local_mcp", config)
        self.mcp_endpoint = self.config.get('mcp_endpoint', 'http://localhost:8080')
        self.timeout = self.config.get('timeout', 15)
        self.max_retries = self.config.get('max_retries', 2)
        
    async def initialize(self) -> bool:
        """初始化本地MCP服务"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            # 测试连接
            async with self.session.get(f"{self.mcp_endpoint}/status") as response:
                if response.status == 200:
                    logger.info(f"本地MCP服务连接成功: {self.mcp_endpoint}")
                    return True
                else:
                    logger.error(f"本地MCP服务连接失败: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"初始化本地MCP服务失败: {str(e)}")
            return False
    
    async def fetch_page(self, url: str, **kwargs) -> MCPResponse:
        """通过本地MCP获取网页内容"""
        start_time = time.time()
        
        # 构建MCP请求参数
        mcp_params = {
            'url': url,
            'method': kwargs.get('method', 'GET'),
            'headers': kwargs.get('headers', {}),
            'timeout': kwargs.get('timeout', 15),
            'follow_redirects': kwargs.get('follow_redirects', True),
            'verify_ssl': kwargs.get('verify_ssl', True)
        }
        
        # 如果是POST请求，添加数据
        if kwargs.get('data'):
            mcp_params['data'] = kwargs['data']
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"本地MCP获取页面 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                
                async with self.session.post(
                    f"{self.mcp_endpoint}/fetch",
                    json=mcp_params,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('success'):
                            logger.info(f"本地MCP获取成功: {url} (耗时: {response_time:.2f}秒)")
                            return MCPResponse(
                                success=True,
                                html_content=result.get('content', ''),
                                url=url,
                                status_code=result.get('status_code', 200),
                                headers=result.get('headers', {}),
                                response_time=response_time,
                                metadata={
                                    'service': 'local_mcp',
                                    'attempt': attempt + 1,
                                    'content_type': result.get('content_type'),
                                    'content_length': result.get('content_length')
                                }
                            )
                        else:
                            error_msg = result.get('error', '未知错误')
                            logger.warning(f"本地MCP返回错误: {error_msg}")
                            
                    else:
                        error_msg = f"HTTP错误: {response.status}"
                        logger.warning(f"本地MCP请求失败: {error_msg}")
                        
            except asyncio.TimeoutError:
                error_msg = "请求超时"
                logger.warning(f"本地MCP超时: {url}")
            except Exception as e:
                error_msg = f"请求异常: {str(e)}"
                logger.error(f"本地MCP异常: {error_msg}")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                wait_time = (attempt + 1) * 1.5
                logger.info(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
        
        response_time = time.time() - start_time
        return MCPResponse(
            success=False,
            html_content='',
            url=url,
            error_message=f"本地MCP获取失败，重试 {self.max_retries} 次后仍然失败",
            response_time=response_time,
            metadata={'service': 'local_mcp', 'attempts': self.max_retries}
        )
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            logger.info("本地MCP服务会话已关闭")

class MCPServiceManager:
    """MCP服务管理器
    
    统一管理浏览器MCP和本地MCP服务，提供智能路由和故障转移
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.services: Dict[str, BaseMCPService] = {}
        self.service_priority = self.config.get('service_priority', ['browser_mcp', 'local_mcp'])
        self.fallback_enabled = self.config.get('fallback_enabled', True)
        
    async def initialize(self) -> bool:
        """初始化所有MCP服务"""
        success_count = 0
        
        # 初始化浏览器MCP服务
        if 'browser_mcp' in self.service_priority:
            browser_config = self.config.get('browser_mcp', {})
            browser_service = BrowserMCPService(browser_config)
            if await browser_service.initialize():
                self.services['browser_mcp'] = browser_service
                success_count += 1
            else:
                logger.warning("浏览器MCP服务初始化失败")
        
        # 初始化本地MCP服务
        if 'local_mcp' in self.service_priority:
            local_config = self.config.get('local_mcp', {})
            local_service = LocalMCPService(local_config)
            if await local_service.initialize():
                self.services['local_mcp'] = local_service
                success_count += 1
            else:
                logger.warning("本地MCP服务初始化失败")
        
        logger.info(f"MCP服务管理器初始化完成，成功初始化 {success_count} 个服务")
        return success_count > 0
    
    def _should_use_browser_mcp(self, url: str, **kwargs) -> bool:
        """判断是否应该使用浏览器MCP服务"""
        # 需要JavaScript渲染的情况
        if kwargs.get('js_code') or kwargs.get('wait_for_selector'):
            return True
        
        # 复杂的单页应用
        spa_patterns = ['weibo.com', 'bilibili.com', 'xiaohongshu.com', 'douyin.com']
        if any(pattern in url for pattern in spa_patterns):
            return True
        
        # 需要特殊等待条件
        if kwargs.get('wait_for') in ['networkidle', 'domcontentloaded']:
            return True
        
        return False
    
    async def fetch_page(self, url: str, **kwargs) -> MCPResponse:
        """智能选择MCP服务获取网页内容"""
        # 确定使用的服务顺序
        preferred_services = []
        
        if self._should_use_browser_mcp(url, **kwargs):
            preferred_services = ['browser_mcp', 'local_mcp']
        else:
            preferred_services = ['local_mcp', 'browser_mcp']
        
        # 只使用已初始化的服务
        available_services = [s for s in preferred_services if s in self.services]
        
        if not available_services:
            return MCPResponse(
                success=False,
                html_content='',
                url=url,
                error_message="没有可用的MCP服务"
            )
        
        # 尝试使用首选服务
        primary_service = available_services[0]
        logger.info(f"使用 {primary_service} 服务获取: {url}")
        
        response = await self.services[primary_service].fetch_page(url, **kwargs)
        
        # 如果首选服务失败且启用了故障转移
        if not response.success and self.fallback_enabled and len(available_services) > 1:
            fallback_service = available_services[1]
            logger.info(f"故障转移到 {fallback_service} 服务: {url}")
            
            # 为故障转移调整参数
            fallback_kwargs = kwargs.copy()
            if fallback_service == 'local_mcp':
                # 移除浏览器特定的参数
                fallback_kwargs.pop('js_code', None)
                fallback_kwargs.pop('wait_for_selector', None)
                fallback_kwargs.pop('wait_for', None)
            
            fallback_response = await self.services[fallback_service].fetch_page(url, **fallback_kwargs)
            if fallback_response.success:
                fallback_response.metadata['fallback_from'] = primary_service
                return fallback_response
        
        return response
    
    async def get_service_status(self, service_type: str) -> Dict[str, Any]:
        """获取指定服务的状态"""
        service_key = f"{service_type}_mcp" if not service_type.endswith('_mcp') else service_type
        
        if service_key in self.services:
            service = self.services[service_key]
            return {
                'available': True,
                'status': 'running',
                'last_used': None,  # 可以在后续版本中添加实际的最后使用时间跟踪
                'service_name': service.service_name,
                'endpoint': getattr(service, 'mcp_endpoint', 'unknown')
            }
        else:
            return {
                'available': False,
                'status': 'not_initialized',
                'last_used': None,
                'service_name': f"{service_type}_mcp",
                'endpoint': 'unknown'
            }
    
    async def cleanup(self):
        """清理所有服务资源"""
        for service_name, service in self.services.items():
            try:
                await service.cleanup()
                logger.info(f"{service_name} 服务已清理")
            except Exception as e:
                logger.error(f"清理 {service_name} 服务时出错: {str(e)}")
        
        self.services.clear()
        logger.info("MCP服务管理器已清理完成")

# 全局MCP服务管理器实例
mcp_manager: Optional[MCPServiceManager] = None

async def get_mcp_manager(config: Dict[str, Any] = None) -> MCPServiceManager:
    """获取全局MCP服务管理器实例"""
    global mcp_manager
    
    if mcp_manager is None:
        mcp_manager = MCPServiceManager(config)
        await mcp_manager.initialize()
    
    return mcp_manager

async def cleanup_mcp_manager():
    """清理全局MCP服务管理器"""
    global mcp_manager
    
    if mcp_manager:
        await mcp_manager.cleanup()
        mcp_manager = None
        logger.info("全局MCP服务管理器已清理")