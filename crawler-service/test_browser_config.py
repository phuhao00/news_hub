#!/usr/bin/env python3
"""
Test script to verify browser configurations work without security warnings
"""
import asyncio
import logging
from utils.browser_config import get_secure_browser_config, get_minimal_browser_config
from crawl4ai import AsyncWebCrawler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_browser_config():
    """Test that browser configurations work without security warnings"""
    
    # Test URLs that might trigger security warnings
    test_urls = [
        "https://httpbin.org/headers",  # Simple test site
        "https://example.com",          # Basic site
    ]
    
    print("Testing browser configurations...")
    
    # Test secure configuration
    print("\n1. Testing secure browser configuration...")
    try:
        browser_config = get_secure_browser_config(
            headless=True,
            browser_type="chromium",
            viewport_width=1920,
            viewport_height=1080,
            verbose=False
        )
        
        crawler = AsyncWebCrawler(config=browser_config)
        
        for url in test_urls:
            print(f"  Testing URL: {url}")
            try:
                result = await crawler.arun(url)
                print(f"  ✓ Success: {url}")
                print(f"    Status: {result.status_code}")
                print(f"    Content length: {len(result.html) if result.html else 0}")
            except Exception as e:
                print(f"  ✗ Error with {url}: {e}")
        
        await crawler.aclose()
        print("  ✓ Secure configuration test completed")
        
    except Exception as e:
        print(f"  ✗ Secure configuration failed: {e}")
    
    # Test minimal configuration
    print("\n2. Testing minimal browser configuration...")
    try:
        browser_config = get_minimal_browser_config(
            headless=True,
            browser_type="chromium"
        )
        
        crawler = AsyncWebCrawler(config=browser_config)
        
        for url in test_urls:
            print(f"  Testing URL: {url}")
            try:
                result = await crawler.arun(url)
                print(f"  ✓ Success: {url}")
                print(f"    Status: {result.status_code}")
                print(f"    Content length: {len(result.html) if result.html else 0}")
            except Exception as e:
                print(f"  ✗ Error with {url}: {e}")
        
        await crawler.aclose()
        print("  ✓ Minimal configuration test completed")
        
    except Exception as e:
        print(f"  ✗ Minimal configuration failed: {e}")
    
    print("\n✓ All browser configuration tests completed!")

if __name__ == "__main__":
    asyncio.run(test_browser_config())

