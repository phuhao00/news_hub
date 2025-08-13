#!/usr/bin/env python3
"""
MCP服务器测试脚本
测试浏览器MCP和本地MCP服务器的基本功能
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from local_mcp_server import LocalMCPServer
import browser_mcp_server


async def test_browser_mcp():
    """测试浏览器MCP服务器"""
    print("\n=== 测试浏览器MCP服务器 ===")
    
    try:
        # 测试浏览器初始化
        print("测试浏览器初始化...")
        await browser_mcp_server.initialize_browser()
        print("✓ 浏览器MCP服务器初始化成功")
        
        # 清理资源
        await browser_mcp_server.cleanup_browser()
        print("✓ 浏览器资源清理完成")
        
    except Exception as e:
        print(f"✗ 浏览器MCP服务器测试失败: {e}")


async def test_local_mcp():
    """测试本地MCP服务器"""
    print("\n=== 测试本地MCP服务器 ===")
    
    try:
        server = LocalMCPServer()
        print("✓ 本地MCP服务器初始化成功")
        
        # 测试文件操作（模拟）
        test_file = Path("test_mcp_file.txt")
        test_content = f"MCP测试文件\n创建时间: {datetime.now().isoformat()}"
        
        # 创建测试文件
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        print("✓ 测试文件创建成功")
        
        # 验证文件存在
        if test_file.exists():
            print("✓ 文件存在验证成功")
            
            # 读取文件内容
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if content == test_content:
                print("✓ 文件内容验证成功")
            else:
                print("✗ 文件内容验证失败")
        else:
            print("✗ 文件不存在")
        
        # 清理测试文件
        if test_file.exists():
            test_file.unlink()
            print("✓ 测试文件清理完成")
            
    except Exception as e:
        print(f"✗ 本地MCP服务器测试失败: {e}")


async def test_mcp_integration():
    """测试MCP集成功能"""
    print("\n=== 测试MCP集成功能 ===")
    
    try:
        # 检查MCP配置
        from main import load_mcp_config
        
        mcp_config = load_mcp_config()
        if mcp_config:
            print("✓ MCP配置加载成功")
            mcp_services = mcp_config.get('mcp_services', {})
            browser_mcp = mcp_config.get('browser_mcp', {})
            local_mcp = mcp_config.get('local_mcp', {})
            print(f"  - MCP启用状态: {mcp_services.get('enabled', False)}")
            print(f"  - 浏览器MCP端点: {browser_mcp.get('mcp_endpoint', 'N/A')}")
            print(f"  - 本地MCP端点: {local_mcp.get('mcp_endpoint', 'N/A')}")
        else:
            print("✗ MCP配置加载失败")
        
        # 检查MCP服务状态
        from main import UnifiedCrawlerService
        
        crawler = UnifiedCrawlerService()
        
        # 确保服务已初始化
        await crawler.ensure_initialized()
        
        if crawler.mcp_enabled and hasattr(crawler, 'mcp_processor') and crawler.mcp_processor:
            print("✓ MCP处理器初始化成功")
            
            # 获取MCP服务状态
            status = await crawler.get_mcp_service_status()
            print(f"✓ MCP服务状态获取成功:")
            print(f"  - 系统启用: {status.enabled}")
            print(f"  - 浏览器MCP: {status.browser_mcp.available}")
            print(f"  - 本地MCP: {status.local_mcp.available}")
            print(f"  - crawl4ai集成: {status.crawl4ai_integration}")
        else:
            print(f"✗ MCP处理器未初始化 (MCP启用: {crawler.mcp_enabled})")
            
        # 清理资源
        await crawler.cleanup()
            
    except Exception as e:
        print(f"✗ MCP集成测试失败: {e}")


async def main():
    """主测试函数"""
    print("开始MCP服务器功能测试")
    print("=" * 50)
    
    # 测试浏览器MCP
    await test_browser_mcp()
    
    # 测试本地MCP
    await test_local_mcp()
    
    # 测试MCP集成
    await test_mcp_integration()
    
    print("\n=" * 50)
    print("MCP服务器功能测试完成")


if __name__ == "__main__":
    asyncio.run(main())
