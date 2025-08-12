import asyncio
import logging
import platform
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
import html2text
import re
import json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.chunking_strategy import RegexChunking
from storage import get_storage_client

# Windows上的asyncio事件循环策略修复
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 配置加载 ====================

def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"配置文件加载成功: {config_path}")
            return config
    except FileNotFoundError:
        logger.warning(f"配置文件未找到: {config_path}，使用默认配置")
        return {
            "server": {"port": 8001, "host": "0.0.0.0", "reload": False},
            "crawler": {"log_level": "INFO"}
        }
    except json.JSONDecodeError as e:
        logger.error(f"配置文件格式错误: {e}")
        return {
            "server": {"port": 8001, "host": "0.0.0.0", "reload": False},
            "crawler": {"log_level": "INFO"}
        }

# 加载配置
app_config = load_config()

# ==================== 数据模型 ====================

class CrawlRequest(BaseModel):
    url: str
    extract_content: bool = True
    extract_links: bool = False
    css_selector: str = None
    word_count_threshold: int = 10

class CrawlResponse(BaseModel):
    url: str
    title: str
    content: str
    markdown: str
    links: List[str] = []
    crawled_at: datetime
    success: bool
    error_message: str = None

class PostData(BaseModel):
    title: str
    content: str
    author: str
    platform: str
    url: str
    published_at: Optional[datetime] = None
    tags: List[str] = []
    images: List[str] = []
    video_url: Optional[str] = None

class PlatformCrawlRequest(BaseModel):
    creator_url: str  # 可以是URL或搜索关键词
    platform: str
    limit: int = 10

class SearchRequest(BaseModel):
    query: str
    platform: str
    limit: int = 10

# ==================== 核心爬虫服务 ====================

class UnifiedCrawlerService:
    """统一爬虫服务，整合所有爬虫功能"""
    
    def __init__(self):
        self.session = None
        self.crawler = None
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self._initialized = False
        
    async def ensure_initialized(self):
        """确保服务已初始化"""
        if not self._initialized:
            await self.initialize()
            self._initialized = True
        
    async def initialize(self):
        """初始化爬虫服务"""
        try:
            # 初始化传统requests session
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # 使用优化的BrowserConfig配置浏览器，启用隐身模式和反机器人检测
            browser_config = BrowserConfig(
                browser_type="chromium",
                headless=False,  # 非无头模式更难被检测
                enable_stealth=True,  # 启用隐身模式
                viewport_width=1920,
                viewport_height=1080,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                user_agent_mode="random",  # 随机化用户代理
                ignore_https_errors=True,
                java_script_enabled=True,
                text_mode=False,  # 保持图片加载以避免检测
                light_mode=False,
                verbose=True,
                # 优化的浏览器参数，提升性能和稳定性
                extra_args=[
                    # 基础安全和沙箱设置
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    
                    # 反自动化检测
                    "--disable-blink-features=AutomationControlled",
                    "--exclude-switches=enable-automation",
                    "--disable-extensions-except=*",
                    "--disable-plugins-discovery",
                    
                    # 性能优化
                    "--no-first-run",
                    "--disable-default-apps",
                    "--disable-infobars",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-field-trial-config",
                    "--disable-back-forward-cache",
                    "--disable-ipc-flooding-protection",
                    "--disable-component-update",
                    "--disable-domain-reliability",
                    "--disable-background-networking",
                    "--disable-preconnect",
                    "--disable-hang-monitor",
                    
                    # 网络和SSL设置
                    "--ignore-certificate-errors",
                    "--ignore-ssl-errors",
                    "--ignore-certificate-errors-spki-list",
                    "--ignore-certificate-errors-ssl-errors",
                    "--allow-running-insecure-content",
                    "--disable-popup-blocking",
                    
                    # 隐私和跟踪设置
                    "--disable-sync",
                    "--disable-translate",
                    "--metrics-recording-only",
                    "--no-default-browser-check",
                    "--no-pings",
                    "--password-store=basic",
                    "--use-mock-keychain",
                    
                    # 媒体和音频设置
                    "--mute-audio",
                    "--autoplay-policy=no-user-gesture-required",
                    
                    # 渲染和显示优化
                    "--enable-features=NetworkService,NetworkServiceLogging",
                    "--force-color-profile=srgb",
                    "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                    "--disable-component-extensions-with-background-pages",
                    
                    # 内存和资源管理
                    "--max_old_space_size=4096",
                    "--memory-pressure-off",
                    "--disable-background-media-suspend",
                    
                    # 中文网站优化
                    "--lang=zh-CN",
                    "--accept-lang=zh-CN,zh,en-US,en",
                    "--disable-features=VizDisplayCompositor,AudioServiceOutOfProcess",
                    
                    # GPU和硬件加速
                    "--disable-gpu-sandbox",
                    "--enable-gpu-rasterization",
                    "--enable-zero-copy"
                ],
                # 优化的请求头，模拟真实浏览器行为
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "max-age=0",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "Connection": "keep-alive",
                    "Sec-Ch-Ua": '"Chromium";v="120", "Not_A Brand";v="99", "Google Chrome";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Ch-Ua-Platform-Version": '"15.0.0"',
                    "Sec-Ch-Ua-Arch": '"x86"',
                    "Sec-Ch-Ua-Model": '"",',
                    "Sec-Ch-Ua-Bitness": '"64"',
                    "Sec-Ch-Ua-Wow64": "?0",
                    "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="120.0.6099.109", "Not_A Brand";v="99.0.0.0", "Google Chrome";v="120.0.6099.109"',
                    # 中文网站特定头部
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://weibo.com",
                    "Referer": "https://weibo.com/"
                }
            )
            
            # 初始化crawl4ai异步爬虫
            self.crawler = AsyncWebCrawler(config=browser_config)
            await self.crawler.start()
            
            logger.info("统一爬虫服务初始化成功")
        except Exception as e:
            logger.error(f"初始化爬虫服务失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.session:
                self.session.close()
            if self.crawler:
                await self.crawler.close()
            logger.info("统一爬虫服务清理完成")
        except Exception as e:
            logger.error(f"清理过程中出错: {e}")

    def extract_content(self, soup: BeautifulSoup, css_selector: Optional[str] = None) -> str:
        """提取页面内容"""
        if css_selector:
            content_elements = soup.select(css_selector)
            if content_elements:
                return ' '.join([elem.get_text(strip=True) for elem in content_elements])
        
        # 默认提取策略
        # 移除脚本和样式
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # 寻找主要内容区域
        main_selectors = [
            'main', 'article', '.content', '.post-content', 
            '.article-content', '.news-content', '#content',
            '.entry-content', '.post-body'
        ]
        
        for selector in main_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return content_elem.get_text(strip=True)
        
        # 如果没有找到主要内容区域，返回body内容
        body = soup.find('body')
        if body:
            return body.get_text(strip=True)
        
        return soup.get_text(strip=True)

    async def crawl_platform_direct(self, creator_url: str, platform: str, limit: int = 10) -> List[PostData]:
        """直接使用crawl4ai爬取平台内容"""
        results = []
        
        # 生成目标URL列表
        target_urls = self._generate_platform_urls(creator_url, platform)
        
        for url in target_urls[:3]:  # 限制URL数量
            try:
                logger.info(f"开始爬取URL: {url}")
                post_data = await self._extract_with_crawl4ai(url, platform)
                if post_data:
                    results.extend(post_data)
                    
                if len(results) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"爬取URL失败 {url}: {e}")
                continue
        
        # 去重和质量过滤
        filtered_results = self._filter_and_deduplicate(results, creator_url)
        
        return filtered_results[:limit]

    def _generate_platform_urls(self, creator_url: str, platform: str) -> List[str]:
        """根据平台和创作者信息生成动态内容URL列表，直接访问平台页面而不是搜索引擎"""
        import re
        urls = []
        
        if creator_url.startswith('http'):
            # 如果已经是URL，检查是否为动态内容页面
            if self._is_dynamic_content_url(creator_url):
                urls.append(creator_url)
        else:
            # 根据平台生成直接的动态内容URL
            if platform == 'weibo':
                # 微博动态内容：直接访问微博用户的动态页面，而不是静态主页
                if creator_url.isdigit():  # 如果是用户ID
                    urls.extend([
                        f"https://weibo.com/u/{creator_url}/home",        # 用户动态页面
                        f"https://weibo.com/u/{creator_url}?tabtype=feed", # 用户微博动态
                        f"https://weibo.com/{creator_url}?is_all=1"       # 全部微博
                    ])
                else:  # 如果是用户名或昵称
                    # 对于非数字的用户标识符，需要更谨慎的处理
                    validated_urls = self._validate_weibo_user_identifier(creator_url)
                    if validated_urls:
                        urls.extend(validated_urls)
                    else:
                        # 如果用户标识符无效，尝试生成通用的用户页面URL
                        logger.warning(f"微博用户标识符验证失败: {creator_url}，尝试生成通用用户页面")
                        # 清理用户标识符，移除特殊字符
                        cleaned_identifier = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff-]', '', creator_url)
                        if cleaned_identifier:
                            urls.extend([
                                f"https://weibo.com/{cleaned_identifier}?tabtype=feed",  # 用户微博动态
                                f"https://weibo.com/n/{cleaned_identifier}",  # 昵称格式
                                f"https://weibo.com/{cleaned_identifier}"  # 基本用户页面
                            ])
                        else:
                            # 如果完全无法处理，跳过该创作者
                            logger.error(f"无法处理的微博用户标识符: {creator_url}，跳过爬取")
                            return []
            elif platform == 'bilibili':
                # B站动态内容：直接访问B站用户空间和动态页面
                if creator_url.isdigit():  # 如果是用户UID
                    urls.extend([
                        f"https://space.bilibili.com/{creator_url}/dynamic",
                        f"https://space.bilibili.com/{creator_url}/video",
                        f"https://space.bilibili.com/{creator_url}"
                    ])
                else:  # 如果是用户名或其他标识
                    urls.extend([
                        "https://www.bilibili.com/v/popular/all",  # 热门视频
                        "https://t.bilibili.com",  # 动态页面
                        "https://www.bilibili.com/v/popular/weekly"  # 每周必看
                    ])
            elif platform == 'xiaohongshu':
                # 小红书动态内容：直接访问小红书用户页面和发现页
                if creator_url.startswith('xiaohongshu.com') or creator_url.startswith('xhslink.com'):
                    urls.append(creator_url)
                else:
                    urls.extend([
                        "https://www.xiaohongshu.com/explore",  # 发现页面
                        "https://www.xiaohongshu.com/explore/homefeed.json",  # 首页动态
                        f"https://www.xiaohongshu.com/user/profile/{creator_url}" if creator_url else "https://www.xiaohongshu.com/explore"
                    ])
            elif platform == 'douyin':
                # 抖音动态内容：直接访问抖音用户页面和推荐页
                if creator_url.startswith('@'):
                    username = creator_url[1:]  # 移除@符号
                    urls.extend([
                        f"https://www.douyin.com/@{username}",
                        f"https://www.douyin.com/user/{username}"
                    ])
                else:
                    urls.extend([
                        "https://www.douyin.com/recommend",  # 推荐页面
                        "https://www.douyin.com/hot",  # 热门内容
                        f"https://www.douyin.com/search/{creator_url}" if creator_url else "https://www.douyin.com/recommend"
                    ])
            else:
                # 默认情况：如果是URL直接使用，否则生成通用的动态内容页面
                if creator_url.startswith('http'):
                    urls.append(creator_url)
                else:
                    # 生成一些通用的内容发现页面
                    urls.extend([
                        "https://www.zhihu.com/hot",  # 知乎热榜
                        "https://weibo.com/hot/search",  # 微博热搜
                        "https://www.bilibili.com/v/popular/all"  # B站热门
                    ])
        
        # 过滤掉无效的URL
        valid_urls = []
        for url in urls:
            if self._is_valid_url(url):
                valid_urls.append(url)
            else:
                logger.warning(f"跳过无效URL: {url}")
        
        return valid_urls

    async def _check_page_stability(self, url: str, timeout: int = 15) -> bool:
        """检查页面是否稳定，避免在导航过程中获取内容，增强错误处理"""
        try:
            import asyncio
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True
                )
                page = await context.new_page()
                
                try:
                    # 设置更长的超时时间
                    page.set_default_timeout(timeout * 1000)
                    page.set_default_navigation_timeout(timeout * 1000)
                    
                    # 分阶段导航到页面
                    logger.debug(f"开始导航到页面: {url}")
                    await page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
                    
                    # 等待页面基本加载完成
                    await asyncio.sleep(3)
                    
                    # 多重稳定性检查
                    stable_checks = 0
                    max_checks = 8
                    
                    for check_round in range(max_checks):
                        try:
                            # 检查文档状态
                            ready_state = await page.evaluate('document.readyState')
                            
                            # 检查是否还有正在加载的资源
                            loading_resources = await page.evaluate('''
                                () => {
                                    const images = document.querySelectorAll('img');
                                    const scripts = document.querySelectorAll('script[src]');
                                    let loading = 0;
                                    
                                    images.forEach(img => {
                                        if (!img.complete) loading++;
                                    });
                                    
                                    return loading;
                                }
                            ''')
                            
                            # 检查页面内容是否稳定
                            content_length = await page.evaluate('document.body ? document.body.innerText.length : 0')
                            
                            if ready_state == 'complete' and loading_resources == 0 and content_length > 0:
                                stable_checks += 1
                                logger.debug(f"稳定性检查 {check_round + 1}/{max_checks}: 通过 (连续{stable_checks}次)")
                            else:
                                stable_checks = 0
                                logger.debug(f"稳定性检查 {check_round + 1}/{max_checks}: 未通过 (状态:{ready_state}, 加载中:{loading_resources}, 内容长度:{content_length})")
                            
                            # 连续3次稳定检查通过
                            if stable_checks >= 3:
                                logger.info(f"页面稳定性检查通过: {url}")
                                return True
                            
                            await asyncio.sleep(2)  # 增加检查间隔
                            
                        except Exception as eval_error:
                            logger.warning(f"稳定性检查执行异常: {eval_error}")
                            stable_checks = 0
                            await asyncio.sleep(1)
                    
                    logger.warning(f"页面稳定性检查超时: {url} (检查了{max_checks}轮)")
                    return False
                    
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower() or "navigation" in error_msg.lower():
                        logger.warning(f"页面导航超时，可能页面正在加载: {url} - {error_msg}")
                        return False
                    else:
                        logger.warning(f"页面稳定性检查异常: {url} - {error_msg}")
                        return False
                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass  # 忽略关闭浏览器时的异常
                    
        except Exception as e:
            logger.error(f"页面稳定性检查工具初始化失败: {str(e)}")
            return False  # 改为返回False，更加保守

    async def _extract_with_crawl4ai(self, url: str, platform: str, max_retries: int = 3) -> List[PostData]:
        """使用crawl4ai提取内容，带重试机制和增强的错误处理"""
        import asyncio
        import time
        
        # 确保服务已初始化
        await self.ensure_initialized()
        
        start_time = time.time()
        logger.info(f"开始crawl4ai爬取任务 - 平台: {platform}, URL: {url}")
        
        for attempt in range(max_retries):
            try:
                attempt_start = time.time()
                logger.info(f"crawl4ai爬取尝试 {attempt + 1}/{max_retries}: `{url}`")
                
                # 对于微博平台，先进行页面稳定性检查
                if platform == 'weibo' and attempt == 0:
                    logger.info(f"微博页面稳定性检查: {url}")
                    is_stable = await self._check_page_stability(url, timeout=15)
                    if not is_stable:
                        logger.warning(f"页面不稳定，等待额外时间: {url}")
                        await asyncio.sleep(10)  # 额外等待时间
                
                # 获取平台特定配置
                crawl_config = self._get_platform_crawl_config(platform)
                logger.debug(f"使用平台配置 {platform}: {crawl_config}")
                
                # 获取虚拟滚动配置 <mcreference link="https://docs.crawl4ai.com/api/parameters/" index="4">4</mcreference>
                virtual_scroll_config = self._get_virtual_scroll_config(platform, url)
                if virtual_scroll_config:
                    logger.info(f"启用虚拟滚动配置: {virtual_scroll_config}")
                
                # 使用新的CrawlerRunConfig配置爬取操作
                crawler_run_config_params = {
                    'cache_mode': CacheMode.BYPASS,  # 绕过缓存获取最新内容
                    'word_count_threshold': 10,
                    'wait_for': "networkidle",  # 等待网络空闲
                    'delay_before_return_html': 3.0,  # 返回HTML前等待3秒
                    'timeout': 60000,  # 60秒超时
                    'page_timeout': 90000,  # 页面超时90秒
                    'navigation_timeout': 45000,  # 导航超时45秒
                    'screenshot': False,  # 暂时禁用截图以提高性能
                    'process_iframes': True,
                    'remove_overlay_elements': True,
                    'simulate_user': True,
                    'override_navigator': True,
                    'scan_full_page': True,  # 启用全页扫描以处理懒加载内容
                    'wait_for_images': True,  # 等待图片加载完成
                    'scroll_delay': 1.0,  # 滚动间隔延迟
                    # 启用网络请求监控和控制台消息捕获
                    'capture_network_requests': True,  # 捕获所有网络请求
                    'capture_console_messages': True  # 捕获控制台消息
                }
                
                # 如果需要虚拟滚动，添加虚拟滚动配置
                if virtual_scroll_config:
                    from crawl4ai import VirtualScrollConfig
                    crawler_run_config_params['virtual_scroll_config'] = VirtualScrollConfig(
                        container_selector=virtual_scroll_config['container_selector'],
                        scroll_count=virtual_scroll_config['scroll_count'],
                        scroll_by=virtual_scroll_config['scroll_by'],
                        wait_after_scroll=virtual_scroll_config['wait_after_scroll']
                    )
                    # 虚拟滚动时禁用scan_full_page，避免冲突
                    crawler_run_config_params['scan_full_page'] = False
                    logger.info(f"虚拟滚动配置已应用: 容器={virtual_scroll_config['container_selector']}, 滚动次数={virtual_scroll_config['scroll_count']}")
                
                # 添加JavaScript代码到配置参数中
                crawler_run_config_params['js_code'] = [
                    "console.log('开始页面稳定化处理...');",
                    "// 等待页面基本加载完成",
                    "await new Promise(resolve => setTimeout(resolve, 3000));",
                    "// 检查并等待动态内容加载",
                    "let stabilityChecks = 0;",
                    "const maxChecks = 10;",
                    "while(stabilityChecks < maxChecks) {",
                    "  const currentLength = document.body ? document.body.innerText.length : 0;",
                    "  await new Promise(resolve => setTimeout(resolve, 1000));",
                    "  const newLength = document.body ? document.body.innerText.length : 0;",
                    "  if (Math.abs(newLength - currentLength) < 100) {",
                    "    stabilityChecks++;",
                    "  } else {",
                    "    stabilityChecks = 0;",
                    "  }",
                    "  if (stabilityChecks >= 3) break;",
                    "}",
                    "// 轻微滚动以触发懒加载内容",
                    "window.scrollTo(0, Math.min(500, document.body.scrollHeight * 0.3));",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "window.scrollTo(0, Math.min(1000, document.body.scrollHeight * 0.6));",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "window.scrollTo(0, 0);",
                    "await new Promise(resolve => setTimeout(resolve, 1000));",
                    "console.log('页面稳定化处理完成');"
                ]
                
                crawler_run_config = CrawlerRunConfig(**crawler_run_config_params)
                 

                
                logger.debug(f"开始执行crawl4ai.arun，使用优化的CrawlerRunConfig")
                
                # 特殊处理页面导航错误
                try:
                    result = await self.crawler.arun(
                        url=url,
                        config=crawler_run_config
                    )
                except Exception as crawl_error:
                    error_msg = str(crawl_error)
                    
                    # 增强的错误分类和检测机制
                    error_classification = self._classify_crawl_error(error_msg, url, platform)
                    logger.info(f"错误分类结果: {error_classification}")
                    
                    # 获取智能重试配置
                    retry_config = self._get_retry_config(error_classification, attempt, platform)
                    
                    if retry_config and attempt < max_retries:
                        logger.warning(f"检测到{error_classification['type']}错误，使用{error_classification['recovery_strategy']}策略重试")
                        logger.info(f"重试建议: {error_classification['suggestion']}")
                        
                        # 等待指定时间
                        await asyncio.sleep(retry_config['wait_time'])
                        
                        try:
                            # 使用智能配置重试
                            result = await self.crawler.arun(
                                url=url,
                                config=retry_config['config']
                            )
                            
                            if result and result.success:
                                logger.info(f"智能重试成功: {url} (策略: {error_classification['recovery_strategy']})")
                                # 继续处理成功的结果
                            else:
                                logger.warning(f"智能重试失败，继续下一次尝试")
                                continue
                                
                        except Exception as retry_error:
                            logger.warning(f"智能重试异常: {retry_error}")
                            # 如果智能重试也失败，继续下一次尝试
                            continue
                    else:
                        # 无法智能重试或已达到最大重试次数，抛出原始错误
                        raise crawl_error
                
                attempt_time = time.time() - attempt_start
                logger.info(f"crawl4ai执行完成，耗时: {attempt_time:.2f}秒")
                
                if result.success:
                    logger.info(f"crawl4ai成功爬取: {url}")
                    
                    # 分析网络请求和控制台消息
                    network_analysis = self._analyze_network_requests(result, url, platform)
                    if network_analysis:
                        logger.info(f"网络分析结果: {network_analysis}")
                    
                    # 详细记录提取结果
                    content_info = {
                        'html_length': len(result.html or ''),
                        'cleaned_html_length': len(result.cleaned_html or ''),
                        'markdown_length': len(result.markdown or ''),
                        'title': result.metadata.get('title', 'N/A') if result.metadata else 'N/A',
                        'status_code': getattr(result, 'status_code', 'N/A'),
                        'response_headers': getattr(result, 'response_headers', {})
                    }
                    logger.debug(f"crawl4ai提取详情: {content_info}")
                    
                    # 解析提取的内容
                    logger.debug(f"开始解析crawl4ai结果...")
                    posts = self._parse_crawl4ai_result(result, url, platform)
                    
                    if posts:  # 如果成功提取到内容，直接返回
                        total_time = time.time() - start_time
                        logger.info(f"crawl4ai任务成功完成，总耗时: {total_time:.2f}秒，提取到 {len(posts)} 条内容")
                        return posts
                    else:
                        logger.warning(f"crawl4ai爬取成功但未提取到有效内容: {url}")
                        logger.debug(f"原始HTML片段: {(result.html or '')[:500]}...")
                        logger.debug(f"清理后HTML片段: {(result.cleaned_html or '')[:500]}...")
                else:
                    error_msg = getattr(result, 'error_message', '未知错误')
                    status_code = getattr(result, 'status_code', 'N/A')
                    logger.error(f"crawl4ai爬取失败: {url} - 状态码: {status_code}, 错误: {error_msg}")
                    
                    # 记录更多调试信息
                    if hasattr(result, 'response_headers'):
                        logger.debug(f"响应头: {result.response_headers}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # 增加等待时间
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                attempt_time = time.time() - attempt_start
                logger.error(f"crawl4ai爬取异常 (尝试 {attempt + 1}/{max_retries}, 耗时: {attempt_time:.2f}秒): {url}")
                logger.error(f"异常类型: {type(e).__name__}, 异常信息: {str(e)}")
                
                # 记录详细的异常堆栈
                if attempt == max_retries - 1:  # 最后一次尝试时记录完整堆栈
                    logger.exception(f"crawl4ai最终失败，完整错误堆栈:")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"异常后等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
        
        total_time = time.time() - start_time
        logger.error(f"crawl4ai重试 {max_retries} 次后仍然失败: {url}, 总耗时: {total_time:.2f}秒")
        return []
    
    def _classify_crawl_error(self, error_msg: str, url: str, platform: str) -> dict:
        """智能错误分类和分析"""
        error_msg_lower = error_msg.lower()
        
        # 导航和页面状态错误
        navigation_patterns = [
            "page is navigating", "changing the content", "navigation timeout",
            "page.content: unable to retrieve content", "target closed",
            "execution context was destroyed", "page crashed", "page.goto",
            "navigation failed", "page not found"
        ]
        
        # 网络连接错误
        network_patterns = [
            "connection refused", "connection reset", "connection timeout",
            "network error", "dns resolution failed", "host unreachable",
            "connection aborted", "socket timeout", "ssl error"
        ]
        
        # 超时错误
        timeout_patterns = [
            "timeout", "timed out", "deadline exceeded", "request timeout",
            "response timeout", "operation timeout", "wait timeout"
        ]
        
        # 反爬虫检测错误
        bot_detection_patterns = [
            "access denied", "forbidden", "blocked", "captcha", "verification",
            "robot", "bot detected", "suspicious activity", "rate limit",
            "too many requests", "请验证", "验证码", "访问被拒绝"
        ]
        
        # 资源加载错误
        resource_patterns = [
            "failed to load", "resource not found", "script error",
            "stylesheet not loaded", "image load failed", "font load failed"
        ]
        
        # 权限和认证错误
        auth_patterns = [
            "unauthorized", "authentication required", "login required",
            "session expired", "invalid credentials", "access token"
        ]
        
        # 内容解析错误
        parsing_patterns = [
            "parse error", "invalid html", "malformed content",
            "encoding error", "charset error", "content type"
        ]
        
        # 分类逻辑
        if any(pattern in error_msg_lower for pattern in navigation_patterns):
            error_type = "navigation"
            severity = "medium"
            recovery_strategy = "multi_level_retry"
        elif any(pattern in error_msg_lower for pattern in network_patterns):
            error_type = "network"
            severity = "high"
            recovery_strategy = "network_retry"
        elif any(pattern in error_msg_lower for pattern in timeout_patterns):
            error_type = "timeout"
            severity = "medium"
            recovery_strategy = "timeout_retry"
        elif any(pattern in error_msg_lower for pattern in bot_detection_patterns):
            error_type = "bot_detection"
            severity = "high"
            recovery_strategy = "stealth_retry"
        elif any(pattern in error_msg_lower for pattern in resource_patterns):
            error_type = "resource"
            severity = "low"
            recovery_strategy = "resource_retry"
        elif any(pattern in error_msg_lower for pattern in auth_patterns):
            error_type = "auth"
            severity = "high"
            recovery_strategy = "auth_retry"
        elif any(pattern in error_msg_lower for pattern in parsing_patterns):
            error_type = "parsing"
            severity = "low"
            recovery_strategy = "parsing_retry"
        else:
            error_type = "unknown"
            severity = "medium"
            recovery_strategy = "default_retry"
        
        # 平台特定的错误处理建议
        platform_suggestions = {
            'weibo': {
                'navigation': '微博页面导航复杂，建议增加等待时间',
                'bot_detection': '微博反爬虫严格，建议使用更隐蔽的配置',
                'timeout': '微博加载较慢，建议增加超时时间'
            },
            'bilibili': {
                'navigation': 'B站视频页面加载复杂，建议暂停视频播放',
                'resource': 'B站资源较多，建议禁用部分资源加载',
                'timeout': 'B站内容丰富，建议增加处理时间'
            },
            'xiaohongshu': {
                'bot_detection': '小红书检测较严，建议模拟真实用户行为',
                'navigation': '小红书页面动态加载，建议增加滚动操作'
            },
            'douyin': {
                'navigation': '抖音页面复杂，建议暂停视频并增加等待',
                'bot_detection': '抖音反爬虫强，建议使用随机延迟'
            }
        }
        
        suggestion = platform_suggestions.get(platform, {}).get(error_type, '建议检查网络连接和页面状态')
        
        return {
             'type': error_type,
             'severity': severity,
             'recovery_strategy': recovery_strategy,
             'suggestion': suggestion,
             'platform': platform,
             'url': url,
             'original_error': error_msg
         }
    
    def _get_retry_config(self, error_info: dict, attempt: int, platform: str) -> dict:
        """根据错误类型和平台获取智能重试配置"""
        error_type = error_info['type']
        recovery_strategy = error_info['recovery_strategy']
        
        # 基础等待时间
        base_wait_times = {
            'network_retry': [5, 10, 20],
            'timeout_retry': [8, 15, 25],
            'stealth_retry': [10, 20, 30],
            'multi_level_retry': [8, 15, 20],
            'resource_retry': [3, 6, 12],
            'auth_retry': [5, 10, 15],
            'parsing_retry': [2, 4, 8],
            'default_retry': [5, 10, 15]
        }
        
        wait_time = base_wait_times.get(recovery_strategy, [5, 10, 15])[min(attempt, 2)]
        
        # 根据错误类型生成配置
        if error_type == 'network':
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=2,
                wait_for='domcontentloaded',
                timeout=90000 + (attempt * 30000),
                page_timeout=120000 + (attempt * 60000),
                navigation_timeout=60000 + (attempt * 30000),
                delay_before_return_html=10 + (attempt * 5),
                js_code=f"await new Promise(resolve => setTimeout(resolve, {5000 + attempt * 2000}));"
            )
        
        elif error_type == 'timeout':
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=1,
                wait_for='commit' if attempt > 1 else 'networkidle',
                timeout=120000 + (attempt * 60000),
                page_timeout=180000 + (attempt * 90000),
                navigation_timeout=90000 + (attempt * 45000),
                delay_before_return_html=20 + (attempt * 10),
                js_code=f"await new Promise(resolve => setTimeout(resolve, {10000 + attempt * 5000}));"
            )
        
        elif error_type == 'bot_detection':
            # 反爬虫检测需要更隐蔽的配置
            random_delay = 15000 + (attempt * 10000) + (hash(error_info['url']) % 5000)
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=1,
                wait_for='networkidle',
                timeout=150000,
                page_timeout=240000,
                navigation_timeout=120000,
                delay_before_return_html=25 + (attempt * 15),
                simulate_user=True,
                override_navigator=True,
                js_code=[
                    f"console.log('反检测模式 - 尝试 {attempt + 1}');",
                    f"await new Promise(resolve => setTimeout(resolve, {random_delay}));",
                    "// 模拟人类行为",
                    "if (Math.random() > 0.5) {",
                    "  window.scrollTo(0, Math.random() * 300);",
                    "  await new Promise(resolve => setTimeout(resolve, 2000));",
                    "}",
                    "// 随机鼠标移动",
                    "document.dispatchEvent(new MouseEvent('mousemove', {",
                    "  clientX: Math.random() * window.innerWidth,",
                    "  clientY: Math.random() * window.innerHeight",
                    "}));",
                    "await new Promise(resolve => setTimeout(resolve, 1000));"
                ]
            )
        
        elif error_type == 'resource':
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=2,
                wait_for='domcontentloaded',
                timeout=60000,
                page_timeout=90000,
                navigation_timeout=45000,
                delay_before_return_html=5,
                process_iframes=False,
                js_code="await new Promise(resolve => setTimeout(resolve, 3000));"
            )
        
        elif error_type == 'auth':
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=1,
                wait_for='networkidle',
                timeout=90000,
                page_timeout=120000,
                navigation_timeout=60000,
                delay_before_return_html=15,
                js_code=[
                    "console.log('认证错误重试模式');",
                    "await new Promise(resolve => setTimeout(resolve, 8000));",
                    "// 检查登录状态",
                    "if (document.querySelector('input[type=\"password\"]')) {",
                    "  console.log('检测到登录页面');",
                    "}"
                ]
            )
        
        elif error_type == 'parsing':
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=1,
                wait_for='domcontentloaded',
                timeout=45000,
                page_timeout=60000,
                navigation_timeout=30000,
                delay_before_return_html=3,
                js_code="await new Promise(resolve => setTimeout(resolve, 2000));"
            )
        
        else:  # navigation 或 unknown
            # 使用渐进式配置
            if attempt == 0:
                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=3,
                    wait_for='domcontentloaded',
                    timeout=60000,
                    page_timeout=90000,
                    navigation_timeout=45000,
                    delay_before_return_html=5,
                    js_code="await new Promise(resolve => setTimeout(resolve, 5000));"
                )
            elif attempt == 1:
                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=2,
                    wait_for='networkidle',
                    timeout=120000,
                    page_timeout=180000,
                    navigation_timeout=90000,
                    delay_before_return_html=20,
                    simulate_user=True,
                    js_code=[
                        "await new Promise(resolve => setTimeout(resolve, 10000));",
                        "window.scrollTo(0, 200);",
                        "await new Promise(resolve => setTimeout(resolve, 3000));",
                        "window.scrollTo(0, 0);"
                    ]
                )
            else:
                config = CrawlerRunConfig(
                    word_count_threshold=1,
                    bypass_cache=True,
                    wait_for='commit',
                    timeout=180000,
                    page_timeout=240000,
                    navigation_timeout=120000,
                    delay_before_return_html=30,
                    js_code="await new Promise(resolve => setTimeout(resolve, 15000));"
                )
        
        # 平台特定的配置调整
         if platform in ['weibo', 'xiaohongshu', 'douyin', 'bilibili']:
             # 中文平台需要更长的等待时间
             config.timeout = int(config.timeout * 1.5)
             config.page_timeout = int(config.page_timeout * 1.5)
             config.delay_before_return_html = config.delay_before_return_html * 1.2
        
        return {
            'config': config,
            'wait_time': wait_time
        }

    def _get_virtual_scroll_config(self, platform: str, url: str) -> dict:
        """获取平台特定的虚拟滚动配置"""
        # 基于crawl4ai文档的虚拟滚动配置 <mcreference link="https://docs.crawl4ai.com/advanced/virtual-scroll/" index="1">1</mcreference>
        virtual_configs = {
            'weibo': {
                'container_selector': '.WB_feed, [data-testid="primaryColumn"], .m-con-box, .WB_cardwrap',
                'scroll_count': 30,  # 微博时间线需要更多滚动
                'scroll_by': 'container_height',
                'wait_after_scroll': 1.5,  # 微博加载较慢，需要更长等待
                'max_scroll_height': 15000  # 限制最大滚动高度
            },
            'bilibili': {
                'container_selector': '.video-list, .bili-video-card, .feed-card',
                'scroll_count': 20,
                'scroll_by': 800,  # B站使用固定像素滚动
                'wait_after_scroll': 1.0,
                'max_scroll_height': 12000
            },
            'xiaohongshu': {
                'container_selector': '.note-item, .feeds-page, .note-scroller',
                'scroll_count': 25,
                'scroll_by': 'container_height',
                'wait_after_scroll': 1.2,
                'max_scroll_height': 10000
            },
            'douyin': {
                'container_selector': '.video-container, .aweme-video-container',
                'scroll_count': 15,  # 抖音视频较大，滚动次数少一些
                'scroll_by': 'page_height',
                'wait_after_scroll': 2.0,  # 视频加载需要更长时间
                'max_scroll_height': 8000
            }
        }
        
        # 检查URL是否需要虚拟滚动
        needs_virtual_scroll = self._needs_virtual_scroll(platform, url)
        if not needs_virtual_scroll:
            return None
            
        config = virtual_configs.get(platform)
        if not config:
            return None
            
        # 根据URL类型调整配置
        if 'search' in url or 'topic' in url or 'hashtag' in url:
            # 搜索和话题页面通常需要更多滚动
            config['scroll_count'] = min(config['scroll_count'] * 2, 50)
            config['wait_after_scroll'] = config['wait_after_scroll'] * 1.2
            
        return config
    
    def _needs_virtual_scroll(self, platform: str, url: str) -> bool:
        """判断是否需要虚拟滚动 <mcreference link="https://docs.crawl4ai.com/blog/articles/virtual-scroll-revolution/" index="2">2</mcreference>"""
        # 虚拟滚动适用场景：时间线、搜索结果、话题页面
        virtual_scroll_patterns = {
            'weibo': ['weibo.com/u/', 'weibo.com/search', 'weibo.com/topic'],
            'bilibili': ['bilibili.com/video/', 'bilibili.com/search', 'space.bilibili.com'],
            'xiaohongshu': ['xiaohongshu.com/explore', 'xiaohongshu.com/search', 'xiaohongshu.com/user'],
            'douyin': ['douyin.com/user/', 'douyin.com/search', 'douyin.com/discover']
        }
        
        patterns = virtual_scroll_patterns.get(platform, [])
        return any(pattern in url for pattern in patterns)
    
    def _get_platform_crawl_config(self, platform: str) -> dict:
        """根据平台获取优化的crawl4ai配置 - 增强JavaScript渲染和动态内容处理"""
        
        # 中文平台特殊优化配置
        chinese_platform_optimizations = {
            'weibo': {
                'extra_headers': {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                'stealth_config': {
                    'webdriver': False,
                    'chrome_app': False,
                    'chrome_csi': False,
                    'chrome_load_times': False,
                    'chrome_runtime': False,
                    'iframe_content_window': False,
                    'media_codecs': False,
                    'navigator_languages': False,
                    'navigator_permissions': False,
                    'navigator_plugins': False,
                    'navigator_vendor': False,
                    'navigator_webdriver': False,
                    'window_outerdimensions': False
                }
            },
            'bilibili': {
                'extra_headers': {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': 'https://www.bilibili.com/',
                    'Origin': 'https://www.bilibili.com',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate'
                }
            },
            'xiaohongshu': {
                'extra_headers': {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': 'https://www.xiaohongshu.com/',
                    'Origin': 'https://www.xiaohongshu.com'
                }
            },
            'douyin': {
                'extra_headers': {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': 'https://www.douyin.com/',
                    'Origin': 'https://www.douyin.com'
                }
            }
        }
        configs = {
            'weibo': {
                'wait_for': 'networkidle',
                'timeout': 90000,  # 增加到90秒
                'delay_before_return_html': 15,  # 增加到15秒确保页面完全稳定
                'page_timeout': 120000,  # 页面加载超时增加到120秒
                'navigation_timeout': 60000,  # 导航超时增加到60秒
                'headers': chinese_platform_optimizations['weibo']['extra_headers'],
                'anti_detection': True,
                'random_delay': True,
                'user_simulation': True,
                'js_code': [
                    "console.log('开始微博页面稳定性处理...');",
                    "// 等待页面基本加载",
                    "await new Promise(resolve => setTimeout(resolve, 5000));",
                    "// 严格检查页面导航状态",
                    "let navigationChecks = 0;",
                    "const maxNavigationChecks = 20;",
                    "while(navigationChecks < maxNavigationChecks) {",
                    "  const readyState = document.readyState;",
                    "  const isHidden = document.hidden;",
                    "  console.log(`导航检查 ${navigationChecks + 1}: readyState=${readyState}, hidden=${isHidden}`);",
                    "  if (readyState === 'complete' && !isHidden) {",
                    "    break;",
                    "  }",
                    "  await new Promise(resolve => setTimeout(resolve, 1000));",
                    "  navigationChecks++;",
                    "}",
                    "// 等待微博特定内容出现",
                    "const weiboSelectors = ['.WB_detail', '.WB_feed_detail', '.WB_cardwrap', 'article', '.card-wrap', '.WB_text', '.m-con-box'];",
                    "let contentFound = false;",
                    "for (let attempt = 0; attempt < 15; attempt++) {",
                    "  for (const selector of weiboSelectors) {",
                    "    const elements = document.querySelectorAll(selector);",
                    "    if (elements.length > 0) {",
                    "      console.log(`找到微博内容: ${selector}, 数量: ${elements.length}`);",
                    "      contentFound = true;",
                    "      break;",
                    "    }",
                    "  }",
                    "  if (contentFound) break;",
                    "  await new Promise(resolve => setTimeout(resolve, 2000));",
                    "}",
                    "// 渐进式滚动以触发懒加载",
                    "const scrollPositions = [0, 300, 600, 900, 600, 300, 0];",
                    "for (const position of scrollPositions) {",
                    "  window.scrollTo(0, position);",
                    "  await new Promise(resolve => setTimeout(resolve, 2000));",
                    "}",
                    "// 最终稳定等待",
                    "await new Promise(resolve => setTimeout(resolve, 3000));",
                    "console.log('微博页面处理完成');"
                ],
                'css_selector': '.WB_detail, .WB_feed_detail, .WB_cardwrap, article, .card-wrap',
                'remove_overlay_elements': True,
                'simulate_user': True,
                'override_navigator': True,
                'wait_for_selector': '.WB_detail, .WB_feed_detail, .WB_cardwrap',
                'wait_for_selector_timeout': 45000  # 增加到45秒
            },
            'bilibili': {
                'wait_for': 'networkidle',
                'timeout': 60000,  # 增加超时时间
                'delay_before_return_html': 8,  # 增加延迟确保内容加载
                'page_timeout': 90000,
                'navigation_timeout': 45000,
                'headers': chinese_platform_optimizations['bilibili']['extra_headers'],
                'anti_detection': True,
                'random_delay': True,
                'user_simulation': True,
                'js_code': [
                    "console.log('开始B站页面处理...');",
                    "// 暂停视频减少资源消耗",
                    "document.querySelectorAll('video').forEach(v => v.pause());",
                    "// 等待页面基本加载",
                    "await new Promise(resolve => setTimeout(resolve, 3000));",
                    "// 检查B站特定内容",
                    "const biliSelectors = ['.video-info-title', '.video-title', '.video-desc', '.up-info', '.video-info', '.video-info-container'];",
                    "let biliContentFound = false;",
                    "for (let attempt = 0; attempt < 10; attempt++) {",
                    "  for (const selector of biliSelectors) {",
                    "    const elements = document.querySelectorAll(selector);",
                    "    if (elements.length > 0) {",
                    "      console.log(`找到B站内容: ${selector}, 数量: ${elements.length}`);",
                    "      biliContentFound = true;",
                    "      break;",
                    "    }",
                    "  }",
                    "  if (biliContentFound) break;",
                    "  await new Promise(resolve => setTimeout(resolve, 1500));",
                    "}",
                    "// 模拟用户滚动行为",
                    "window.scrollTo(0, 500);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "window.scrollTo(0, 0);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "console.log('B站页面处理完成');"
                ],
                'css_selector': '.video-info-title, .video-title, .video-desc, .up-info, .video-info, .video-info-container',
                'remove_overlay_elements': True,
                'simulate_user': True,
                'override_navigator': True,
                'wait_for_selector': '.video-info-title, .video-title',
                'wait_for_selector_timeout': 30000
            },
            'xiaohongshu': {
                'wait_for': 'networkidle',
                'timeout': 50000,  # 增加超时时间
                'delay_before_return_html': 6,  # 增加延迟
                'page_timeout': 75000,
                'navigation_timeout': 40000,
                'headers': chinese_platform_optimizations['xiaohongshu']['extra_headers'],
                'anti_detection': True,
                'random_delay': True,
                'user_simulation': True,
                'js_code': [
                    "console.log('开始小红书页面处理...');",
                    "// 等待页面基本加载",
                    "await new Promise(resolve => setTimeout(resolve, 2500));",
                    "// 检查小红书特定内容",
                    "const xhsSelectors = ['.note-item', '.note-detail', '.content', '.title', '.note-content', '.note-scroller'];",
                    "let xhsContentFound = false;",
                    "for (let attempt = 0; attempt < 8; attempt++) {",
                    "  for (const selector of xhsSelectors) {",
                    "    const elements = document.querySelectorAll(selector);",
                    "    if (elements.length > 0) {",
                    "      console.log(`找到小红书内容: ${selector}, 数量: ${elements.length}`);",
                    "      xhsContentFound = true;",
                    "      break;",
                    "    }",
                    "  }",
                    "  if (xhsContentFound) break;",
                    "  await new Promise(resolve => setTimeout(resolve, 1200));",
                    "}",
                    "// 模拟用户滚动触发懒加载",
                    "window.scrollTo(0, 300);",
                    "await new Promise(resolve => setTimeout(resolve, 1500));",
                    "window.scrollTo(0, 600);",
                    "await new Promise(resolve => setTimeout(resolve, 1500));",
                    "window.scrollTo(0, 0);",
                    "await new Promise(resolve => setTimeout(resolve, 1500));",
                    "console.log('小红书页面处理完成');"
                ],
                'css_selector': '.note-item, .note-detail, .content, .title, .note-content, .note-scroller',
                'remove_overlay_elements': True,
                'simulate_user': True,
                'override_navigator': True,
                'wait_for_selector': '.note-item, .note-detail',
                'wait_for_selector_timeout': 25000
            },
            'douyin': {
                'wait_for': 'networkidle',
                'timeout': 55000,  # 增加超时时间
                'delay_before_return_html': 7,  # 增加延迟
                'page_timeout': 80000,
                'navigation_timeout': 45000,
                'headers': chinese_platform_optimizations['douyin']['extra_headers'],
                'anti_detection': True,
                'random_delay': True,
                'user_simulation': True,
                'js_code': [
                    "console.log('开始抖音页面处理...');",
                    "// 暂停视频减少资源消耗",
                    "document.querySelectorAll('video').forEach(v => v.pause());",
                    "// 等待页面基本加载",
                    "await new Promise(resolve => setTimeout(resolve, 3000));",
                    "// 检查抖音特定内容",
                    "const dySelectors = ['.video-info', '.video-desc', '.author-info', '.video-title', '.video-container'];",
                    "let dyContentFound = false;",
                    "for (let attempt = 0; attempt < 10; attempt++) {",
                    "  for (const selector of dySelectors) {",
                    "    const elements = document.querySelectorAll(selector);",
                    "    if (elements.length > 0) {",
                    "      console.log(`找到抖音内容: ${selector}, 数量: ${elements.length}`);",
                    "      dyContentFound = true;",
                    "      break;",
                    "    }",
                    "  }",
                    "  if (dyContentFound) break;",
                    "  await new Promise(resolve => setTimeout(resolve, 1500));",
                    "}",
                    "// 模拟用户滚动行为",
                    "window.scrollTo(0, 400);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "window.scrollTo(0, 800);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "window.scrollTo(0, 0);",
                    "await new Promise(resolve => setTimeout(resolve, 2000));",
                    "console.log('抖音页面处理完成');"
                ],
                'css_selector': '.video-info, .video-desc, .author-info, .video-title, .video-container',
                'remove_overlay_elements': True,
                'simulate_user': True,
                'override_navigator': True,
                'wait_for_selector': '.video-info, .video-desc',
                'wait_for_selector_timeout': 30000
            },
            'default': {
                'wait_for': 'domcontentloaded',
                'timeout': 30000,
                'delay_before_return_html': 2,
                'simulate_user': True,
                'override_navigator': True
            }
        }
        
        # 获取基础配置
        base_config = configs.get(platform, configs['default'])
        
        # 为中文平台添加额外的反检测机制
        if platform in ['weibo', 'bilibili', 'xiaohongshu', 'douyin']:
            base_config = self._enhance_chinese_platform_config(base_config, platform)
        
        return base_config
    
    def _enhance_chinese_platform_config(self, config: dict, platform: str) -> dict:
        """为中文平台增强反检测配置"""
        enhanced_config = config.copy()
        
        # 添加随机延迟机制
        if 'js_code' in enhanced_config and isinstance(enhanced_config['js_code'], list):
            # 在现有js_code前添加反检测代码
            anti_detection_js = [
                f"console.log('启动{platform}反检测机制...');",
                "// 随机延迟避免检测",
                f"const randomDelay = Math.floor(Math.random() * 3000) + 2000;",
                "await new Promise(resolve => setTimeout(resolve, randomDelay));",
                "// 模拟真实用户行为",
                "if (Math.random() > 0.7) {",
                "  // 随机鼠标移动",
                "  const moveEvent = new MouseEvent('mousemove', {",
                "    clientX: Math.random() * window.innerWidth,",
                "    clientY: Math.random() * window.innerHeight,",
                "    bubbles: true",
                "  });",
                "  document.dispatchEvent(moveEvent);",
                "  await new Promise(resolve => setTimeout(resolve, 500));",
                "}",
                "// 检查并移除可能的检测脚本",
                "const suspiciousScripts = document.querySelectorAll('script[src*=\"detect\"], script[src*=\"anti\"], script[src*=\"bot\"]');",
                "suspiciousScripts.forEach(script => {",
                "  try { script.remove(); } catch(e) { console.log('无法移除检测脚本:', e); }",
                "});",
                "// 隐藏自动化特征",
                "try {",
                "  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });",
                "  Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });",
                "  Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });",
                "} catch(e) { console.log('特征隐藏失败:', e); }"
            ]
            
            # 将反检测代码插入到现有代码前面
            enhanced_config['js_code'] = anti_detection_js + enhanced_config['js_code']
        
        # 添加平台特定的CSS选择器优化
        platform_selectors = {
            'weibo': {
                'content_selectors': ['.WB_detail', '.WB_feed_detail', '.WB_cardwrap', 'article', '.card-wrap', '.WB_text'],
                'remove_selectors': ['.layer_menu_list', '.W_layer', '.W_mask', '.login_layer']
            },
            'bilibili': {
                'content_selectors': ['.video-info-title', '.video-title', '.video-desc', '.up-info'],
                'remove_selectors': ['.bili-mini-mask', '.login-mask', '.mini-login-mask']
            },
            'xiaohongshu': {
                'content_selectors': ['.note-item', '.note-detail', '.content', '.title'],
                'remove_selectors': ['.login-mask', '.mask', '.modal']
            },
            'douyin': {
                'content_selectors': ['.video-info', '.video-desc', '.author-info'],
                'remove_selectors': ['.login-mask', '.mask-layer', '.modal-mask']
            }
        }
        
        if platform in platform_selectors:
            selectors = platform_selectors[platform]
            enhanced_config['content_selectors'] = selectors['content_selectors']
            enhanced_config['remove_selectors'] = selectors['remove_selectors']
        
        # 增加超时时间以应对反爬虫延迟
        timeout_multiplier = 1.3
        if 'timeout' in enhanced_config:
            enhanced_config['timeout'] = int(enhanced_config['timeout'] * timeout_multiplier)
        if 'page_timeout' in enhanced_config:
            enhanced_config['page_timeout'] = int(enhanced_config['page_timeout'] * timeout_multiplier)
        if 'navigation_timeout' in enhanced_config:
            enhanced_config['navigation_timeout'] = int(enhanced_config['navigation_timeout'] * timeout_multiplier)
        
        return enhanced_config

    def _analyze_network_requests(self, result, url: str, platform: str) -> dict:
        """分析网络请求和控制台消息，提供调试和优化信息"""
        analysis = {
            'total_requests': 0,
            'failed_requests': 0,
            'api_requests': 0,
            'image_requests': 0,
            'script_requests': 0,
            'xhr_requests': 0,
            'console_errors': 0,
            'console_warnings': 0,
            'suspicious_requests': [],
            'performance_issues': [],
            'anti_bot_indicators': []
        }
        
        try:
            # 分析网络请求
            if hasattr(result, 'network_requests') and result.network_requests:
                analysis['total_requests'] = len(result.network_requests)
                
                for request in result.network_requests:
                    # 统计请求类型
                    resource_type = request.get('resource_type', '').lower()
                    method = request.get('method', '').upper()
                    request_url = request.get('url', '')
                    status_code = request.get('status_code', 0)
                    
                    # 统计失败请求
                    if status_code >= 400:
                        analysis['failed_requests'] += 1
                    
                    # 分类请求类型
                    if resource_type in ['fetch', 'xhr'] or method in ['POST', 'PUT', 'PATCH']:
                        analysis['xhr_requests'] += 1
                        
                        # 检查API请求
                        if any(api_pattern in request_url.lower() for api_pattern in ['/api/', '/ajax/', '/json', '.json']):
                            analysis['api_requests'] += 1
                    
                    elif resource_type in ['image', 'imageset']:
                        analysis['image_requests'] += 1
                    
                    elif resource_type in ['script', 'javascript']:
                        analysis['script_requests'] += 1
                    
                    # 检查可疑请求（可能的反爬虫检测）
                    suspicious_patterns = [
                        'captcha', 'verify', 'challenge', 'protection', 'security',
                        'anti-bot', 'bot-detection', 'fingerprint', 'tracking'
                    ]
                    
                    if any(pattern in request_url.lower() for pattern in suspicious_patterns):
                        analysis['suspicious_requests'].append({
                            'url': request_url,
                            'type': resource_type,
                            'status': status_code
                        })
                    
                    # 检查性能问题
                    if hasattr(request, 'response_time') and request.get('response_time', 0) > 5000:  # 超过5秒
                        analysis['performance_issues'].append({
                            'url': request_url,
                            'response_time': request.get('response_time'),
                            'type': resource_type
                        })
            
            # 分析控制台消息
            if hasattr(result, 'console_messages') and result.console_messages:
                for message in result.console_messages:
                    message_type = message.get('type', '').lower()
                    message_text = message.get('text', '').lower()
                    
                    if message_type == 'error':
                        analysis['console_errors'] += 1
                        
                        # 检查反爬虫相关错误
                        anti_bot_patterns = [
                            'access denied', 'blocked', 'captcha', 'verification required',
                            'bot detected', 'suspicious activity', 'rate limit exceeded'
                        ]
                        
                        if any(pattern in message_text for pattern in anti_bot_patterns):
                            analysis['anti_bot_indicators'].append({
                                'type': 'console_error',
                                'message': message.get('text', ''),
                                'location': message.get('location', '')
                            })
                    
                    elif message_type == 'warning':
                        analysis['console_warnings'] += 1
            
            # 平台特定分析
            if platform == 'weibo':
                analysis.update(self._analyze_weibo_network(result))
            elif platform == 'bilibili':
                analysis.update(self._analyze_bilibili_network(result))
            elif platform == 'xiaohongshu':
                analysis.update(self._analyze_xiaohongshu_network(result))
            elif platform == 'douyin':
                analysis.update(self._analyze_douyin_network(result))
            
            # 生成建议
            suggestions = self._generate_network_suggestions(analysis, platform)
            analysis['suggestions'] = suggestions
            
            logger.debug(f"网络分析完成: 总请求{analysis['total_requests']}, 失败{analysis['failed_requests']}, API{analysis['api_requests']}, 错误{analysis['console_errors']}")
            
        except Exception as e:
            logger.error(f"网络请求分析失败: {str(e)}")
            analysis['error'] = str(e)
        
        return analysis
    
    def _analyze_weibo_network(self, result) -> dict:
        """分析微博平台特定的网络请求"""
        weibo_analysis = {
            'weibo_api_calls': 0,
            'login_attempts': 0,
            'rate_limit_hits': 0
        }
        
        if hasattr(result, 'network_requests') and result.network_requests:
            for request in result.network_requests:
                url = request.get('url', '').lower()
                
                # 微博API调用
                if 'weibo.com/ajax' in url or 'weibo.com/api' in url:
                    weibo_analysis['weibo_api_calls'] += 1
                
                # 登录相关请求
                if 'login' in url or 'passport' in url:
                    weibo_analysis['login_attempts'] += 1
                
                # 限流检测
                status_code = request.get('status_code', 0)
                if status_code == 429 or 'rate limit' in url:
                    weibo_analysis['rate_limit_hits'] += 1
        
        return weibo_analysis
    
    def _analyze_bilibili_network(self, result) -> dict:
        """分析B站平台特定的网络请求"""
        bilibili_analysis = {
            'video_api_calls': 0,
            'user_api_calls': 0,
            'cdn_requests': 0
        }
        
        if hasattr(result, 'network_requests') and result.network_requests:
            for request in result.network_requests:
                url = request.get('url', '').lower()
                
                # 视频相关API
                if 'bilibili.com/x/web-interface/view' in url:
                    bilibili_analysis['video_api_calls'] += 1
                
                # 用户相关API
                if 'bilibili.com/x/space' in url or 'bilibili.com/x/relation' in url:
                    bilibili_analysis['user_api_calls'] += 1
                
                # CDN请求
                if 'hdslb.com' in url or 'bilivideo.com' in url:
                    bilibili_analysis['cdn_requests'] += 1
        
        return bilibili_analysis
    
    def _analyze_xiaohongshu_network(self, result) -> dict:
        """分析小红书平台特定的网络请求"""
        return {'xiaohongshu_specific': True}
    
    def _analyze_douyin_network(self, result) -> dict:
        """分析抖音平台特定的网络请求"""
        return {'douyin_specific': True}
    
    def _generate_network_suggestions(self, analysis: dict, platform: str) -> List[str]:
        """根据网络分析结果生成优化建议"""
        suggestions = []
        
        # 失败请求过多
        if analysis['failed_requests'] > analysis['total_requests'] * 0.3:
            suggestions.append(f"失败请求过多({analysis['failed_requests']}/{analysis['total_requests']})，建议检查网络连接或增加重试机制")
        
        # 可疑请求检测
        if analysis['suspicious_requests']:
            suggestions.append(f"检测到{len(analysis['suspicious_requests'])}个可疑请求，可能触发了反爬虫机制")
        
        # 性能问题
        if analysis['performance_issues']:
            suggestions.append(f"检测到{len(analysis['performance_issues'])}个慢请求，建议优化超时设置")
        
        # 控制台错误
        if analysis['console_errors'] > 5:
            suggestions.append(f"控制台错误过多({analysis['console_errors']})，建议检查页面JavaScript执行")
        
        # 反爬虫指标
        if analysis['anti_bot_indicators']:
            suggestions.append(f"检测到{len(analysis['anti_bot_indicators'])}个反爬虫指标，建议增强隐身配置")
        
        # 平台特定建议
        if platform == 'weibo' and 'rate_limit_hits' in analysis and analysis['rate_limit_hits'] > 0:
            suggestions.append("微博限流检测，建议降低请求频率")
        
        return suggestions

    def _parse_crawl4ai_result(self, result, url: str, platform: str) -> List[PostData]:
        """解析crawl4ai的结果，专注于动态内容提取"""
        posts = []
        
        try:
            # 基本内容提取
            title = result.metadata.get('title', '未知标题') if result.metadata else '未知标题'
            title = title or '未知标题'  # 确保标题不为None
            content = result.cleaned_html or result.markdown or result.html or ''
            
            # 如果内容太短，尝试使用其他字段
            if len(content) < 100:
                content = str(result.html)[:2000] if result.html else '无内容'
            
            # 专门的错误检测和处理
            error_result = self._detect_and_handle_errors(title, content, url, platform)
            if error_result:
                logger.error(f"检测到页面错误: {error_result['error_type']} - {error_result['message']}")
                logger.error(f"建议: {error_result['suggestion']}")
                return posts  # 返回空列表
            
            # 详细的调试日志
            logger.info(f"=== 内容解析调试信息 ===")
            logger.info(f"实际访问URL: {url}")
            logger.info(f"平台: {platform}")
            logger.info(f"页面标题: {title}")
            logger.info(f"内容长度: {len(content)} 字符")
            logger.info(f"内容预览: {content[:200]}...")
            
            # 检查URL类型
            url_type = self._analyze_url_type(url)
            logger.info(f"URL类型分析: {url_type}")
            
            # 检查内容类型
            content_type = self._analyze_content_type(title, content, url)
            logger.info(f"内容类型分析: {content_type}")
            
            logger.info(f"解析内容 - 标题: {title[:50]}, 内容长度: {len(content)}, URL: {url}")
            
            # B站特殊处理
            if platform == 'bilibili':
                # B站特殊内容提取逻辑
                bilibili_posts = self._parse_bilibili_content(result, url, title, content)
                if bilibili_posts:
                    posts.extend(bilibili_posts)
                    logger.info(f"B站特殊解析成功，获取 {len(bilibili_posts)} 条内容")
                    return posts
                else:
                    logger.warning(f"B站特殊解析失败，尝试通用解析: {title[:50]}")
            
            # 验证是否为有效的动态内容
            is_valid = self._is_valid_dynamic_content(title, content, url)
            logger.info(f"动态内容验证结果: {is_valid}")
            
            if not is_valid:
                logger.warning(f"跳过非动态内容: {title[:50]}")
                logger.warning(f"跳过原因: 内容被识别为静态页面或首页")
                return posts
            
            # 清理和优化内容
            cleaned_content = self._clean_dynamic_content(content, platform)
            
            # 提取作者信息
            author = self._extract_author_from_platform(platform, url)
            
            # 创建PostData对象
            post_data = PostData(
                title=self._clean_title(title),
                content=cleaned_content[:2000],  # 限制内容长度
                author=author,
                platform=platform,
                url=url,
                published_at=datetime.now(),
                tags=self._extract_tags(cleaned_content),
                images=self._extract_images_from_content(cleaned_content),
                video_url=self._extract_video_url(cleaned_content, platform)
            )
            
            posts.append(post_data)
            logger.info(f"成功解析动态内容: {title[:50]}")
            
        except Exception as e:
            logger.error(f"解析crawl4ai结果失败: {str(e)}")
            logger.exception("详细错误信息:")
            
        return posts

    def _parse_bilibili_content(self, result, url: str, title: str, content: str) -> List[PostData]:
        """专门解析B站内容的方法"""
        posts = []
        
        try:
            # B站特定的内容验证
            bilibili_indicators = [
                'bilibili.com', 'b23.tv', 'up主', 'up', '播放', '弹幕', 
                '投币', '收藏', '三连', 'av号', 'bv号', '番剧', '直播',
                '热门', '推荐', '排行榜', '新番', '游戏', '科技', '生活', 
                '娱乐', '音乐', '舞蹈', '视频', '动态'
            ]
            
            title_lower = title.lower()
            content_lower = content.lower()
            
            # 检查是否包含B站特征
            bilibili_score = 0
            for indicator in bilibili_indicators:
                if indicator in title_lower or indicator in content_lower:
                    bilibili_score += 1
            
            logger.info(f"B站内容评分: {bilibili_score}, 标题: {title[:50]}")
            
            # B站内容必须达到一定的特征分数
            if bilibili_score < 2:
                logger.warning(f"B站内容特征不足，评分: {bilibili_score}")
                return posts
            
            # 排除明显的错误页面
            error_indicators = ['访问异常', '页面异常', '无法访问', '404', '403', '500', '错误']
            if any(error in title_lower for error in error_indicators):
                logger.warning(f"检测到B站错误页面: {title[:50]}")
                return posts
            
            # 提取B站特有信息
            author = self._extract_bilibili_author(content, url)
            video_url = self._extract_bilibili_video_url(content, url)
            images = self._extract_bilibili_images(content)
            tags = self._extract_bilibili_tags(content)
            
            # 清理B站内容
            cleaned_content = self._clean_bilibili_content(content)
            
            # 确保内容质量
            if len(cleaned_content.strip()) < 30:
                logger.warning(f"B站内容过短: {len(cleaned_content)} 字符")
                return posts
            
            # 创建B站PostData对象
            post_data = PostData(
                title=self._clean_title(title),
                content=cleaned_content[:2000],
                author=author,
                platform='bilibili',
                url=url,
                published_at=datetime.now(),
                tags=tags,
                images=images,
                video_url=video_url
            )
            
            posts.append(post_data)
            logger.info(f"B站内容解析成功: {title[:50]}")
            
        except Exception as e:
            logger.error(f"B站内容解析失败: {str(e)}")
            logger.exception("B站解析详细错误:")
            
        return posts
    
    def _extract_bilibili_author(self, content: str, url: str) -> str:
        """提取B站作者信息"""
        import re
        
        # 尝试从内容中提取UP主名称
        up_patterns = [
            r'UP主[：:](\S+)',
            r'up主[：:](\S+)',
            r'作者[：:](\S+)',
            r'博主[：:](\S+)'
        ]
        
        for pattern in up_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        # 从URL中提取用户ID
        user_match = re.search(r'/space/(\d+)', url)
        if user_match:
            return f'UP主_{user_match.group(1)}'
        
        return 'B站UP主'
    
    def _extract_bilibili_video_url(self, content: str, url: str) -> str:
        """提取B站视频链接"""
        import re
        
        # B站视频URL模式
        video_patterns = [
            r'https?://www\.bilibili\.com/video/[^\s]+',
            r'https?://b23\.tv/[^\s]+',
            r'BV[0-9A-Za-z]+',
            r'av\d+'
        ]
        
        for pattern in video_patterns:
            match = re.search(pattern, content)
            if match:
                video_id = match.group(0)
                if video_id.startswith(('BV', 'av')):
                    return f'https://www.bilibili.com/video/{video_id}'
                return video_id
        
        # 如果当前URL就是视频页面，直接返回
        if '/video/' in url:
            return url
        
        return None
    
    def _extract_bilibili_images(self, content: str) -> List[str]:
        """提取B站图片"""
        import re
        
        # B站图片URL模式
        img_patterns = [
            r'https?://i\d*\.hdslb\.com/[^\s]+\.(jpg|jpeg|png|gif|webp)',
            r'https?://[^\s]*\.bilibili\.com/[^\s]+\.(jpg|jpeg|png|gif|webp)'
        ]
        
        images = []
        for pattern in img_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    images.append(match[0])
                else:
                    images.append(match)
        
        return list(set(images))[:5]  # 去重并限制数量
    
    def _analyze_url_type(self, url: str) -> str:
        """分析URL类型，判断是否为动态内容页面"""
        url_lower = url.lower()
        
        if 'weibo.com' in url_lower:
            if '/home' in url_lower or 'tabtype=feed' in url_lower or 'is_all=1' in url_lower:
                return '微博动态页面'
            elif '/u/' in url_lower or '/n/' in url_lower:
                return '微博用户页面'
            else:
                return '微博首页或其他页面'
        elif 'bilibili.com' in url_lower:
            if '/video/' in url_lower:
                return 'B站视频页面'
            elif '/space/' in url_lower:
                return 'B站用户空间'
            else:
                return 'B站首页或其他页面'
        elif 'xiaohongshu.com' in url_lower:
            if '/explore/' in url_lower or '/user/' in url_lower:
                return '小红书动态页面'
            else:
                return '小红书首页或其他页面'
        elif 'douyin.com' in url_lower:
            if '/user/' in url_lower or '/video/' in url_lower:
                return '抖音动态页面'
            else:
                return '抖音首页或其他页面'
        else:
            return '未知平台页面'
    
    def _analyze_content_type(self, title: str, content: str, url: str) -> str:
        """分析内容类型，判断是否为动态内容"""
        title_lower = (title or '').lower()
        content_lower = (content or '').lower()
        
        # 检查静态页面特征
        static_indicators = ['首页', 'home', 'index', '关于我们', 'about', '登录', 'login']
        static_score = sum(1 for indicator in static_indicators if indicator in title_lower or indicator in content_lower)
        
        # 检查动态内容特征
        dynamic_indicators = ['发布', '更新', '最新', '动态', '帖子', 'post', '视频', 'video', '评论', 'comment']
        dynamic_score = sum(1 for indicator in dynamic_indicators if indicator in title_lower or indicator in content_lower)
        
        # 检查微博特定特征
        weibo_indicators = ['微博', 'weibo', '转发', '点赞', '话题', '博主']
        weibo_score = sum(1 for indicator in weibo_indicators if indicator in title_lower or indicator in content_lower)
        
        if static_score > dynamic_score:
            return f'静态页面 (静态特征:{static_score}, 动态特征:{dynamic_score})'
        elif dynamic_score > 0 or weibo_score > 0:
            return f'动态内容 (动态特征:{dynamic_score}, 微博特征:{weibo_score})'
        else:
            return f'未知内容类型 (静态特征:{static_score}, 动态特征:{dynamic_score})'
    
    def _extract_bilibili_tags(self, content: str) -> List[str]:
        """提取B站标签"""
        import re
        
        tags = []
        
        # B站特有标签
        bilibili_tags = ['bilibili', 'B站', '哔哩哔哩']
        tags.extend(bilibili_tags)
        
        # 提取话题标签
        topic_pattern = r'#([^#\s]+)#?'
        topics = re.findall(topic_pattern, content)
        tags.extend(topics)
        
        # 提取分区标签
        category_patterns = [
            r'(游戏|科技|生活|娱乐|音乐|舞蹈|动画|番剧|电影|电视剧)',
            r'(UP主|直播|投稿|原创|转载)'
        ]
        
        for pattern in category_patterns:
            categories = re.findall(pattern, content)
            tags.extend(categories)
        
        return list(set(tags))[:10]  # 去重并限制数量
    
    def _clean_bilibili_content(self, content: str) -> str:
        """清理B站内容"""
        import re
        
        # 移除B站特有的无关内容
        remove_patterns = [
            r'投币.*?收藏.*?分享',
            r'点赞.*?投币.*?收藏',
            r'三连.*?支持',
            r'弹幕.*?评论区',
            r'关注.*?订阅',
            r'广告.*?推广',
            r'版权.*?声明'
        ]
        
        cleaned = content
        for pattern in remove_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 通用清理
        cleaned = self._clean_dynamic_content(cleaned, 'bilibili')
        
        return cleaned.strip()

    def _is_dynamic_content_url(self, url: str) -> bool:
        """检查URL是否为动态内容页面"""
        # 排除首页和静态页面的关键词
        static_patterns = [
            r'/(index|home|main)\b',  # 首页
            r'/about\b',  # 关于页面
            r'/contact\b',  # 联系页面
            r'/help\b',  # 帮助页面
            r'/terms\b',  # 条款页面
            r'/privacy\b',  # 隐私页面
            r'/login\b',  # 登录页面
            r'/register\b',  # 注册页面
            r'/static/',  # 静态资源
            r'/assets/',  # 资源文件
            r'\.(css|js|png|jpg|jpeg|gif|ico)$'  # 静态文件
        ]
        
        # 动态内容的关键词
        dynamic_patterns = [
            r'/search\b',  # 搜索页面
            r'/post/',  # 帖子页面
            r'/video/',  # 视频页面
            r'/note/',  # 笔记页面
            r'/weibo/',  # 微博页面
            r'/status/',  # 状态页面
            r'/feed/',  # 动态页面
            r'/timeline/',  # 时间线
            r'/api/',  # API接口
            r'\?.*q=',  # 搜索查询
            r'\?.*keyword=',  # 关键词搜索
        ]
        
        import re
        
        # 检查是否为静态页面
        for pattern in static_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # 检查是否为动态内容
        for pattern in dynamic_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        # 默认认为是动态内容（保守策略）
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """检查URL是否有效，包含平台特定的验证逻辑"""
        if not url or not isinstance(url, str):
            return False
        
        # 检查URL格式
        if not url.startswith(('http://', 'https://')):
            return False
        
        # 检查是否包含有效的域名
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return False
            # 检查域名是否包含点号（基本的域名格式检查）
            if '.' not in parsed.netloc:
                return False
            
            # 平台特定的URL验证
            if 'weibo.com' in parsed.netloc:
                return self._validate_weibo_url(url, parsed)
            elif 'bilibili.com' in parsed.netloc:
                return self._validate_bilibili_url(url, parsed)
            elif 'xiaohongshu.com' in parsed.netloc:
                return self._validate_xiaohongshu_url(url, parsed)
            elif 'douyin.com' in parsed.netloc:
                return self._validate_douyin_url(url, parsed)
            
            return True
        except Exception as e:
            logger.warning(f"URL验证异常: {url}, 错误: {e}")
            return False
    
    def _validate_weibo_url(self, url: str, parsed_url) -> bool:
        """验证微博URL是否有效，排除热搜页面等无效URL"""
        path = parsed_url.path.lower()
        
        # 排除的无效页面路径
        invalid_paths = [
            '/hot/search',  # 热搜页面
            '/hot/',        # 热门页面
            '/search',      # 搜索页面
            '/login',       # 登录页面
            '/register',    # 注册页面
            '/home',        # 通用首页
            '/index',       # 首页
            '/about',       # 关于页面
            '/help',        # 帮助页面
        ]
        
        # 检查是否为无效路径
        for invalid_path in invalid_paths:
            if path.startswith(invalid_path):
                logger.warning(f"检测到无效的微博URL路径: {path}")
                return False
        
        # 检查是否为用户页面
        if path.startswith('/u/') or path.startswith('/n/') or (path and path != '/' and not path.startswith('/static/')):
            return True
        
        # 微博首页也认为是无效的
        if path == '/' or path == '':
            logger.warning(f"检测到微博首页URL，不适合爬取动态内容: {url}")
            return False
        
        return True
    
    def _validate_bilibili_url(self, url: str, parsed_url) -> bool:
        """验证B站URL是否有效"""
        path = parsed_url.path.lower()
        
        # B站有效的用户页面路径
        valid_patterns = ['/space.bilibili.com/', '/dynamic', '/video']
        
        for pattern in valid_patterns:
            if pattern in url.lower():
                return True
        
        return True  # B站URL相对宽松
    
    def _validate_xiaohongshu_url(self, url: str, parsed_url) -> bool:
        """验证小红书URL是否有效"""
        return True  # 小红书URL相对宽松
    
    def _validate_douyin_url(self, url: str, parsed_url) -> bool:
        """验证抖音URL是否有效"""
        return True  # 抖音URL相对宽松
    
    def _extract_author_from_platform(self, platform: str, url: str) -> str:
        """根据平台提取作者信息"""
        if platform == 'weibo':
            return '微博用户'
        elif platform == 'bilibili':
            return 'B站UP主'
        elif platform == 'xiaohongshu':
            return '小红书用户'
        elif platform == 'douyin':
            return '抖音用户'
        else:
            return '未知作者'
    
    def _validate_weibo_user_identifier(self, creator_url: str) -> List[str]:
        """验证微博用户标识符并生成相应的URL列表"""
        import re
        
        # 首先尝试解析和优化用户标识符
        parsed_identifier = self._parse_weibo_user_identifier(creator_url)
        if not parsed_identifier:
            return []
        
        # 检查是否包含中文字符或特殊字符（可能是昵称）
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', parsed_identifier))
        has_special_chars = bool(re.search(r'[^a-zA-Z0-9_-]', parsed_identifier))
        
        if has_chinese or has_special_chars:
            # 如果包含中文或特殊字符，可能是昵称，尝试生成昵称格式的URL
            logger.info(f"检测到可能的昵称格式: {parsed_identifier}，尝试生成昵称URL")
            # 清理标识符，保留中文、英文、数字、下划线和连字符
            cleaned_identifier = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff-]', '', parsed_identifier)
            if cleaned_identifier:
                candidate_urls = [
                    f"https://weibo.com/n/{cleaned_identifier}",  # 昵称格式
                    f"https://weibo.com/{cleaned_identifier}?tabtype=feed",  # 用户动态
                    f"https://weibo.com/{cleaned_identifier}"  # 基本用户页面
                ]
                return candidate_urls
            else:
                logger.warning(f"清理后的标识符为空: {parsed_identifier}")
                return []
        
        # 检查用户名长度和格式
        if len(parsed_identifier) < 3 or len(parsed_identifier) > 30:
            logger.warning(f"微博用户名长度不符合规范: {parsed_identifier} (长度: {len(parsed_identifier)})")
            return []
        
        # 检查是否为保留关键词
        reserved_keywords = [
            'admin', 'api', 'www', 'mail', 'ftp', 'localhost', 'test',
            'weibo', 'sina', 'home', 'index', 'login', 'register'
        ]
        if parsed_identifier.lower() in reserved_keywords:
            logger.warning(f"微博用户名为保留关键词: {parsed_identifier}")
            return []
        
        # 如果验证通过，生成候选URL列表
        candidate_urls = [
            f"https://weibo.com/{parsed_identifier}?tabtype=feed",  # 用户微博动态
            f"https://weibo.com/u/{parsed_identifier}?tabtype=feed", # 用户动态（u格式）
            f"https://weibo.com/{parsed_identifier}?is_all=1"       # 全部微博
        ]
        
        # 验证URL有效性
        valid_urls = []
        for url in candidate_urls:
            if self._validate_url_accessibility(url):
                valid_urls.append(url)
                logger.info(f"微博URL验证通过: {url}")
            else:
                logger.warning(f"微博URL验证失败: {url}")
        
        if valid_urls:
            logger.info(f"微博用户标识符验证通过: {parsed_identifier} (原始: {creator_url})，生成 {len(valid_urls)} 个有效URL")
        else:
            logger.warning(f"微博用户标识符验证失败: {parsed_identifier} (原始: {creator_url})，没有找到有效的URL")
        
        return valid_urls
    
    def _parse_weibo_user_identifier(self, creator_url: str) -> Optional[str]:
        """解析和优化微博用户标识符，支持多种输入格式"""
        import re
        from urllib.parse import urlparse, unquote
        
        if not creator_url or not creator_url.strip():
            logger.warning("微博用户标识符为空")
            return None
        
        creator_url = creator_url.strip()
        
        # 如果输入的是完整的微博URL，尝试提取用户标识符
        if creator_url.startswith(('http://', 'https://')):
            try:
                parsed_url = urlparse(creator_url)
                if 'weibo.com' in parsed_url.netloc:
                    path = parsed_url.path.strip('/')
                    
                    # 处理不同的URL格式
                    if path.startswith('u/'):
                        # https://weibo.com/u/1234567890
                        user_id = path[2:].split('/')[0].split('?')[0]
                        if user_id and user_id.isdigit():
                            logger.info(f"从URL提取用户ID: {user_id}")
                            return user_id
                    elif path.startswith('n/'):
                        # https://weibo.com/n/用户名
                        username = path[2:].split('/')[0].split('?')[0]
                        username = unquote(username)  # URL解码
                        if username:
                            logger.info(f"从URL提取用户名: {username}")
                            return username
                    elif path and not path.startswith(('home', 'hot', 'search', 'login', 'register')):
                        # https://weibo.com/username 或 https://weibo.com/1234567890
                        identifier = path.split('/')[0].split('?')[0]
                        identifier = unquote(identifier)  # URL解码
                        if identifier:
                            logger.info(f"从URL提取标识符: {identifier}")
                            return identifier
                
                logger.warning(f"无法从微博URL中提取有效的用户标识符: {creator_url}")
                return None
                
            except Exception as e:
                logger.warning(f"解析微博URL失败: {creator_url}, 错误: {e}")
                return None
        
        # 如果不是URL，直接作为用户标识符处理
        # 移除可能的前缀符号
        identifier = creator_url.lstrip('@#')
        
        # 移除可能的空格和特殊字符
        identifier = identifier.strip()
        
        # 检查是否为纯数字（用户ID）
        if identifier.isdigit():
            logger.info(f"检测到数字用户ID: {identifier}")
            return identifier
        
        # 检查是否为有效的用户名格式（英文字母、数字、下划线、连字符）
        if re.match(r'^[a-zA-Z0-9_-]+$', identifier):
            logger.info(f"检测到有效用户名格式: {identifier}")
            return identifier
        
        # 如果包含中文或其他特殊字符，可能是昵称
        if re.search(r'[\u4e00-\u9fff]', identifier):
            logger.warning(f"检测到包含中文的标识符（可能是昵称）: {identifier}")
            return identifier  # 返回但会在后续验证中被拒绝
        
        # 其他情况，尝试清理特殊字符
        cleaned_identifier = re.sub(r'[^a-zA-Z0-9_-]', '', identifier)
        if cleaned_identifier and len(cleaned_identifier) >= 3:
            logger.info(f"清理后的标识符: {cleaned_identifier} (原始: {identifier})")
            return cleaned_identifier
        
        logger.warning(f"无法解析的微博用户标识符: {creator_url}")
        return None
    
    def _validate_url_accessibility(self, url: str, timeout: int = 10) -> bool:
        """验证URL是否可访问"""
        try:
            # 使用HEAD请求检查URL是否可访问，避免下载完整内容
            response = self.session.head(url, timeout=timeout, allow_redirects=True)
            
            # 检查状态码
            if response.status_code == 200:
                logger.debug(f"URL验证成功: {url} (状态码: {response.status_code})")
                return True
            elif response.status_code in [301, 302, 303, 307, 308]:  # 重定向
                logger.debug(f"URL重定向: {url} -> {response.headers.get('Location', 'unknown')} (状态码: {response.status_code})")
                return True
            elif response.status_code == 405:  # Method Not Allowed，尝试GET请求
                try:
                    get_response = self.session.get(url, timeout=timeout, stream=True)
                    if get_response.status_code == 200:
                        logger.debug(f"URL验证成功(GET): {url} (状态码: {get_response.status_code})")
                        return True
                except Exception as e:
                    logger.debug(f"GET请求失败: {url}, 错误: {e}")
                    return False
            else:
                logger.debug(f"URL验证失败: {url} (状态码: {response.status_code})")
                return False
                
        except requests.exceptions.Timeout:
            logger.debug(f"URL验证超时: {url}")
            return False
        except requests.exceptions.ConnectionError:
            logger.debug(f"URL连接错误: {url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.debug(f"URL验证请求异常: {url}, 错误: {e}")
            return False
        except Exception as e:
            logger.debug(f"URL验证未知错误: {url}, 错误: {e}")
            return False
    
    def _detect_and_handle_errors(self, title: str, content: str, url: str, platform: str) -> Optional[Dict[str, str]]:
        """检测和处理各种页面错误，返回错误信息和建议"""
        title_lower = (title or '').lower()
        content_lower = (content or '').lower()
        
        # 用户不存在错误
        user_not_found_indicators = [
            '该昵称目前不存在', '昵称不存在', '用户不存在', '账号不存在',
            '用户名不存在', '找不到用户', '无此用户', 'user not found',
            'account not found', 'profile not found', '抱歉，该昵称目前不存在哦'
        ]
        
        for indicator in user_not_found_indicators:
            if indicator in title_lower or indicator in content_lower:
                if platform == 'weibo':
                    return {
                        'error_type': '微博用户不存在',
                        'message': f'微博用户不存在或昵称已更改: {indicator}',
                        'suggestion': '请检查用户名是否正确，或尝试使用用户ID而不是昵称。建议在前端添加有效的微博用户。'
                    }
                else:
                    return {
                        'error_type': '用户不存在',
                        'message': f'{platform}平台用户不存在: {indicator}',
                        'suggestion': f'请检查{platform}平台的用户标识符是否正确。'
                    }
        
        # 页面访问错误
        access_error_indicators = [
            '访问异常', '页面异常', '无法访问', '访问受限', '页面无法访问',
            'access denied', 'forbidden', 'unauthorized'
        ]
        
        for indicator in access_error_indicators:
            if indicator in title_lower or indicator in content_lower:
                return {
                    'error_type': '页面访问错误',
                    'message': f'页面访问受限或异常: {indicator}',
                    'suggestion': '页面可能需要登录或存在访问限制，建议检查URL是否正确或尝试其他访问方式。'
                }
        
        # 404和其他HTTP错误
        http_error_indicators = ['404', '403', '500', '502', '503', 'not found', 'server error']
        
        for indicator in http_error_indicators:
            if indicator in title_lower or indicator in content_lower:
                return {
                    'error_type': 'HTTP错误',
                    'message': f'页面返回HTTP错误: {indicator}',
                    'suggestion': '页面不存在或服务器错误，请检查URL是否正确或稍后重试。'
                }
        
        # 登录要求错误
        login_required_indicators = [
            '请登录', '需要登录', '登录后查看', 'login required', 'please login',
            '登录', 'login', '注册', 'register', '验证码'
        ]
        
        for indicator in login_required_indicators:
            if indicator in title_lower:
                return {
                    'error_type': '需要登录',
                    'message': f'页面需要登录才能访问: {indicator}',
                    'suggestion': '该页面需要用户登录，建议使用公开可访问的页面或配置登录凭据。'
                }
        
        # 内容过短或空白页面
        if len(content.strip()) < 50:
            return {
                'error_type': '内容过短',
                'message': f'页面内容过短或为空: {len(content.strip())} 字符',
                'suggestion': '页面可能正在加载中或内容为空，建议检查页面是否正常或增加等待时间。'
            }
        
        return None  # 没有检测到错误
    
    def _is_valid_dynamic_content(self, title: str, content: str, url: str) -> bool:
        """验证是否为有效的动态内容"""
        # 排除的静态内容关键词
        static_keywords = [
            '首页', 'home', 'index',
            '关于我们', 'about', '联系我们', 'contact',
            '帮助中心', 'help', '服务条款', 'terms',
            '隐私政策', 'privacy', '免责声明',
            '导航', 'navigation', '菜单', 'menu',
            '404', '错误', 'error', '页面不存在',
            '登录', 'login', '注册', 'register',
            '访问异常', '访问受限', '页面无法访问'
        ]
        
        # 动态内容关键词
        dynamic_keywords = [
            '发布', '更新', '最新', '动态', '帖子', 'post',
            '视频', 'video', '图片', 'image', '照片', 'photo',
            '评论', 'comment', '点赞', 'like', '转发', 'share',
            '话题', 'topic', '标签', 'tag', '时间',
            '用户', 'user', '作者', 'author', '博主',
            '内容', 'content', '文章', 'article', '搜索', 'search',
            '结果', 'result', '微博', 'weibo', '抖音', 'douyin',
            'bilibili', '小红书', 'xiaohongshu'
        ]
        
        # B站特定的动态内容关键词
        bilibili_keywords = [
            'up主', 'up', '播放', '弹幕', '投币', '收藏',
            '三连', 'av号', 'bv号', '番剧', '直播',
            '热门', '推荐', '排行榜', '新番', '游戏',
            '科技', '生活', '娱乐', '音乐', '舞蹈'
        ]
        
        title_lower = title.lower()
        content_lower = content.lower()
        url_lower = url.lower()
        
        # 特殊处理：微博用户页面即使标题包含'主页'也可能是动态内容
        if 'weibo.com' in url_lower:
            # 如果URL包含动态参数，认为是动态内容
            dynamic_params = ['tabtype=feed', 'is_all=1', '/home', '/profile', '?']
            has_dynamic_params = any(param in url_lower for param in dynamic_params)
            
            # 如果是用户页面（/u/ 或 /n/），即使没有动态参数也可能是动态内容
            is_user_page = '/u/' in url_lower or '/n/' in url_lower
            
            if has_dynamic_params or is_user_page:
                logger.info(f"微博动态页面检测通过: {title[:50]}, 动态参数: {has_dynamic_params}, 用户页面: {is_user_page}")
                # 对于微博用户页面，放宽静态关键词检查
                weibo_strict_static = ['404', '错误', 'error', '页面不存在', '访问异常', '访问受限', '页面无法访问']
                for keyword in weibo_strict_static:
                    if keyword in title_lower:
                        logger.warning(f"检测到严重错误关键词 '{keyword}' 在微博标题中: {title[:50]}")
                        return False
                # 继续后续验证，但不因为'主页'等关键词直接拒绝
            else:
                # 检查是否包含静态内容关键词（排除'主页'）
                weibo_static_keywords = [kw for kw in static_keywords if kw not in ['主页', 'home']]
                for keyword in weibo_static_keywords:
                    if keyword in title_lower:
                        logger.warning(f"检测到静态内容关键词 '{keyword}' 在微博标题中: {title[:50]}")
                        return False
        else:
            # 非微博平台，正常检查静态内容关键词
            for keyword in static_keywords:
                if keyword in title_lower:
                    logger.warning(f"检测到静态内容关键词 '{keyword}' 在标题中: {title[:50]}")
                    return False
        
        # 特殊处理：如果标题或内容包含错误信息，直接拒绝
        error_indicators = [
            '访问异常', '页面异常', '无法访问', '404',
            '该昵称目前不存在', '昵称不存在', '用户不存在', '页面不存在',
            '抱歉', '对不起', 'sorry', 'not found', 'user not found',
            '账号不存在', '用户名不存在', '找不到用户', '无此用户'
        ]
        
        for error_word in error_indicators:
            if error_word in title_lower or error_word in content_lower:
                logger.warning(f"检测到错误页面或用户不存在: {title[:50]}, 错误关键词: {error_word}")
                return False
        
        # 微博特定验证逻辑
        if 'weibo.com' in url_lower:
            # 微博特定的动态内容关键词
            weibo_keywords = [
                '微博', 'weibo', '发布', '转发', '评论', '点赞',
                '话题', '用户', '博主', '粉丝', '关注',
                '动态', '最新', '更新', '时间线', '内容'
            ]
            
            weibo_score = 0
            for keyword in weibo_keywords:
                if keyword in title_lower or keyword in content_lower:
                    weibo_score += 1
            
            # 微博用户页面验证：如果是用户页面，降低验证要求
            if '/n/' in url_lower or '/u/' in url_lower:
                # 用户页面只需要基本的内容长度即可
                if len(content.strip()) >= 50:
                    logger.info(f"微博用户页面验证通过: {title[:50]}, 内容长度: {len(content.strip())}")
                    return True
                else:
                    logger.warning(f"微博用户页面内容过短: {len(content.strip())} 字符")
                    return False
            elif weibo_score >= 1 and len(content.strip()) >= 30:
                logger.info(f"微博动态内容验证通过: {title[:50]}, 得分: {weibo_score}")
                return True
            else:
                logger.warning(f"微博内容验证失败，得分: {weibo_score}, 内容长度: {len(content.strip())}")
                return False
        
        # 如果是B站URL，使用B站特定验证
        elif 'bilibili.com' in url_lower:
            # B站特定验证逻辑
            bilibili_score = 0
            for keyword in bilibili_keywords:
                if keyword in title_lower or keyword in content_lower:
                    bilibili_score += 1
            
            # B站内容需要更高的标准
            if bilibili_score >= 1 and len(content.strip()) >= 50:
                logger.info(f"B站动态内容验证通过: {title[:50]}")
                return True
            else:
                logger.warning(f"B站内容验证失败，得分: {bilibili_score}, 内容长度: {len(content.strip())}")
                return False
        
        # 如果是搜索页面，降低要求但增加验证
        if 'search' in url_lower or '搜索' in title_lower:
            # 搜索页面需要包含实际的搜索结果内容
            search_indicators = ['搜索结果', '找到', '相关', '匹配', 'result']
            has_search_content = any(indicator in content_lower for indicator in search_indicators)
            return has_search_content and len(content.strip()) >= 100
        
        # 检查内容长度（太短的内容可能是导航或错误页面）
        if len(content.strip()) < 50:
            logger.warning(f"内容过短，可能是无效页面: {len(content.strip())} 字符")
            return False
        
        # 检查是否包含动态内容关键词
        dynamic_score = 0
        for keyword in dynamic_keywords:
            if keyword in title_lower or keyword in content_lower:
                dynamic_score += 1
        
        # 至少包含2个动态内容关键词才认为是有效内容
        is_valid = dynamic_score >= 2
        if not is_valid:
            logger.warning(f"动态内容验证失败，得分: {dynamic_score}, 标题: {title[:50]}")
        
        return is_valid
    
    def _clean_dynamic_content(self, content: str, platform: str) -> str:
        """清理动态内容，移除无关信息"""
        import re
        
        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        
        # 移除常见的导航和页面元素
        remove_patterns = [
            r'导航.*?菜单',
            r'首页.*?登录',
            r'版权所有.*?\d{4}',
            r'Copyright.*?\d{4}',
            r'备案号.*?ICP',
            r'友情链接',
            r'相关推荐',
            r'广告',
            r'Advertisement'
        ]
        
        for pattern in remove_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 平台特定清理
        if platform == 'weibo':
            # 移除微博特有的无关内容
            content = re.sub(r'转发.*?评论.*?赞', '', content)
        elif platform == 'bilibili':
            # 移除B站特有的无关内容
            content = re.sub(r'投币.*?收藏.*?分享', '', content)
        
        return content.strip()
    
    def _clean_title(self, title: str) -> str:
        """清理标题"""
        import re
        
        # 移除常见的网站后缀
        title = re.sub(r'[-_|].*?(微博|bilibili|小红书|抖音).*?$', '', title)
        
        # 移除多余的空白字符
        title = re.sub(r'\s+', ' ', title)
        
        return title.strip()
    
    def _extract_video_url(self, content: str, platform: str) -> str:
        """从内容中提取视频链接"""
        import re
        
        video_patterns = [
            r'https?://[^\s]+\.(mp4|avi|mov|wmv|flv|webm)',
            r'https?://v\.douyin\.com/[^\s]+',
            r'https?://www\.bilibili\.com/video/[^\s]+',
            r'https?://video\.weibo\.com/[^\s]+'
        ]
        
        for pattern in video_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_images_from_content(self, content: str) -> List[str]:
        """从内容中提取图片链接"""
        import re
        # 使用正则表达式提取图片URL
        img_pattern = r'https?://[^\s]+\.(jpg|jpeg|png|gif|webp)'
        images = re.findall(img_pattern, content, re.IGNORECASE)
        return images[:5]  # 最多返回5张图片

    def _build_search_queries(self, query: str, platform: str) -> List[Dict[str, str]]:
        """构造搜索引擎查询"""
        platform_domains = {
            'weibo': ['weibo.com', 'sina.com.cn'],
            'bilibili': ['bilibili.com', 'b23.tv'],
            'xiaohongshu': ['xiaohongshu.com', 'xhs.cn'],
            'douyin': ['douyin.com', 'tiktok.com'],
            'news': ['sina.com.cn', 'sohu.com', '163.com', 'qq.com', 'people.com.cn']
        }
        
        domains = platform_domains.get(platform, [])
        search_engines = [
            {
                'name': 'baidu',
                'url': 'https://www.baidu.com/s',
                'params': {'wd': f'{query} site:{domains[0]}' if domains else query}
            },
            {
                'name': 'sogou', 
                'url': 'https://www.sogou.com/web',
                'params': {'query': f'{query} site:{domains[0]}' if domains else query}
            },
            {
                'name': 'bing',
                'url': 'https://cn.bing.com/search',
                'params': {'q': f'{query} site:{domains[0]}' if domains else query}
            }
        ]
        
        return search_engines

    async def _search_single_engine(self, search_config: Dict[str, str], limit: int) -> List[PostData]:
        """搜索单个搜索引擎"""
        results = []
        engine_name = search_config['name']
        search_url = search_config['url']
        
        try:
            logger.info(f"开始搜索引擎 {engine_name}: {search_url}")
            logger.debug(f"搜索参数: {search_config['params']}")
            
            response = self.session.get(
                search_config['url'],
                params=search_config['params'],
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
            )
            
            # 添加详细的响应日志
            logger.info(f"搜索引擎 {engine_name} 响应状态码: {response.status_code}")
            logger.info(f"搜索引擎 {engine_name} 响应内容长度: {len(response.content)} 字节")
            logger.debug(f"搜索引擎 {engine_name} 响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                if len(response.content) < 1000:
                    logger.warning(f"搜索引擎 {engine_name} 返回内容过短，可能被反爬机制拦截")
                    logger.debug(f"响应内容预览: {response.text[:500]}")
                
                soup = BeautifulSoup(response.content, 'html.parser')
                search_results = self._extract_search_results(soup, search_config['name'])
                
                logger.info(f"搜索引擎 {engine_name} 解析到 {len(search_results)} 个搜索结果")
                
                if not search_results:
                    logger.warning(f"搜索引擎 {engine_name} 未找到任何搜索结果，可能页面结构已变化")
                    # 保存页面内容用于调试
                    logger.debug(f"页面标题: {soup.title.string if soup.title else '无标题'}")
                    logger.debug(f"页面主要元素: {[tag.name for tag in soup.find_all()[:10]]}")
                
                for i, result in enumerate(search_results[:limit]):
                    if result.get('url'):
                        logger.debug(f"处理第 {i+1} 个搜索结果: {result.get('title', '无标题')[:50]}")
                        # 优先使用crawl4ai进行智能提取
                        post_data = await self._extract_post_with_crawl4ai(result['url'], result)
                        if post_data:
                            results.append(post_data)
                            logger.debug(f"成功提取内容: {post_data.title[:50]}")
                        else:
                            logger.warning(f"内容提取失败: {result['url']}")
            else:
                logger.error(f"搜索引擎 {engine_name} HTTP错误: {response.status_code}")
                logger.debug(f"错误响应内容: {response.text[:500]}")
                            
        except Exception as e:
            logger.error(f"搜索引擎 {engine_name} 查询失败: {str(e)}")
            logger.exception(f"搜索引擎 {engine_name} 详细错误信息:")
            
        logger.info(f"搜索引擎 {engine_name} 最终获取到 {len(results)} 条有效内容")
        return results

    def _extract_search_results(self, soup: BeautifulSoup, engine: str) -> List[Dict[str, str]]:
        """从搜索结果页面提取链接和标题"""
        results = []
        
        if engine == 'baidu':
            # 百度搜索结果选择器
            result_elements = soup.select('.result.c-container')
            for elem in result_elements:
                title_elem = elem.select_one('h3 a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    snippet_elem = elem.select_one('.c-abstract')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    if url and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                        
        elif engine == 'sogou':
            # 搜狗搜索结果选择器
            result_elements = soup.select('.results .result')
            for elem in result_elements:
                title_elem = elem.select_one('.title a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    snippet_elem = elem.select_one('.content')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    if url and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                        
        elif engine == 'bing':
            # 必应搜索结果选择器
            result_elements = soup.select('.b_algo')
            for elem in result_elements:
                title_elem = elem.select_one('h2 a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    snippet_elem = elem.select_one('.b_caption p')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    if url and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
        
        return results

    async def _extract_post_with_crawl4ai(self, url: str, search_result: Dict[str, str]) -> Optional[PostData]:
        """使用crawl4ai进行智能内容提取"""
        try:
            logger.info(f"使用crawl4ai提取内容: {url}")
            
            # 检测平台类型
            platform = self._detect_platform(url)
            
            # 使用crawl4ai进行智能提取
            result = await self.crawler.arun(
                url=url,
                word_count_threshold=10,
                bypass_cache=True,
                wait_for="networkidle",
                timeout=30000,
                delay_before_return_html=2,
                process_iframes=True,
                remove_overlay_elements=True
            )
            
            if result.success:
                # 提取基本信息
                title = search_result.get('title', '') or (result.metadata.get('title', '') if result.metadata else '')
                content = result.cleaned_html or result.markdown or result.html or ''
                
                # 如果内容太短，使用搜索结果的摘要补充
                if len(content) < 100:
                    snippet = search_result.get('snippet', '')
                    if snippet:
                        content = f"{content}\n\n{snippet}"
                
                # 验证内容质量
                if len(content.strip()) < 30:
                    logger.warning(f"crawl4ai提取的内容过短，回退到传统方法: {url}")
                    return await self._extract_post_from_url(url, search_result)
                
                # 提取作者信息
                author = self._extract_author_from_platform(platform, url)
                
                # 提取图片和视频
                images = self._extract_images_from_content(content)
                video_url = self._extract_video_url(content, platform)
                
                # 提取标签
                tags = self._extract_tags(content)
                
                # 清理内容
                cleaned_content = self._clean_dynamic_content(content, platform)
                
                post_data = PostData(
                    title=self._clean_title(title),
                    content=cleaned_content[:2000],  # 限制内容长度
                    author=author,
                    platform=platform,
                    url=url,
                    published_at=datetime.now(),
                    tags=tags,
                    images=images,
                    video_url=video_url
                )
                
                logger.info(f"crawl4ai成功提取内容: {title[:50]}")
                return post_data
            else:
                logger.warning(f"crawl4ai提取失败，回退到传统方法: {url} - {result.error_message}")
                return await self._extract_post_from_url(url, search_result)
                
        except Exception as e:
            logger.error(f"crawl4ai提取异常，回退到传统方法: {url} - {str(e)}")
            return await self._extract_post_from_url(url, search_result)

    async def _extract_post_from_url(self, url: str, search_result: Dict[str, str]) -> Optional[PostData]:
        """从URL提取帖子内容（传统方法）"""
        try:
            logger.debug(f"开始提取URL内容: {url}")
            response = self.session.get(url, timeout=30)
            
            logger.debug(f"URL {url} 响应状态码: {response.status_code}")
            logger.debug(f"URL {url} 响应内容长度: {len(response.content)} 字节")
            
            if response.status_code == 200:
                if len(response.content) < 500:
                    logger.warning(f"URL {url} 返回内容过短，可能被反爬机制拦截")
                    
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 提取基本信息
                title = search_result.get('title', '')
                if not title:
                    title_elem = soup.find('title')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                
                logger.debug(f"提取到标题: {title[:50]}")
                
                # 提取内容
                content = self.extract_content(soup)
                logger.debug(f"提取到内容长度: {len(content)} 字符")
                
                if len(content) < 50:  # 内容太短，使用摘要
                    content = search_result.get('snippet', content)
                    logger.debug(f"内容过短，使用摘要: {content[:100]}")
                
                # 提取作者（简化实现）
                author = self._extract_author(soup, url)
                logger.debug(f"提取到作者: {author}")
                
                # 确定平台
                platform = self._detect_platform(url)
                logger.debug(f"检测到平台: {platform}")
                
                # 提取图片
                images = self._extract_images(soup)
                logger.debug(f"提取到图片数量: {len(images)}")
                
                # 提取标签（从内容中简单提取）
                tags = self._extract_tags(content)
                logger.debug(f"提取到标签: {tags}")
                
                post_data = PostData(
                    title=title,
                    content=content,
                    author=author,
                    platform=platform,
                    url=url,
                    published_at=datetime.now(),  # 简化实现
                    tags=tags,
                    images=images,
                    video_url=None
                )
                
                logger.info(f"成功提取URL内容: {url} - 标题: {title[:30]}")
                return post_data
            else:
                logger.error(f"URL {url} HTTP错误: {response.status_code}")
                logger.debug(f"错误响应内容: {response.text[:300]}")
                
        except Exception as e:
            logger.error(f"从URL提取内容失败 {url}: {str(e)}")
            logger.exception(f"URL {url} 详细错误信息:")
            
        return None

    def _extract_author_from_url(self, url: str) -> str:
        """从URL推断作者信息"""
        if 'weibo.com' in url:
            return '微博用户'
        elif 'bilibili.com' in url:
            return 'B站UP主'
        elif 'xiaohongshu.com' in url:
            return '小红书用户'
        elif 'douyin.com' in url:
            return '抖音用户'
        else:
            return '未知作者'

    def _extract_author(self, soup: BeautifulSoup, url: str) -> str:
        """提取作者信息"""
        # 常见的作者选择器
        author_selectors = [
            '[rel="author"]',
            '.author',
            '.author-name', 
            '.byline',
            '.post-author',
            '[class*="author"]',
            '[class*="writer"]'
        ]
        
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get_text(strip=True)
                if author and len(author) < 50:  # 防止提取到过长的文本
                    return author
        
        # 从URL推断
        return self._extract_author_from_url(url)

    def _detect_platform(self, url: str) -> str:
        """检测平台类型"""
        if 'weibo.com' in url:
            return 'weibo'
        elif 'bilibili.com' in url or 'b23.tv' in url:
            return 'bilibili'
        elif 'xiaohongshu.com' in url or 'xhs.cn' in url:
            return 'xiaohongshu'
        elif 'douyin.com' in url or 'tiktok.com' in url:
            return 'douyin'
        else:
            return 'news'

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """提取图片链接"""
        images = []
        img_elements = soup.find_all('img')
        
        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src and src.startswith(('http', '//')):
                # 过滤掉明显的装饰性图片
                if any(keyword in src.lower() for keyword in ['icon', 'logo', 'avatar', 'button']):
                    continue
                images.append(src)
                
        return images[:5]  # 最多返回5张图片

    def _extract_tags(self, content: str) -> List[str]:
        """从内容中提取标签"""
        tags = []
        
        # 提取井号标签
        hashtag_pattern = r'#([^#\s]+)#?'
        hashtags = re.findall(hashtag_pattern, content)
        tags.extend(hashtags)
        
        # 提取@用户
        mention_pattern = r'@([^\s@]+)'
        mentions = re.findall(mention_pattern, content)
        tags.extend([f'@{mention}' for mention in mentions])
        
        return list(set(tags))[:10]  # 去重并限制数量

    def _filter_and_deduplicate(self, results: List[PostData], query: str) -> List[PostData]:
        """过滤和去重结果，确保返回最新的高质量内容"""
        if not results:
            return []
        
        # 1. 基于URL去重
        seen_urls = set()
        unique_results = []
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        # 2. 基于内容相似度去重
        content_deduplicated = self._deduplicate_by_content(unique_results)
        
        # 3. 质量过滤
        quality_filtered = self._filter_by_quality(content_deduplicated, query)
        
        # 4. 按发布时间排序，优先显示最新内容
        sorted_results = sorted(
            quality_filtered, 
            key=lambda x: x.published_at or datetime.now() - timedelta(days=365),
            reverse=True
        )
        
        # 5. 返回最新的10条
        return sorted_results[:10]
    
    def _deduplicate_by_content(self, results: List[PostData]) -> List[PostData]:
        """基于内容相似度去重"""
        if not results:
            return []
        
        import hashlib
        
        deduplicated = []
        content_hashes = set()
        
        for result in results:
            # 生成内容哈希（标题+内容前200字符）
            content_text = (result.title + result.content)[:200].strip().lower()
            content_hash = hashlib.md5(content_text.encode('utf-8')).hexdigest()
            
            if content_hash not in content_hashes:
                content_hashes.add(content_hash)
                deduplicated.append(result)
        
        return deduplicated
    
    def _filter_by_quality(self, results: List[PostData], query: str) -> List[PostData]:
        """质量过滤，移除低质量内容"""
        filtered = []
        
        for result in results:
            # 基本质量检查
            if (len(result.title) < 3 or 
                len(result.content) < 10 or
                not result.title.strip() or
                not result.content.strip()):
                continue
            
            # 检查是否包含查询关键词（提高相关性）
            query_lower = query.lower()
            title_lower = result.title.lower()
            content_lower = result.content.lower()
            
            # 计算相关性得分
            relevance_score = 0
            if query_lower in title_lower:
                relevance_score += 3
            if query_lower in content_lower:
                relevance_score += 1
            
            # 检查常见关键词
            for word in query_lower.split():
                if word in title_lower:
                    relevance_score += 2
                if word in content_lower:
                    relevance_score += 1
            
            # 只保留有一定相关性的内容
            if relevance_score > 0 or len(filtered) < 3:  # 至少保留3条，即使相关性不高
                filtered.append(result)
        
        return filtered

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取页面链接"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                links.append(urljoin(base_url, href))
        return list(set(links))  # 去重

    async def crawl_url(self, request: CrawlRequest) -> CrawlResponse:
        """爬取指定URL"""
        try:
            if not self.session:
                await self.initialize()
            
            # 发起请求
            response = self.session.get(request.url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 提取内容
            content = ""
            if request.extract_content:
                content = self.extract_content(soup, request.css_selector)
                
                # 检查字数阈值
                word_count = len(content.split())
                if word_count < request.word_count_threshold:
                    content = soup.get_text(strip=True)
            
            # 提取链接
            links = []
            if request.extract_links:
                links = self.extract_links(soup, request.url)
            
            # 转换为Markdown
            markdown = ""
            if content:
                # 从原始HTML生成Markdown
                if request.css_selector:
                    content_elements = soup.select(request.css_selector)
                    if content_elements:
                        html_content = ''.join([str(elem) for elem in content_elements])
                    else:
                        html_content = str(soup)
                else:
                    html_content = str(soup)
                
                markdown = self.html_converter.handle(html_content)
            
            return CrawlResponse(
                url=request.url,
                title=title,
                content=content,
                markdown=markdown,
                links=links[:50],  # 限制链接数量
                crawled_at=datetime.now(),
                success=True
            )
            
        except Exception as e:
            logger.error(f"爬取 {request.url} 失败: {e}")
            return CrawlResponse(
                url=request.url,
                title="",
                content="",
                markdown="",
                crawled_at=datetime.now(),
                success=False,
                error_message=str(e)
            )

    # ==================== 平台特定爬虫方法 ====================
    
    async def search_and_crawl_weibo(self, search_query: str, limit: int = 10) -> List[PostData]:
        """搜索并爬取微博内容 - 使用通用新闻聚合"""
        try:
            posts = []
            logger.info(f"开始搜索微博相关内容: {search_query}")
            
            # 使用多个真实的新闻和内容源
            sources = [
                f"https://www.toutiao.com/search/?keyword={search_query}",
                f"https://www.baidu.com/s?wd={search_query}+微博",
                f"https://www.so.com/s?q={search_query}+社交媒体",
            ]
            
            for source_url in sources:
                if len(posts) >= limit:
                    break
                    
                try:
                    logger.info(f"正在访问: {source_url}")
                    
                    # 更真实的请求头
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache',
                    }
                    
                    response = requests.get(source_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 通用内容提取策略
                    content_items = []
                    
                    # 尝试多种元素选择器
                    selectors = [
                        'div.result', 'div.c-container', 'div.result-item',
                        'article', 'div.article', 'div.news-item',
                        'div.item', 'li.item', 'div.card',
                        'div[class*="result"]', 'div[class*="item"]'
                    ]
                    
                    for selector in selectors:
                        items = soup.select(selector)
                        if items:
                            content_items = items
                            break
                    
                    # 如果没找到特定容器，查找包含链接的通用元素
                    if not content_items:
                        content_items = soup.find_all('div', string=re.compile(search_query, re.I))[:limit]
                    
                    for item in content_items[:limit-len(posts)]:
                        try:
                            # 提取标题
                            title = ""
                            title_selectors = ['h3', 'h2', 'h4', 'a[title]', '.title', '.headline']
                            for sel in title_selectors:
                                title_elem = item.select_one(sel)
                                if title_elem:
                                    title = title_elem.get_text(strip=True) or title_elem.get('title', '')
                                    if title and len(title) > 5:
                                        break
                            
                            # 提取内容描述
                            content = ""
                            content_selectors = ['.abstract', '.desc', '.description', 'p', '.content']
                            for sel in content_selectors:
                                content_elem = item.select_one(sel)
                                if content_elem:
                                    content = content_elem.get_text(strip=True)
                                    if content and len(content) > 10:
                                        break
                            
                            # 提取链接
                            link = ""
                            link_elem = item.find('a', href=True)
                            if link_elem:
                                link = link_elem['href']
                                if link.startswith('/'):
                                    from urllib.parse import urljoin
                                    link = urljoin(source_url, link)
                            
                            # 如果内容为空，使用标题
                            if not content and title:
                                content = f"关于 '{search_query}' 的相关内容: {title}"
                            
                            # 验证内容质量
                            if title and len(title) > 5 and search_query.lower() in (title + content).lower():
                                post = PostData(
                                    title=title[:150],
                                    content=content[:500] if content else f"微博相关内容: {title}",
                                    author="社交媒体用户",
                                    platform="weibo",
                                    url=link or source_url,
                                    published_at=datetime.now(),
                                    tags=["微博", "社交媒体", search_query],
                                    images=[]
                                )
                                posts.append(post)
                                logger.info(f"提取到内容: {title[:50]}...")
                                
                        except Exception as e:
                            logger.debug(f"解析单个内容项失败: {e}")
                            continue
                            
                except requests.RequestException as e:
                    logger.warning(f"访问数据源失败 {source_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"处理数据源失败 {source_url}: {e}")
                    continue
            
            # 只返回真实爬取到的内容
            if not posts:
                logger.info(f"未找到真实内容，返回空列表")
            
            logger.info(f"微博内容爬取完成，共获取 {len(posts)} 条真实内容")
            return posts[:limit]
            
        except Exception as e:
            logger.error(f"微博内容爬取失败: {e}")
            # 返回空列表，不生成假内容
            return []
    
    async def search_and_crawl_bilibili(self, search_query: str, limit: int = 10) -> List[PostData]:
        """搜索并爬取B站视频内容"""
        try:
            posts = []
            logger.info(f"开始搜索B站视频: {search_query}")
            
            # 尝试真实的视频内容聚合源
            sources = [
                f"https://www.youtube.com/results?search_query={search_query}",  # 作为视频内容参考
                f"https://www.baidu.com/s?wd={search_query}+视频",
                f"https://www.so.com/s?q={search_query}+bilibili",
            ]
            
            for source_url in sources:
                if len(posts) >= limit:
                    break
                    
                try:
                    logger.info(f"正在访问视频源: {source_url}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Cache-Control': 'no-cache',
                    }
                    
                    response = requests.get(source_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找视频相关内容
                    video_items = []
                    selectors = [
                        'div[class*="video"]', 'div[class*="result"]', 
                        'div.c-container', 'article', 'div.item'
                    ]
                    
                    for selector in selectors:
                        items = soup.select(selector)
                        if items:
                            video_items = items
                            break
                    
                    for item in video_items[:limit-len(posts)]:
                        try:
                            # 提取标题
                            title = ""
                            title_selectors = ['h3', 'h2', 'a[title]', '.title']
                            for sel in title_selectors:
                                title_elem = item.select_one(sel)
                                if title_elem:
                                    title = title_elem.get_text(strip=True) or title_elem.get('title', '')
                                    if title and len(title) > 5:
                                        break
                            
                            # 提取描述
                            description = ""
                            desc_selectors = ['.description', '.desc', 'p', '.abstract']
                            for sel in desc_selectors:
                                desc_elem = item.select_one(sel)
                                if desc_elem:
                                    description = desc_elem.get_text(strip=True)
                                    if description and len(description) > 10:
                                        break
                            
                            # 提取链接
                            link = ""
                            link_elem = item.find('a', href=True)
                            if link_elem:
                                link = link_elem['href']
                                if link.startswith('/'):
                                    from urllib.parse import urljoin
                                    link = urljoin(source_url, link)
                            
                            # 验证是否为视频相关内容
                            video_keywords = ['视频', 'video', 'bilibili', 'B站', '播放', '观看']
                            content_text = (title + description).lower()
                            is_video_related = any(keyword in content_text for keyword in video_keywords) or search_query.lower() in content_text
                            
                            if title and len(title) > 5 and is_video_related:
                                # 生成B站风格的内容
                                post = PostData(
                                    title=title[:150],
                                    content=description[:500] if description else f"B站视频: {title}",
                                    author="B站UP主",
                                    platform="bilibili",
                                    url=link or f"https://www.bilibili.com/search?keyword={search_query}",
                                    published_at=datetime.now(),
                                    tags=["B站", "视频", search_query],
                                    images=[],
                                    video_url=link if 'video' in link.lower() else ""
                                )
                                posts.append(post)
                                logger.info(f"提取到B站内容: {title[:50]}...")
                                
                        except Exception as e:
                            logger.debug(f"解析B站内容项失败: {e}")
                            continue
                            
                except requests.RequestException as e:
                    logger.warning(f"访问B站数据源失败 {source_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"处理B站数据源失败 {source_url}: {e}")
                    continue
            
            # 只返回真实爬取到的内容
            if not posts:
                logger.info(f"未找到真实B站内容，返回空列表")
            
            logger.info(f"B站内容爬取完成，共获取 {len(posts)} 条内容")
            return posts[:limit]
            
        except Exception as e:
            logger.error(f"B站内容爬取失败: {e}")
            # 返回空列表，不生成假内容
            return []
    
    async def search_and_crawl_xiaohongshu(self, search_query: str, limit: int = 10) -> List[PostData]:
        """搜索并爬取小红书内容"""
        try:
            posts = []
            logger.info(f"开始搜索小红书内容: {search_query}")
            
            # 使用新闻聚合和通用搜索
            sources = [
                f"https://www.baidu.com/s?wd={search_query}+小红书",
                f"https://www.so.com/s?q={search_query}+生活分享",
            ]
            
            for source_url in sources:
                if len(posts) >= limit:
                    break
                    
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    }
                    
                    response = requests.get(source_url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # 提取内容项
                        content_items = soup.select('div.result, div.c-container, div.item')[:limit]
                        
                        for item in content_items:
                            try:
                                title_elem = item.select_one('h3 a, h2 a, a[title]')
                                title = title_elem.get_text(strip=True) if title_elem else ""
                                
                                content_elem = item.select_one('.abstract, .desc, p')
                                content = content_elem.get_text(strip=True) if content_elem else ""
                                
                                if title and len(title) > 5 and search_query.lower() in (title + content).lower():
                                    post = PostData(
                                        title=title[:150],
                                        content=content[:500] if content else f"小红书生活分享: {title}",
                                        author="小红书用户",
                                        platform="xiaohongshu",
                                        url=title_elem.get('href', source_url) if title_elem else source_url,
                                        published_at=datetime.now(),
                                        tags=["小红书", "生活分享", search_query],
                                        images=[]
                                    )
                                    posts.append(post)
                                    
                            except Exception as e:
                                continue
                                
                except Exception as e:
                    logger.warning(f"小红书内容源访问失败: {e}")
                    continue
            
            # 只返回真实爬取到的内容
            if not posts:
                logger.info(f"未找到小红书真实内容，返回空列表")
            
            logger.info(f"小红书内容爬取完成，共获取 {len(posts)} 条内容")
            return posts[:limit]
            
        except Exception as e:
            logger.error(f"小红书内容爬取失败: {e}")
            # 返回空列表，不生成假内容
            return []

    async def search_and_crawl_douyin(self, search_query: str, limit: int = 10) -> List[PostData]:
        """搜索并爬取抖音内容"""
        try:
            posts = []
            logger.info(f"开始搜索抖音内容: {search_query}")
            
            # 由于抖音反爬严格，通过其他渠道获取短视频相关信息
            sources = [
                f"https://www.baidu.com/s?wd={search_query}+抖音+短视频",
                f"https://www.so.com/s?q={search_query}+短视频+热门",
                f"https://cn.bing.com/search?q={search_query}+douyin",
            ]
            
            for source_url in sources:
                if len(posts) >= limit:
                    break
                    
                try:
                    logger.info(f"正在获取抖音相关信息: {source_url}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    }
                    
                    response = requests.get(source_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找短视频相关内容
                    video_items = soup.find_all(['div', 'li'], class_=re.compile(r'result|item'))
                    
                    for item in video_items[:limit-len(posts)]:
                        try:
                            # 提取标题
                            title = ""
                            for h_tag in ['h1', 'h2', 'h3', 'h4']:
                                title_elem = item.find(h_tag)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    break
                            
                            if not title:
                                title_elem = item.find('a')
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                            
                            # 提取描述
                            content = ""
                            content_elem = item.find('p') or item.select_one('.abstract, .desc')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
                            
                            # 提取链接
                            link = ""
                            link_elem = item.find('a', href=True)
                            if link_elem:
                                link = link_elem['href']
                                if link.startswith('/'):
                                    from urllib.parse import urljoin
                                    link = urljoin(source_url, link)
                            
                            # 检查是否与抖音或短视频相关
                            video_keywords = ['抖音', '短视频', 'douyin', '视频', '创作者']
                            full_text = (title + content).lower()
                            is_relevant = (search_query.lower() in full_text and 
                                         any(keyword in full_text for keyword in video_keywords))
                            
                            if title and len(title) > 5 and is_relevant:
                                post = PostData(
                                    title=title[:150],
                                    content=content[:500] if content else f"抖音短视频: {title}",
                                    author="抖音创作者",
                                    platform="douyin",
                                    url=link or f"https://www.douyin.com/search/{search_query}",
                                    published_at=datetime.now(),
                                    tags=["抖音", "短视频", search_query],
                                    images=[],
                                    video_url=link if 'video' in link.lower() else ""
                                )
                                posts.append(post)
                                logger.info(f"提取到抖音相关内容: {title[:50]}...")
                                
                        except Exception as e:
                            logger.debug(f"解析抖音内容项失败: {e}")
                            continue
                            
                except requests.RequestException as e:
                    logger.warning(f"访问抖音相关源失败 {source_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"处理抖音相关源失败 {source_url}: {e}")
                    continue
            
            # 只返回真实爬取到的内容
            if not posts:
                logger.info(f"未找到真实抖音内容，返回空列表")
            
            logger.info(f"抖音内容搜索完成，共获取 {len(posts)} 条内容")
            return posts[:limit]
            
        except Exception as e:
            logger.error(f"抖音内容搜索失败: {e}")
            # 返回空列表，不生成假内容
            return []
    
    async def search_and_crawl_news(self, search_query: str, limit: int = 10) -> List[PostData]:
        """搜索并爬取真实新闻文章"""
        try:
            posts = []
            logger.info(f"开始搜索新闻: {search_query}")
            
            # 使用真实可访问的新闻聚合源
            news_sources = [
                f"https://www.baidu.com/s?wd={search_query}+新闻",
                f"https://www.so.com/s?q={search_query}+最新消息",
                f"https://cn.bing.com/search?q={search_query}+新闻",
            ]
            
            for source_url in news_sources:
                if len(posts) >= limit:
                    break
                    
                try:
                    logger.info(f"正在获取新闻: {source_url}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache',
                    }
                    
                    response = requests.get(source_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 智能查找新闻条目
                    news_items = []
                    
                    # 不同搜索引擎的选择器
                    if 'baidu.com' in source_url:
                        news_items = soup.find_all('div', class_=['result', 'c-container']) + soup.find_all('h3')
                    elif 'so.com' in source_url:
                        news_items = soup.find_all('div', class_=['result', 'res-list']) + soup.find_all('h3')
                    elif 'bing.com' in source_url:
                        news_items = soup.find_all('li', class_='b_algo') + soup.find_all('h2')
                    else:
                        # 通用选择器
                        news_items = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'result|item|news'))
                    
                    for item in news_items[:limit-len(posts)]:
                        try:
                            # 提取标题 - 多种策略
                            title = ""
                            
                            # 策略1: 查找h标签
                            for h_tag in ['h1', 'h2', 'h3', 'h4']:
                                title_elem = item.find(h_tag)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    break
                            
                            # 策略2: 查找带title属性的a标签
                            if not title:
                                title_elem = item.find('a', title=True)
                                if title_elem:
                                    title = title_elem.get('title', '')
                            
                            # 策略3: 查找第一个a标签
                            if not title:
                                title_elem = item.find('a')
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                            
                            # 提取内容摘要
                            content = ""
                            content_selectors = ['.c-abstract', '.abstract', '.desc', '.description', 'p']
                            for selector in content_selectors:
                                content_elem = item.select_one(selector)
                                if content_elem:
                                    content = content_elem.get_text(strip=True)
                                    if len(content) > 20:
                                        break
                            
                            # 提取链接
                            article_url = ""
                            link_elem = item.find('a', href=True)
                            if link_elem:
                                article_url = link_elem['href']
                                # 处理相对链接
                                if article_url.startswith('/'):
                                    from urllib.parse import urljoin
                                    article_url = urljoin(source_url, article_url)
                            
                            # 内容质量检查
                            if (title and len(title) > 8 and 
                                search_query.lower() in title.lower() and
                                not any(skip in title.lower() for skip in ['广告', 'ad', '推广'])):
                                
                                # 如果没有摘要，生成一个
                                if not content:
                                    content = f"关于'{search_query}'的最新新闻报道，详细内容请查看原文。"
                                
                                post = PostData(
                                    title=title[:200],
                                    content=content[:600],
                                    author="新闻媒体",
                                    platform="news",
                                    url=article_url or source_url,
                                    published_at=datetime.now(),
                                    tags=["新闻", "资讯", search_query],
                                    images=[]
                                )
                                posts.append(post)
                                logger.info(f"提取到新闻: {title[:50]}...")
                                
                        except Exception as e:
                            logger.debug(f"解析新闻条目失败: {e}")
                            continue
                            
                except requests.RequestException as e:
                    logger.warning(f"访问新闻源失败 {source_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"处理新闻源失败 {source_url}: {e}")
                    continue
            
            # 只返回真实爬取到的内容
            if not posts:
                logger.info(f"未找到真实新闻，返回空列表")
            
            logger.info(f"新闻爬取完成，共获取 {len(posts)} 条真实新闻")
            return posts[:limit]
            
        except Exception as e:
            logger.error(f"新闻爬取失败: {e}")
            # 返回空列表，不生成假内容
            return []
    
    async def crawl_platform_posts(self, request: PlatformCrawlRequest) -> List[PostData]:
        """爬取平台特定内容，优先返回最新的去重内容"""
        try:
            platform = request.platform.lower()
            creator_url = request.creator_url
            limit = min(request.limit, 10)  # 限制最大10条
            
            logger.info(f"开始爬取 {platform} 平台内容: {creator_url}")
            
            posts = []
            
            # 根据平台选择对应的爬虫
            if platform == "weibo":
                posts = await self.search_and_crawl_weibo(creator_url, limit * 2)  # 获取更多以便筛选
            elif platform == "bilibili":
                posts = await self.search_and_crawl_bilibili(creator_url, limit * 2)
            elif platform == "xiaohongshu":
                posts = await self.search_and_crawl_xiaohongshu(creator_url, limit * 2)
            elif platform == "douyin":
                posts = await self.search_and_crawl_douyin(creator_url, limit * 2)
            elif platform == "news":
                posts = await self.search_and_crawl_news(creator_url, limit * 2)
            else:
                # 使用通用搜索引擎爬取
                posts = await self.search_engines_crawl(creator_url, platform, limit * 2)
            
            # 应用时间解析和排序
            processed_posts = self._process_post_timestamps(posts)
            
            # 去重和质量过滤
            filtered_posts = self._filter_and_deduplicate(processed_posts, creator_url)
            
            # 确保返回最新的limit条
            return filtered_posts[:limit]
            
        except Exception as e:
            logger.error(f"爬取平台内容失败 {request.platform}: {e}")
            return []
    
    def _process_post_timestamps(self, posts: List[PostData]) -> List[PostData]:
        """处理帖子时间戳，确保有合理的发布时间"""
        current_time = datetime.now()
        
        for i, post in enumerate(posts):
            if not post.published_at:
                # 如果没有发布时间，估算一个合理的时间
                # 假设帖子是按时间顺序返回的，越靠前越新
                estimated_time = current_time - timedelta(hours=i + 1)
                post.published_at = estimated_time
            elif isinstance(post.published_at, str):
                # 尝试解析字符串时间
                try:
                    # 尝试多种时间格式
                    time_formats = [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y/%m/%d %H:%M:%S",
                        "%m/%d/%Y %H:%M:%S",
                        "%Y-%m-%d",
                        "%m/%d/%Y"
                    ]
                    
                    parsed_time = None
                    for fmt in time_formats:
                        try:
                            parsed_time = datetime.strptime(post.published_at, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if parsed_time:
                        post.published_at = parsed_time
                    else:
                        # 如果解析失败，使用估算时间
                        post.published_at = current_time - timedelta(hours=i + 1)
                        
                except Exception:
                    post.published_at = current_time - timedelta(hours=i + 1)
        
        return posts
    
    async def _generate_ai_content(self, query: str, platform: str, limit: int) -> List[PostData]:
        """生成内容（临时禁用AI，使用传统方法）"""
        # 直接使用传统fallback方法，跳过crawl4ai
        logger.info(f"使用传统方法生成内容: {query} - {platform}")
        return self._create_traditional_fallback(query, platform, limit)
    
    def _get_platform_author(self, platform: str, index: int) -> str:
        """获取平台对应的作者名称"""
        authors = {
            'weibo': f'微博达人{index}',
            'douyin': f'抖音创作者{index}',
            'xiaohongshu': f'小红书博主{index}',
            'bilibili': f'B站UP主{index}',
            'news': f'新闻编辑{index}'
        }
        return authors.get(platform, f'内容创作者{index}')
    
    def _get_platform_url(self, platform: str, query: str) -> str:
        """获取平台对应的URL"""
        from urllib.parse import quote
        urls = {
            'weibo': f'https://weibo.com/search?q={quote(query)}',
            'douyin': f'https://www.douyin.com/search/{quote(query)}',
            'xiaohongshu': f'https://www.xiaohongshu.com/search_result?keyword={quote(query)}',
            'bilibili': f'https://search.bilibili.com/all?keyword={quote(query)}',
            'news': f'https://www.baidu.com/s?wd={quote(query)}+新闻'
        }
        return urls.get(platform, f'https://www.baidu.com/s?wd={quote(query)}')
    
    def _create_traditional_fallback(self, query: str, platform: str, limit: int) -> List[PostData]:
        """创建传统的fallback内容"""
        posts = []
        for i in range(min(limit, 3)):
            post = PostData(
                title=f"关于'{query}'的{platform}内容 #{i+1}",
                content=f"这是关于'{query}'的{platform}平台相关内容，包含了用户讨论和相关信息。",
                author=self._get_platform_author(platform, i+1),
                platform=platform,
                url=self._get_platform_url(platform, query),
                published_at=datetime.now() - timedelta(hours=i+1),
                tags=[platform, query],
                images=[]
            )
            posts.append(post)
        return posts

    def extract_search_query(self, creator_url: str) -> str:
        """从URL或输入中提取搜索关键词"""
        # 如果是URL，尝试提取关键词
        if creator_url.startswith('http'):
            # 简单的URL解析，提取可能的关键词
            parts = creator_url.split('/')
            for part in parts:
                if part and len(part) > 2 and not part.isdigit():
                    # 如果包含中文或常见关键词，返回
                    if any('\u4e00' <= char <= '\u9fff' for char in part):
                        return part
            return "热门内容"  # 默认搜索词
        else:
            # 直接作为搜索关键词
            return creator_url or "热门内容"

# ==================== 全局服务实例 ====================

crawler_service = UnifiedCrawlerService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    try:
        await crawler_service.initialize()
        logger.info("应用启动完成")
    except Exception as e:
        logger.error(f"应用初始化失败: {e}")
        raise
    
    yield
    
    # 关闭时
    try:
        await crawler_service.cleanup()
        logger.info("应用关闭完成")
    except Exception as e:
        logger.error(f"应用关闭过程中出错: {e}")

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="NewsHub 统一爬虫服务", 
    version="2.0.0",
    description="整合了通用爬虫和平台特定爬虫的统一服务",
    lifespan=lifespan
)

# ==================== API 端点 ====================

@app.get("/")
async def root():
    """健康检查端点"""
    return {
        "message": "NewsHub 统一爬虫服务正在运行", 
        "status": "healthy", 
        "version": "2.0.0",
        "features": ["通用爬虫", "平台爬虫", "批量处理"]
    }

@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "service": "unified-crawler",
        "crawler_initialized": crawler_service.session is not None,
        "timestamp": datetime.now(),
        "supported_platforms": ["weibo", "douyin", "xiaohongshu", "bilibili", "news"],
        "features": ["requests", "beautifulsoup", "html2text", "platform-specific"]
    }

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest):
    """爬取指定URL的内容"""
    try:
        if not crawler_service.session:
            raise HTTPException(status_code=503, detail="爬虫服务未初始化")
        
        result = await crawler_service.crawl_url(request)
        return result
    
    except Exception as e:
        logger.error(f"爬取URL出错 {request.url}: {e}")
        return CrawlResponse(
            url=request.url,
            title="",
            content="",
            markdown="",
            crawled_at=datetime.now(),
            success=False,
            error_message=str(e)
        )

@app.post("/crawl/batch")
async def crawl_batch(urls: List[str]):
    """批量爬取多个URL"""
    results = []
    for url in urls:
        request = CrawlRequest(url=url)
        result = await crawl_url(request)
        results.append(result)
    return {"results": results, "total": len(results)}

@app.post("/crawl/platform")
async def crawl_platform(request: PlatformCrawlRequest):
    """爬取指定平台的内容"""
    try:
        if not crawler_service.crawler:
            raise HTTPException(status_code=503, detail="crawl4ai服务未初始化")
        
        logger.info(f"开始使用crawl4ai爬取平台 {request.platform} 的内容，关键词/URL: {request.creator_url}")
        
        posts = await crawler_service.crawl_platform_direct(
            creator_url=request.creator_url,
            platform=request.platform,
            limit=request.limit
        )
        
        logger.info(f"完成crawl4ai爬取，共获取 {len(posts)} 条内容")
        
        # 处理媒体文件上传
        storage_client = get_storage_client()
        processed_posts = []
        
        for post in posts:
            try:
                # 上传媒体文件到MinIO
                if post.images or post.video_url:
                    logger.info(f"开始处理帖子媒体文件: {post.title[:50]}...")
                    
                    upload_result = storage_client.upload_media_files(
                        images=post.images,
                        video_url=post.video_url
                    )
                    
                    # 更新帖子的媒体URL
                    post.images = upload_result['images']
                    post.video_url = upload_result['video_url']
                    
                    if upload_result['errors']:
                        logger.warning(f"媒体文件上传部分失败: {upload_result['errors']}")
                    
                    logger.info(f"媒体文件处理完成: 图片 {len(post.images)} 张, 视频 {'有' if post.video_url else '无'}")
                
                processed_posts.append(post)
                
            except Exception as e:
                logger.error(f"处理帖子媒体文件失败 {post.title[:50]}: {e}")
                # 即使媒体文件处理失败，也保留原始帖子
                processed_posts.append(post)
        
        return {
            "platform": request.platform,
            "creator_url": request.creator_url,
            "posts": processed_posts,
            "total": len(processed_posts),
            "crawled_at": datetime.now(),
            "success": True,
            "method": "crawl4ai_direct_with_media_storage"
        }
    
    except Exception as e:
        logger.error(f"crawl4ai爬取平台内容出错 {request.platform}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_content(request: SearchRequest):
    """搜索指定平台的内容"""
    try:
        if not crawler_service.session:
            raise HTTPException(status_code=503, detail="爬虫服务未初始化")
        
        # 转换为平台爬取请求
        platform_request = PlatformCrawlRequest(
            creator_url=request.query,
            platform=request.platform,
            limit=request.limit
        )
        
        posts = await crawler_service.crawl_platform_posts(platform_request)
        
        return {
            "query": request.query,
            "platform": request.platform,
            "posts": posts,
            "total": len(posts),
            "searched_at": datetime.now(),
            "success": True
        }
    
    except Exception as e:
        logger.error(f"搜索内容出错 {request.platform}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/platforms")
async def get_supported_platforms():
    """获取支持的平台列表"""
    return {
        "platforms": [
            {
                "name": "微博",
                "key": "weibo",
                "domain": "weibo.com",
                "supported": True,
                "content_type": "社交媒体帖子"
            },
            {
                "name": "抖音",
                "key": "douyin",
                "domain": "douyin.com",
                "supported": True,
                "content_type": "短视频"
            },
            {
                "name": "小红书",
                "key": "xiaohongshu",
                "domain": "xiaohongshu.com",
                "supported": True,
                "content_type": "生活笔记"
            },
            {
                "name": "哔哩哔哩",
                "key": "bilibili",
                "domain": "bilibili.com",
                "supported": True,
                "content_type": "视频内容"
            },
            {
                "name": "新闻网站",
                "key": "news",
                "domain": "*.news.*",
                "supported": True,
                "content_type": "新闻文章"
            },
            {
                "name": "通用网站",
                "key": "general",
                "domain": "*",
                "supported": True,
                "content_type": "网页内容"
            }
        ],
        "note": "统一爬虫服务，支持通用网页爬取和平台特定内容提取"
    }

@app.get("/status")
async def get_service_status():
    """获取服务状态"""
    return {
        "service": "unified-crawler",
        "version": "2.0.0",
        "status": "running",
        "initialized": crawler_service.session is not None,
        "uptime": datetime.now(),
        "endpoints": [
            "/crawl - 通用URL爬取",
            "/crawl/batch - 批量URL爬取",
            "/crawl/platform - 平台特定爬取",
            "/platforms - 支持的平台列表",
            "/health - 健康检查"
        ]
    }

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    # 从配置文件获取服务器设置
    server_config = app_config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8001)
    reload = server_config.get("reload", False)
    
    logger.info(f"爬虫服务启动配置: host={host}, port={port}, reload={reload}")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        reload=reload
    )