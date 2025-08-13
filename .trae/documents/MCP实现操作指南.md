# MCP实现操作指南

## 1. MCP协议基础概念

### 1.1 什么是MCP

Model Context Protocol (MCP) 是一个开放协议，用于为大语言模型提供上下文信息。它允许AI应用程序安全地连接到数据源，为模型提供实时、相关的信息。

### 1.2 MCP工作原理

* **客户端-服务器架构**：MCP采用客户端-服务器模式，客户端请求资源，服务器提供数据

* **标准化接口**：通过统一的API接口进行通信

* **安全性**：支持身份验证和权限控制

* **可扩展性**：支持多种数据源和服务类型

### 1.3 核心组件

* **MCP服务器**：提供数据和工具的服务端

* **MCP客户端**：消费数据的应用程序

* **资源**：可访问的数据源（文件、API等）

* **工具**：可执行的功能模块

## 2. 环境准备

### 2.1 Python依赖安装

```bash
pip install mcp
pip install anthropic
pip install fastmcp
pip install httpx
pip install aiohttp
```

### 2.2 Node.js依赖（可选）

某些MCP服务器可能需要Node.js环境：

```bash
npm install @modelcontextprotocol/sdk
```

## 3. MCP服务器实现

### 3.1 浏览器MCP服务器

创建 `browser_mcp_server.py`：

```python
import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from playwright.async_api import async_playwright
import uvicorn

class BrowserRequest(BaseModel):
    url: str
    wait_for: Optional[str] = None
    timeout: int = 30000
    viewport: Dict[str, int] = {"width": 1920, "height": 1080}
    headers: Optional[Dict[str, str]] = None
    javascript: Optional[str] = None

class BrowserMCPServer:
    def __init__(self):
        self.app = FastAPI(title="Browser MCP Server")
        self.browser = None
        self.context = None
        self.setup_routes()
    
    async def startup(self):
        """启动浏览器实例"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--disable-extensions',
                '--disable-default-apps'
            ]
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    
    async def shutdown(self):
        """关闭浏览器实例"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    def setup_routes(self):
        @self.app.on_event("startup")
        async def startup_event():
            await self.startup()
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            await self.shutdown()
        
        @self.app.post("/fetch")
        async def fetch_content(request: BrowserRequest):
            try:
                page = await self.context.new_page()
                
                # 设置视口
                await page.set_viewport_size(request.viewport)
                
                # 设置额外头部
                if request.headers:
                    await page.set_extra_http_headers(request.headers)
                
                # 导航到页面
                await page.goto(request.url, timeout=request.timeout)
                
                # 等待特定元素（如果指定）
                if request.wait_for:
                    await page.wait_for_selector(request.wait_for, timeout=request.timeout)
                
                # 执行JavaScript（如果指定）
                if request.javascript:
                    await page.evaluate(request.javascript)
                
                # 获取页面内容
                content = await page.content()
                title = await page.title()
                url = page.url
                
                await page.close()
                
                return {
                    "success": True,
                    "content": content,
                    "title": title,
                    "url": url,
                    "timestamp": asyncio.get_event_loop().time()
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
        
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "browser_mcp",
                "browser_ready": self.browser is not None
            }

if __name__ == "__main__":
    server = BrowserMCPServer()
    uvicorn.run(server.app, host="0.0.0.0", port=3000)
```

### 3.2 本地MCP服务器

创建 `local_mcp_server.py`：

```python
import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import uvicorn
from fake_useragent import UserAgent

class LocalRequest(BaseModel):
    url: str
    timeout: int = 30
    headers: Optional[Dict[str, str]] = None
    follow_redirects: bool = True
    max_redirects: int = 5

class LocalMCPServer:
    def __init__(self):
        self.app = FastAPI(title="Local MCP Server")
        self.ua = UserAgent()
        self.setup_routes()
    
    def get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def setup_routes(self):
        @self.app.post("/fetch")
        async def fetch_content(request: LocalRequest):
            try:
                headers = self.get_default_headers()
                if request.headers:
                    headers.update(request.headers)
                
                async with httpx.AsyncClient(
                    timeout=request.timeout,
                    follow_redirects=request.follow_redirects,
                    max_redirects=request.max_redirects
                ) as client:
                    response = await client.get(request.url, headers=headers)
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "content": response.text,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "url": str(response.url),
                        "timestamp": asyncio.get_event_loop().time()
                    }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
        
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "local_mcp"
            }

if __name__ == "__main__":
    server = LocalMCPServer()
    uvicorn.run(server.app, host="0.0.0.0", port=8080)
```

## 4. MCP客户端集成

### 4.1 MCP服务管理器

创建 `mcp_service.py`：

```python
import asyncio
import json
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

class MCPServiceManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_service = BrowserMCPService(config.get('browser_mcp', {}))
        self.local_service = LocalMCPService(config.get('local_mcp', {}))
        self.enabled = config.get('mcp_services', {}).get('enabled', True)
        self.priority = config.get('mcp_services', {}).get('priority', ['browser', 'local'])
        self.fallback = config.get('mcp_services', {}).get('fallback', True)
    
    async def fetch_content(self, url: str, platform: str = None, **kwargs) -> Dict[str, Any]:
        """获取网页内容，支持智能路由和故障转移"""
        if not self.enabled:
            raise Exception("MCP services are disabled")
        
        # 根据平台选择服务
        services = self._get_services_for_platform(platform)
        
        last_error = None
        for service_name in services:
            try:
                service = getattr(self, f"{service_name}_service")
                result = await service.fetch_content(url, **kwargs)
                
                if result.get('success'):
                    result['service_used'] = service_name
                    return result
                else:
                    last_error = result.get('error', 'Unknown error')
            
            except Exception as e:
                last_error = str(e)
                if not self.fallback:
                    break
                continue
        
        raise Exception(f"All MCP services failed. Last error: {last_error}")
    
    def _get_services_for_platform(self, platform: str) -> List[str]:
        """根据平台选择合适的服务"""
        # JavaScript重度平台优先使用浏览器服务
        js_heavy_platforms = ['weibo', 'bilibili', 'xiaohongshu', 'douyin']
        
        if platform in js_heavy_platforms:
            return ['browser', 'local'] if self.fallback else ['browser']
        else:
            return self.priority
    
    async def get_service_status(self) -> Dict[str, Any]:
        """获取所有服务状态"""
        browser_status = await self.browser_service.get_status()
        local_status = await self.local_service.get_status()
        
        return {
            'browser': browser_status,
            'local': local_status,
            'enabled': self.enabled,
            'priority': self.priority,
            'fallback': self.fallback
        }

class BrowserMCPService:
    def __init__(self, config: Dict[str, Any]):
        self.endpoint = config.get('endpoint', 'http://localhost:3000')
        self.timeout = config.get('timeout', 30)
        self.last_used = None
    
    async def fetch_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """通过浏览器MCP服务获取内容"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                'url': url,
                'timeout': kwargs.get('timeout', 30000),
                'viewport': kwargs.get('viewport', {'width': 1920, 'height': 1080}),
                'wait_for': kwargs.get('wait_for'),
                'headers': kwargs.get('headers'),
                'javascript': kwargs.get('javascript')
            }
            
            response = await client.post(f"{self.endpoint}/fetch", json=payload)
            response.raise_for_status()
            
            self.last_used = datetime.now()
            return response.json()
    
    async def get_status(self) -> Dict[str, Any]:
        """获取浏览器服务状态"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.endpoint}/health")
                response.raise_for_status()
                
                return {
                    'available': True,
                    'status': 'healthy',
                    'last_used': self.last_used.isoformat() if self.last_used else None,
                    'endpoint': self.endpoint
                }
        except Exception as e:
            return {
                'available': False,
                'status': f'error: {str(e)}',
                'last_used': self.last_used.isoformat() if self.last_used else None,
                'endpoint': self.endpoint
            }

class LocalMCPService:
    def __init__(self, config: Dict[str, Any]):
        self.endpoint = config.get('endpoint', 'http://localhost:8080')
        self.timeout = config.get('timeout', 30)
        self.last_used = None
    
    async def fetch_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """通过本地MCP服务获取内容"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                'url': url,
                'timeout': kwargs.get('timeout', 30),
                'headers': kwargs.get('headers'),
                'follow_redirects': kwargs.get('follow_redirects', True),
                'max_redirects': kwargs.get('max_redirects', 5)
            }
            
            response = await client.post(f"{self.endpoint}/fetch", json=payload)
            response.raise_for_status()
            
            self.last_used = datetime.now()
            return response.json()
    
    async def get_status(self) -> Dict[str, Any]:
        """获取本地服务状态"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.endpoint}/health")
                response.raise_for_status()
                
                return {
                    'available': True,
                    'status': 'healthy',
                    'last_used': self.last_used.isoformat() if self.last_used else None,
                    'endpoint': self.endpoint
                }
        except Exception as e:
            return {
                'available': False,
                'status': f'error: {str(e)}',
                'last_used': self.last_used.isoformat() if self.last_used else None,
                'endpoint': self.endpoint
            }
```

## 5. 配置文件详解

### 5.1 MCP配置文件结构

创建 `mcp_config.json`：

```json
{
  "mcp_services": {
    "enabled": true,
    "service_priority": ["browser_mcp", "local_mcp"],
    "fallback_enabled": true,
    "default_timeout": 30,
    "max_retries": 3
  },
  "browser_mcp": {
    "mcp_endpoint": "http://localhost:3000/mcp",
    "timeout": 45,
    "max_retries": 3,
    "default_viewport": {
      "width": 1920,
      "height": 1080
    },
    "default_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "stealth_mode": true,
    "screenshot_enabled": false,
    "pdf_enabled": false,
    "platform_configs": {
      "weibo": {
        "wait_for": "networkidle",
        "timeout": 60000,
        "viewport": {"width": 1920, "height": 1080},
        "headers": {
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
          "Accept-Encoding": "gzip, deflate, br",
          "Cache-Control": "no-cache",
          "Pragma": "no-cache"
        },
        "javascript": [
          "console.log('微博页面MCP处理开始...');",
          "await new Promise(resolve => setTimeout(resolve, 5000));",
          "// 等待微博内容加载",
          "const weiboSelectors = ['.WB_detail', '.WB_feed_detail', '.WB_cardwrap'];",
          "let contentFound = false;",
          "for (let attempt = 0; attempt < 10; attempt++) {",
          "  for (const selector of weiboSelectors) {",
          "    if (document.querySelectorAll(selector).length > 0) {",
          "      contentFound = true;",
          "      break;",
          "    }",
          "  }",
          "  if (contentFound) break;",
          "  await new Promise(resolve => setTimeout(resolve, 2000));",
          "}",
          "console.log('微博页面MCP处理完成');"
        ]
      },
      "bilibili": {
        "wait_for": "networkidle",
        "timeout": 45000,
        "viewport": {"width": 1920, "height": 1080},
        "headers": {
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
          "Referer": "https://www.bilibili.com/"
        },
        "javascript": [
          "console.log('B站页面MCP处理开始...');",
          "document.querySelectorAll('video').forEach(v => v.pause());",
          "await new Promise(resolve => setTimeout(resolve, 3000));",
          "console.log('B站页面MCP处理完成');"
        ]
      }
    }
  },
  "local_mcp": {
    "mcp_endpoint": "http://localhost:8080/mcp",
    "timeout": 20,
    "max_retries": 2,
    "default_headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      "Accept-Encoding": "gzip, deflate, br",
      "DNT": "1",
      "Connection": "keep-alive",
      "Upgrade-Insecure-Requests": "1"
    },
    "follow_redirects": true,
    "verify_ssl": true,
    "platform_configs": {
      "general": {
        "timeout": 15,
        "headers": {
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
      },
      "news": {
        "timeout": 20,
        "headers": {
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
          "Cache-Control": "no-cache"
        }
      }
    }
  },
  "crawl4ai_integration": {
    "enabled": true,
    "process_mcp_content": true,
    "content_validation": {
      "min_content_length": 100,
      "required_tags": ["title", "body"],
      "exclude_empty_content": true
    },
    "extraction_config": {
      "word_count_threshold": 10,
      "extract_links": true,
      "extract_images": true,
      "extract_metadata": true,
      "clean_html": true
    },
    "platform_extraction": {
      "weibo": {
        "css_selectors": [
          ".WB_detail .WB_text",
          ".WB_feed_detail .WB_text",
          ".WB_cardwrap .WB_text",
          ".WB_text",
          ".weibo-text"
        ],
        "exclude_selectors": [
          ".WB_expand",
          ".WB_media_a",
          ".WB_func"
        ]
      },
      "bilibili": {
        "css_selectors": [
          ".video-info-title",
          ".video-title",
          ".video-desc .desc-info",
          ".up-info .up-name"
        ],
        "exclude_selectors": [
          ".video-toolbar",
          ".video-share",
          ".video-like"
        ]
      }
    }
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "mcp_service.log",
    "max_size": "10MB",
    "backup_count": 5
  }
}
```

### 5.2 配置参数说明

#### 5.2.1 MCP服务全局配置
* **mcp_services.enabled**: 是否启用MCP服务
* **mcp_services.service_priority**: 服务优先级顺序，支持 `["browser_mcp", "local_mcp"]`
* **mcp_services.fallback_enabled**: 是否启用故障转移机制
* **mcp_services.default_timeout**: 默认超时时间（秒）
* **mcp_services.max_retries**: 最大重试次数

#### 5.2.2 浏览器MCP配置
* **browser_mcp.mcp_endpoint**: 浏览器MCP服务端点地址
* **browser_mcp.timeout**: 请求超时时间（秒）
* **browser_mcp.max_retries**: 最大重试次数
* **browser_mcp.default_viewport**: 默认浏览器视口大小
* **browser_mcp.default_user_agent**: 默认用户代理字符串
* **browser_mcp.stealth_mode**: 是否启用隐身模式，避免反爬虫检测
* **browser_mcp.screenshot_enabled**: 是否启用截图功能
* **browser_mcp.pdf_enabled**: 是否启用PDF生成功能
* **browser_mcp.platform_configs**: 平台特定配置
  * **wait_for**: 等待条件（如 `"networkidle"` 或特定选择器）
  * **timeout**: 平台特定超时时间（毫秒）
  * **viewport**: 平台特定视口大小
  * **headers**: 平台特定HTTP头部
  * **javascript**: 平台特定JavaScript代码数组

#### 5.2.3 本地MCP配置
* **local_mcp.mcp_endpoint**: 本地MCP服务端点地址
* **local_mcp.timeout**: 请求超时时间（秒）
* **local_mcp.max_retries**: 最大重试次数
* **local_mcp.default_headers**: 默认HTTP请求头
* **local_mcp.follow_redirects**: 是否跟随重定向
* **local_mcp.verify_ssl**: 是否验证SSL证书
* **local_mcp.platform_configs**: 平台特定配置

#### 5.2.4 Crawl4AI集成配置
* **crawl4ai_integration.enabled**: 是否启用Crawl4AI集成
* **crawl4ai_integration.process_mcp_content**: 是否处理MCP获取的内容
* **crawl4ai_integration.content_validation**: 内容验证配置
  * **min_content_length**: 最小内容长度
  * **required_tags**: 必需的HTML标签
  * **exclude_empty_content**: 是否排除空内容
* **crawl4ai_integration.extraction_config**: 提取配置
  * **word_count_threshold**: 词数阈值
  * **extract_links**: 是否提取链接
  * **extract_images**: 是否提取图片
  * **extract_metadata**: 是否提取元数据
  * **clean_html**: 是否清理HTML
* **crawl4ai_integration.platform_extraction**: 平台特定提取配置
  * **css_selectors**: CSS选择器数组，用于提取内容
  * **exclude_selectors**: 排除的CSS选择器数组

#### 5.2.5 日志配置
* **logging.level**: 日志级别（DEBUG, INFO, WARNING, ERROR）
* **logging.format**: 日志格式字符串
* **logging.file**: 日志文件路径
* **logging.max_size**: 日志文件最大大小
* **logging.backup_count**: 日志文件备份数量

## 6. 启动和运行

### 6.1 启动MCP服务器

```bash
# 启动浏览器MCP服务器
python browser_mcp_server.py

# 启动本地MCP服务器
python local_mcp_server.py

# 启动主应用程序
python main.py
```

### 6.2 服务验证

#### 6.2.1 健康检查

```python
import asyncio
import httpx

async def test_mcp_services():
    # 测试浏览器服务
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:3000/health")
            print(f"Browser MCP: {response.json()}")
        except Exception as e:
            print(f"Browser MCP Error: {e}")
        
        try:
            response = await client.get("http://localhost:8080/health")
            print(f"Local MCP: {response.json()}")
        except Exception as e:
            print(f"Local MCP Error: {e}")
        
        # 测试主服务状态
        try:
            response = await client.get("http://localhost:8001/mcp/status")
            print(f"Main Service MCP Status: {response.json()}")
        except Exception as e:
            print(f"Main Service Error: {e}")

# 运行测试
asyncio.run(test_mcp_services())
```

#### 6.2.2 功能测试

```python
import asyncio
import httpx

async def test_mcp_crawling():
    """测试MCP爬虫功能"""
    async with httpx.AsyncClient(timeout=60) as client:
        # 测试单个URL爬取
        test_url = "https://example.com"
        
        payload = {
            "url": test_url,
            "platform": "general",
            "use_mcp": True
        }
        
        try:
            response = await client.post(
                "http://localhost:8001/crawl",
                json=payload
            )
            result = response.json()
            
            if result.get("success"):
                print(f"✅ 爬取成功: {test_url}")
                print(f"服务类型: {result.get('mcp_service_used', 'unknown')}")
                print(f"内容长度: {len(result.get('content', ''))}")
                print(f"标题: {result.get('title', 'N/A')}")
            else:
                print(f"❌ 爬取失败: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ 请求异常: {e}")

# 运行功能测试
asyncio.run(test_mcp_crawling())
```

#### 6.2.3 批量测试

```python
import asyncio
import httpx

async def test_batch_crawling():
    """测试批量爬取功能"""
    async with httpx.AsyncClient(timeout=120) as client:
        test_urls = [
            {"url": "https://example.com", "platform": "general"},
            {"url": "https://httpbin.org/html", "platform": "general"},
        ]
        
        payload = {
            "urls": test_urls,
            "use_mcp": True,
            "max_concurrent": 2
        }
        
        try:
            response = await client.post(
                "http://localhost:8001/batch_crawl",
                json=payload
            )
            result = response.json()
            
            print(f"批量爬取结果:")
            print(f"总数: {result.get('total', 0)}")
            print(f"成功: {result.get('successful', 0)}")
            print(f"失败: {result.get('failed', 0)}")
            
            for item in result.get('results', []):
                status = "✅" if item.get('success') else "❌"
                print(f"{status} {item.get('url')}: {item.get('title', 'N/A')}")
                
        except Exception as e:
            print(f"❌ 批量请求异常: {e}")

# 运行批量测试
asyncio.run(test_batch_crawling())
```

## 7. 调试和测试

### 7.1 日志配置

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcp_service.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 7.2 性能监控

```python
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {e}")
            raise
    return wrapper
```

### 7.3 单元测试

```python
import pytest
import asyncio
from mcp_service import MCPServiceManager

@pytest.mark.asyncio
async def test_mcp_fetch_content():
    config = {
        'mcp_services': {'enabled': True, 'priority': ['local', 'browser']},
        'browser_mcp': {'endpoint': 'http://localhost:3000'},
        'local_mcp': {'endpoint': 'http://localhost:8080'}
    }
    
    manager = MCPServiceManager(config)
    result = await manager.fetch_content('https://example.com')
    
    assert result['success'] is True
    assert 'content' in result
    assert 'service_used' in result
```

## 8. 常见问题和解决方案

### 8.1 连接问题

**问题**: MCP服务器无法连接
**解决方案**:

1. 检查服务器是否正在运行
2. 验证端口是否被占用
3. 检查防火墙设置
4. 确认配置文件中的端点地址正确

### 8.2 性能问题

**问题**: 响应时间过长
**解决方案**:

1. 调整超时设置
2. 优化浏览器配置
3. 使用连接池
4. 实现缓存机制

### 8.3 内存泄漏

**问题**: 长时间运行后内存占用过高
**解决方案**:

1. 确保正确关闭浏览器实例
2. 定期重启服务
3. 监控资源使用情况
4. 实现资源清理机制

### 8.4 反爬虫检测

**问题**: 被目标网站检测为爬虫
**解决方案**:

1. 使用随机User-Agent
2. 添加请求延迟
3. 使用代理IP
4. 模拟真实用户行为

## 9. 最佳实践

### 9.1 错误处理

* 实现完善的异常捕获机制

* 提供详细的错误信息

* 实现自动重试逻辑

* 记录错误日志用于调试

### 9.2 性能优化

* 使用异步编程提高并发性能

* 实现连接池减少连接开销

* 添加缓存机制避免重复请求

* 监控和分析性能指标

### 9.3 安全考虑

* 验证输入参数防止注入攻击

* 限制访问频率防止滥用

* 使用HTTPS确保通信安全

* 定期更新依赖包修复安全漏洞

### 9.4 可维护性

* 编写清晰的文档和注释

* 使用配置文件管理参数

* 实现模块化设计便于扩展

* 编写单元测试确保代码质量

## 10. 完整部署示例

### 10.1 项目结构

```
crawler-service/
├── main.py                    # 主服务入口
├── mcp_service.py            # MCP服务管理器
├── browser_mcp_server.py     # 浏览器MCP服务器
├── local_mcp_server.py       # 本地MCP服务器
├── mcp_config.json          # MCP配置文件
├── requirements.txt         # Python依赖
├── start_services.py        # 服务启动脚本
└── logs/                    # 日志目录
    ├── main_service.log
    ├── browser_mcp.log
    └── local_mcp.log
```

### 10.2 服务启动脚本

创建 `start_services.py`：

```python
import asyncio
import subprocess
import time
import sys
import os
from pathlib import Path

class MCPServiceLauncher:
    def __init__(self):
        self.processes = []
        self.base_dir = Path(__file__).parent
    
    def start_browser_mcp(self):
        """启动浏览器MCP服务"""
        print("🚀 启动浏览器MCP服务...")
        process = subprocess.Popen([
            sys.executable, "browser_mcp_server.py"
        ], cwd=self.base_dir)
        self.processes.append(('browser_mcp', process))
        return process
    
    def start_local_mcp(self):
        """启动本地MCP服务"""
        print("🚀 启动本地MCP服务...")
        process = subprocess.Popen([
            sys.executable, "local_mcp_server.py"
        ], cwd=self.base_dir)
        self.processes.append(('local_mcp', process))
        return process
    
    def start_main_service(self):
        """启动主服务"""
        print("🚀 启动主爬虫服务...")
        process = subprocess.Popen([
            sys.executable, "main.py"
        ], cwd=self.base_dir)
        self.processes.append(('main_service', process))
        return process
    
    async def wait_for_service(self, url, service_name, max_attempts=30):
        """等待服务启动"""
        import httpx
        
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        print(f"✅ {service_name} 服务已就绪")
                        return True
            except:
                pass
            
            print(f"⏳ 等待 {service_name} 启动... ({attempt + 1}/{max_attempts})")
            await asyncio.sleep(2)
        
        print(f"❌ {service_name} 启动超时")
        return False
    
    async def start_all_services(self):
        """启动所有服务"""
        print("🎯 开始启动MCP集成爬虫服务...")
        
        # 启动MCP服务
        self.start_browser_mcp()
        self.start_local_mcp()
        
        # 等待MCP服务启动
        await asyncio.sleep(5)
        
        # 检查MCP服务状态
        browser_ready = await self.wait_for_service(
            "http://localhost:3000/health", "浏览器MCP"
        )
        local_ready = await self.wait_for_service(
            "http://localhost:8080/health", "本地MCP"
        )
        
        if browser_ready and local_ready:
            # 启动主服务
            self.start_main_service()
            
            # 等待主服务启动
            main_ready = await self.wait_for_service(
                "http://localhost:8001/health", "主爬虫服务"
            )
            
            if main_ready:
                print("🎉 所有服务启动成功！")
                print("📊 服务状态:")
                print("   - 浏览器MCP: http://localhost:3000")
                print("   - 本地MCP: http://localhost:8080")
                print("   - 主服务: http://localhost:8001")
                print("   - API文档: http://localhost:8001/docs")
                return True
        
        print("❌ 服务启动失败")
        self.stop_all_services()
        return False
    
    def stop_all_services(self):
        """停止所有服务"""
        print("🛑 停止所有服务...")
        for name, process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=10)
                print(f"✅ {name} 已停止")
            except:
                try:
                    process.kill()
                    print(f"🔪 强制停止 {name}")
                except:
                    print(f"❌ 无法停止 {name}")
    
    def run(self):
        """运行服务启动器"""
        try:
            success = asyncio.run(self.start_all_services())
            if success:
                print("\n按 Ctrl+C 停止所有服务")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号...")
        finally:
            self.stop_all_services()

if __name__ == "__main__":
    launcher = MCPServiceLauncher()
    launcher.run()
```

### 10.3 一键启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动所有服务
python start_services.py
```

### 10.4 Docker部署（可选）

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安装Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 3000 8080 8001

# 启动服务
CMD ["python", "start_services.py"]
```

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  mcp-crawler:
    build: .
    ports:
      - "3000:3000"  # 浏览器MCP
      - "8080:8080"  # 本地MCP
      - "8001:8001"  # 主服务
    volumes:
      - ./logs:/app/logs
      - ./mcp_config.json:/app/mcp_config.json
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

## 11. 扩展功能

### 11.1 添加新的MCP服务

```python
class CustomMCPService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoint = config.get('endpoint')
        self.timeout = config.get('timeout', 30)
    
    async def fetch_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """实现自定义内容获取逻辑"""
        # 示例：调用第三方API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.endpoint}/custom_fetch",
                json={"url": url, **kwargs}
            )
            return response.json()
    
    async def get_status(self) -> Dict[str, Any]:
        """实现状态检查"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.endpoint}/health")
                return {
                    'available': True,
                    'status': 'healthy',
                    'endpoint': self.endpoint
                }
        except Exception as e:
            return {
                'available': False,
                'status': f'error: {str(e)}',
                'endpoint': self.endpoint
            }
```

### 11.2 集成其他协议
- **WebSocket实时通信**: 支持实时数据推送
- **GraphQL查询**: 灵活的数据查询接口
- **gRPC支持**: 高性能的服务间通信
- **消息队列集成**: 异步任务处理

### 11.3 监控和告警

```python
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge

# 定义监控指标
REQUEST_COUNT = Counter('mcp_requests_total', 'Total MCP requests', ['service', 'status'])
REQUEST_DURATION = Histogram('mcp_request_duration_seconds', 'MCP request duration')
ACTIVE_CONNECTIONS = Gauge('mcp_active_connections', 'Active MCP connections')

class MonitoringMixin:
    def record_request(self, service: str, status: str, duration: float):
        REQUEST_COUNT.labels(service=service, status=status).inc()
        REQUEST_DURATION.observe(duration)
```

通过本指南，开发者可以完整地理解和实现MCP集成，构建高效、可靠、可扩展的网页内容获取系统。
