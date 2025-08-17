"""
浏览器配置工具模块
提供统一的 Playwright 浏览器配置，避免安全警告和自动化检测
"""

from crawl4ai import BrowserConfig
from typing import List, Optional


def get_secure_browser_config(
    headless: bool = True,
    browser_type: str = "chromium",
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    user_agent: Optional[str] = None,
    verbose: bool = False
) -> BrowserConfig:
    """
    获取安全的浏览器配置，避免安全警告和自动化检测
    
    Args:
        headless: 是否使用无头模式
        browser_type: 浏览器类型 (chromium, firefox, webkit)
        viewport_width: 视口宽度
        viewport_height: 视口高度
        user_agent: 自定义 User-Agent
        verbose: 是否启用详细日志
    
    Returns:
        BrowserConfig: 配置好的浏览器配置对象
    """
    
    # 默认 User-Agent
    if not user_agent:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # 安全参数列表，用于避免安全警告和自动化检测
    security_args = [
        # 基础安全设置
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-web-security",
        "--ignore-certificate-errors",
        "--allow-running-insecure-content",
        
        # 自动化检测防护
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins",
        
        # 性能优化
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-ipc-flooding-protection",
        "--disable-hang-monitor",
        
        # 用户体验优化
        "--no-first-run",
        "--disable-default-apps",
        "--disable-infobars",
        "--disable-prompt-on-repost",
        "--disable-domain-reliability",
        "--disable-component-extensions-with-background-pages",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--mute-audio",
        "--no-default-browser-check",
        "--no-experiments",
        "--no-pings",
        "--no-zygote",
        
        # 日志和调试
        "--disable-logging",
        "--disable-breakpad",
        "--metrics-recording-only",
        "--no-report-upload",
        
        # 安全功能
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-features=VizDisplayCompositor",
        "--disable-print-preview",
        "--disable-save-password-bubble",
        "--disable-single-click-autofill",
        "--disable-spellcheck-autocorrect",
        "--disable-voice-input",
        "--disable-web-resources",
        
        # 其他设置
        "--force-color-profile=srgb",
        "--password-store=basic",
        "--use-mock-keychain",
        "--disable-features=site-per-process",
        "--disable-site-isolation-trials"
    ]
    
    return BrowserConfig(
        browser_type=browser_type,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        user_agent=user_agent,
        ignore_https_errors=True,
        java_script_enabled=True,
        verbose=verbose,
        extra_args=security_args
    )


def get_minimal_browser_config(
    headless: bool = True,
    browser_type: str = "chromium"
) -> BrowserConfig:
    """
    获取最小化的浏览器配置，用于简单的HTML处理
    
    Args:
        headless: 是否使用无头模式
        browser_type: 浏览器类型
    
    Returns:
        BrowserConfig: 最小化的浏览器配置对象
    """
    
    minimal_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-web-security",
        "--ignore-certificate-errors",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins",
        "--no-first-run",
        "--disable-default-apps",
        "--disable-infobars",
        "--disable-logging",
        "--disable-breakpad",
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--mute-audio",
        "--no-default-browser-check",
        "--no-experiments",
        "--no-pings",
        "--no-zygote",
        "--metrics-recording-only",
        "--no-report-upload",
        "--password-store=basic",
        "--use-mock-keychain"
    ]
    
    return BrowserConfig(
        browser_type=browser_type,
        headless=headless,
        ignore_https_errors=True,
        verbose=False,
        extra_args=minimal_args
    )


def get_stealth_browser_config(
    headless: bool = True,
    browser_type: str = "chromium",
    viewport_width: int = 1920,
    viewport_height: int = 1080
) -> BrowserConfig:
    """
    获取隐身模式的浏览器配置，最大程度避免检测
    
    Args:
        headless: 是否使用无头模式
        browser_type: 浏览器类型
        viewport_width: 视口宽度
        viewport_height: 视口高度
    
    Returns:
        BrowserConfig: 隐身模式的浏览器配置对象
    """
    
    # 随机化 User-Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    import random
    user_agent = random.choice(user_agents)
    
    stealth_args = [
        # 基础安全设置
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-web-security",
        "--ignore-certificate-errors",
        "--allow-running-insecure-content",
        
        # 高级隐身设置
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-images",  # 不加载图片以提高速度
        "--disable-javascript-harmony-shipping",
        
        # 性能优化
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-ipc-flooding-protection",
        "--disable-hang-monitor",
        
        # 用户体验
        "--no-first-run",
        "--disable-default-apps",
        "--disable-infobars",
        "--disable-prompt-on-repost",
        "--disable-domain-reliability",
        "--disable-component-extensions-with-background-pages",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--mute-audio",
        "--no-default-browser-check",
        "--no-experiments",
        "--no-pings",
        "--no-zygote",
        
        # 日志和调试
        "--disable-logging",
        "--disable-breakpad",
        "--metrics-recording-only",
        "--no-report-upload",
        
        # 安全功能
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-features=VizDisplayCompositor",
        "--disable-print-preview",
        "--disable-save-password-bubble",
        "--disable-single-click-autofill",
        "--disable-spellcheck-autocorrect",
        "--disable-voice-input",
        "--disable-web-resources",
        
        # 其他设置
        "--force-color-profile=srgb",
        "--password-store=basic",
        "--use-mock-keychain",
        "--disable-features=site-per-process",
        "--disable-site-isolation-trials",
        
        # 额外的隐身设置
        "--disable-features=TranslateUI",
        "--disable-features=VizDisplayCompositor",
        "--disable-features=site-per-process",
        "--disable-features=TranslateUI",
        "--disable-features=VizDisplayCompositor",
        "--disable-features=site-per-process"
    ]
    
    return BrowserConfig(
        browser_type=browser_type,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        user_agent=user_agent,
        ignore_https_errors=True,
        java_script_enabled=True,
        verbose=False,
        extra_args=stealth_args
    )

