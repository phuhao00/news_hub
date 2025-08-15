#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强数据提取层 - 集成截图内容提取、DOM解析、内容清洗和格式标准化
实现智能爬取系统的核心数据提取功能
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page
import base64
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    """提取方法枚举"""
    DOM_ONLY = "dom_only"
    SCREENSHOT_ONLY = "screenshot_only"
    COMBINED = "combined"
    CRAWL4AI_FALLBACK = "crawl4ai_fallback"

class ContentQuality(Enum):
    """内容质量等级"""
    HIGH = "high"        # 高质量：完整内容，结构清晰
    MEDIUM = "medium"    # 中等质量：部分内容，结构一般
    LOW = "low"          # 低质量：内容不完整或结构混乱
    FAILED = "failed"    # 提取失败

@dataclass
class ExtractionResult:
    """提取结果数据结构"""
    title: str = ""
    content: str = ""
    author: str = ""
    publish_time: str = ""
    tags: List[str] = None
    images: List[str] = None
    links: List[str] = None
    summary: str = ""
    quality: ContentQuality = ContentQuality.FAILED
    confidence: float = 0.0
    extraction_method: ExtractionMethod = ExtractionMethod.DOM_ONLY
    processing_time: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.images is None:
            self.images = []
        if self.links is None:
            self.links = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ScreenshotAnalysis:
    """截图分析结果"""
    has_content: bool = False
    content_density: float = 0.0
    text_regions: List[Dict] = None
    image_regions: List[Dict] = None
    layout_score: float = 0.0
    confidence: float = 0.0
    analysis_time: float = 0.0
    
    def __post_init__(self):
        if self.text_regions is None:
            self.text_regions = []
        if self.image_regions is None:
            self.image_regions = []

class EnhancedExtractor:
    """增强数据提取器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.platform_configs = self._load_platform_configs()
        self.quality_thresholds = {
            'min_content_length': 100,
            'min_title_length': 5,
            'max_title_length': 200,
            'min_confidence': 0.6,
            'high_quality_threshold': 0.8,
            'medium_quality_threshold': 0.6
        }
        
    def _load_platform_configs(self) -> Dict[str, Dict]:
        """加载平台特定配置"""
        return {
            'weibo': {
                'content_selectors': [
                    '.WB_text', '.WB_detail .WB_text', '.card-wrap .txt',
                    '[node-type="feed_list_content"]', '.weibo-text'
                ],
                'title_selectors': ['.WB_text', '.weibo-text'],
                'author_selectors': ['.WB_info a[usercard]', '.name', '.u-name'],
                'time_selectors': ['.WB_from', '.time', '.ct'],
                'exclude_selectors': ['.WB_expand', '.WB_media_a', 'script', 'style']
            },
            'xiaohongshu': {
                'content_selectors': [
                    '.note-content', '.content', '.desc',
                    '[class*="content"]', '[class*="desc"]'
                ],
                'title_selectors': ['.title', '.note-title', 'h1'],
                'author_selectors': ['.author', '.username', '.user-name'],
                'time_selectors': ['.time', '.date', '.publish-time'],
                'exclude_selectors': ['script', 'style', '.ad', '.recommend']
            },
            'douyin': {
                'content_selectors': [
                    '.video-info-detail', '.desc', '.content',
                    '[data-e2e="video-desc"]'
                ],
                'title_selectors': ['.desc', '.content', '[data-e2e="video-desc"]'],
                'author_selectors': ['.author', '.username', '[data-e2e="video-author"]'],
                'time_selectors': ['.time', '.date'],
                'exclude_selectors': ['script', 'style', '.recommend']
            },
            'bilibili': {
                'content_selectors': [
                    '.video-desc', '.desc-info', '.intro',
                    '.video-info .desc'
                ],
                'title_selectors': ['.video-title', 'h1', '.title'],
                'author_selectors': ['.up-name', '.username', '.author'],
                'time_selectors': ['.pubdate', '.time', '.date'],
                'exclude_selectors': ['script', 'style', '.ad']
            },
            'zhihu': {
                'content_selectors': [
                    '.RichContent-inner', '.Post-RichTextContainer',
                    '.AnswerItem .RichContent', '.QuestionAnswer-content'
                ],
                'title_selectors': ['.QuestionHeader-title', 'h1', '.Post-Title'],
                'author_selectors': ['.AuthorInfo-name', '.UserLink-link'],
                'time_selectors': ['.ContentItem-time', '.PublishDate'],
                'exclude_selectors': ['script', 'style', '.Recommendations']
            }
        }
    
    async def extract_content(self, page: Page, url: str, platform: str = None) -> ExtractionResult:
        """主要内容提取入口"""
        start_time = time.time()
        
        try:
            logger.info(f"开始提取内容: {url}")
            
            # 1. 获取页面HTML
            html_content = await page.content()
            
            # 2. 截图分析
            screenshot_analysis = await self._analyze_screenshot(page, url)
            
            # 3. DOM解析
            dom_result = await self._extract_from_dom(html_content, url, platform)
            
            # 4. 结合分析结果
            combined_result = self._combine_extraction_results(
                dom_result, screenshot_analysis, url, platform
            )
            
            # 5. 内容清洗和标准化
            cleaned_result = self._clean_and_standardize(combined_result)
            
            # 6. 质量评估
            final_result = self._assess_quality(cleaned_result)
            
            processing_time = time.time() - start_time
            final_result.processing_time = processing_time
            
            logger.info(f"内容提取完成: {url}, 质量: {final_result.quality.value}, "
                       f"置信度: {final_result.confidence:.2f}, 耗时: {processing_time:.2f}s")
            
            return final_result
            
        except Exception as e:
            logger.error(f"内容提取失败: {url}, 错误: {str(e)}")
            processing_time = time.time() - start_time
            return ExtractionResult(
                quality=ContentQuality.FAILED,
                confidence=0.0,
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    async def _analyze_screenshot(self, page: Page, url: str) -> ScreenshotAnalysis:
        """截图分析"""
        start_time = time.time()
        
        try:
            # 捕获截图
            screenshot_bytes = await page.screenshot(
                full_page=True,
                type='png',
                quality=90
            )
            
            # 基础截图分析（未来可集成ML模型）
            analysis = ScreenshotAnalysis(
                has_content=len(screenshot_bytes) > 10000,  # 基于文件大小判断
                content_density=self._estimate_content_density(screenshot_bytes),
                layout_score=0.7,  # 默认布局分数
                confidence=0.6,
                analysis_time=time.time() - start_time
            )
            
            # 添加截图元数据
            analysis.text_regions = [{
                'region': 'full_page',
                'confidence': 0.6,
                'estimated_text_length': len(screenshot_bytes) // 1000
            }]
            
            return analysis
            
        except Exception as e:
            logger.error(f"截图分析失败: {url}, 错误: {str(e)}")
            return ScreenshotAnalysis(
                confidence=0.0,
                analysis_time=time.time() - start_time
            )
    
    def _estimate_content_density(self, screenshot_bytes: bytes) -> float:
        """估算内容密度"""
        try:
            # 基于截图大小估算内容密度
            size_kb = len(screenshot_bytes) / 1024
            
            if size_kb > 500:  # 大于500KB认为内容丰富
                return 0.8
            elif size_kb > 200:  # 200-500KB认为内容中等
                return 0.6
            elif size_kb > 50:   # 50-200KB认为内容较少
                return 0.4
            else:  # 小于50KB认为内容很少
                return 0.2
                
        except Exception:
            return 0.3  # 默认值
    
    async def _extract_from_dom(self, html_content: str, url: str, platform: str = None) -> ExtractionResult:
        """DOM解析提取"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 移除不需要的元素
            self._remove_unwanted_elements(soup)
            
            # 获取平台配置
            platform_config = self.platform_configs.get(platform, {})
            
            # 提取各个字段
            title = self._extract_title(soup, platform_config)
            content = self._extract_content(soup, platform_config)
            author = self._extract_author(soup, platform_config)
            publish_time = self._extract_publish_time(soup, platform_config)
            tags = self._extract_tags(soup)
            images = self._extract_images(soup, url)
            links = self._extract_links(soup, url)
            
            # 生成摘要
            summary = self._generate_summary(content)
            
            return ExtractionResult(
                title=title,
                content=content,
                author=author,
                publish_time=publish_time,
                tags=tags,
                images=images,
                links=links,
                summary=summary,
                extraction_method=ExtractionMethod.DOM_ONLY,
                metadata={
                    'platform': platform,
                    'html_length': len(html_content),
                    'soup_elements': len(soup.find_all())
                }
            )
            
        except Exception as e:
            logger.error(f"DOM解析失败: {url}, 错误: {str(e)}")
            return ExtractionResult(
                extraction_method=ExtractionMethod.DOM_ONLY,
                metadata={'error': str(e)}
            )
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup):
        """移除不需要的元素"""
        unwanted_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']
        unwanted_classes = ['ad', 'advertisement', 'sidebar', 'recommend', 'related']
        
        # 移除标签
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 移除包含特定class的元素
        for class_name in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
    
    def _extract_title(self, soup: BeautifulSoup, platform_config: Dict) -> str:
        """提取标题"""
        selectors = platform_config.get('title_selectors', ['title', 'h1', 'h2'])
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                title = elements[0].get_text(strip=True)
                if len(title) > 5:  # 标题长度检查
                    return title[:200]  # 限制标题长度
        
        # 回退到页面title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)[:200]
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup, platform_config: Dict) -> str:
        """提取内容"""
        selectors = platform_config.get('content_selectors', [
            'article', '.content', '.post-content', 'main', '.main-content'
        ])
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                content_parts = []
                for element in elements:
                    text = element.get_text(separator='\n', strip=True)
                    if len(text) > 50:  # 内容长度检查
                        content_parts.append(text)
                
                if content_parts:
                    return '\n\n'.join(content_parts)
        
        # 回退到body内容
        body = soup.find('body')
        if body:
            return body.get_text(separator='\n', strip=True)
        
        return ""
    
    def _extract_author(self, soup: BeautifulSoup, platform_config: Dict) -> str:
        """提取作者"""
        selectors = platform_config.get('author_selectors', [
            '.author', '.username', '.user-name', '[rel="author"]'
        ])
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                author = elements[0].get_text(strip=True)
                if len(author) > 0 and len(author) < 100:
                    return author
        
        return ""
    
    def _extract_publish_time(self, soup: BeautifulSoup, platform_config: Dict) -> str:
        """提取发布时间"""
        selectors = platform_config.get('time_selectors', [
            'time', '.time', '.date', '.publish-time', '[datetime]'
        ])
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                element = elements[0]
                
                # 尝试从datetime属性获取
                datetime_attr = element.get('datetime')
                if datetime_attr:
                    return datetime_attr
                
                # 从文本内容获取
                time_text = element.get_text(strip=True)
                if time_text and len(time_text) < 50:
                    return time_text
        
        return ""
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """提取标签"""
        tags = []
        
        # 常见标签选择器
        tag_selectors = [
            '.tag', '.tags', '.hashtag', '.category',
            '[class*="tag"]', '[class*="label"]'
        ]
        
        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                tag_text = element.get_text(strip=True)
                if tag_text and len(tag_text) < 50:
                    tags.append(tag_text)
        
        # 从内容中提取话题标签
        content_text = soup.get_text()
        hashtag_pattern = r'#([^#\s]+)#?'
        hashtags = re.findall(hashtag_pattern, content_text)
        tags.extend(hashtags[:10])  # 限制数量
        
        return list(set(tags))[:20]  # 去重并限制数量
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取图片"""
        images = []
        
        img_elements = soup.find_all('img')
        for img in img_elements:
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            if src:
                # 转换为绝对URL
                absolute_url = urljoin(base_url, src)
                if self._is_valid_image_url(absolute_url):
                    images.append(absolute_url)
        
        return images[:50]  # 限制图片数量
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取链接"""
        links = []
        
        link_elements = soup.find_all('a', href=True)
        for link in link_elements:
            href = link.get('href')
            if href and not href.startswith('#'):
                absolute_url = urljoin(base_url, href)
                if self._is_valid_link_url(absolute_url):
                    links.append(absolute_url)
        
        return list(set(links))[:30]  # 去重并限制数量
    
    def _is_valid_image_url(self, url: str) -> bool:
        """验证图片URL"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 检查文件扩展名
            path = parsed.path.lower()
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
            return any(path.endswith(ext) for ext in image_extensions) or 'image' in url.lower()
        except:
            return False
    
    def _is_valid_link_url(self, url: str) -> bool:
        """验证链接URL"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False
    
    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """生成内容摘要"""
        if not content:
            return ""
        
        # 简单的摘要生成：取前几句话
        sentences = re.split(r'[。！？.!?]', content)
        summary_parts = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if current_length + len(sentence) > max_length:
                break
            
            summary_parts.append(sentence)
            current_length += len(sentence)
        
        summary = '。'.join(summary_parts)
        if summary and not summary.endswith(('。', '！', '？', '.', '!', '?')):
            summary += '...'
        
        return summary
    
    def _combine_extraction_results(
        self, 
        dom_result: ExtractionResult, 
        screenshot_analysis: ScreenshotAnalysis,
        url: str,
        platform: str
    ) -> ExtractionResult:
        """结合DOM和截图分析结果"""
        try:
            # 计算综合置信度
            dom_confidence = self._calculate_dom_confidence(dom_result)
            screenshot_confidence = screenshot_analysis.confidence
            
            combined_confidence = (
                dom_confidence * 0.7 +  # DOM分析权重70%
                screenshot_confidence * 0.3  # 截图分析权重30%
            )
            
            # 更新结果
            dom_result.confidence = combined_confidence
            dom_result.extraction_method = ExtractionMethod.COMBINED
            
            # 添加截图分析元数据
            dom_result.metadata.update({
                'screenshot_analysis': {
                    'has_content': screenshot_analysis.has_content,
                    'content_density': screenshot_analysis.content_density,
                    'layout_score': screenshot_analysis.layout_score,
                    'analysis_time': screenshot_analysis.analysis_time
                },
                'combined_confidence': combined_confidence,
                'dom_confidence': dom_confidence,
                'screenshot_confidence': screenshot_confidence
            })
            
            return dom_result
            
        except Exception as e:
            logger.error(f"结合分析结果失败: {url}, 错误: {str(e)}")
            dom_result.metadata['combination_error'] = str(e)
            return dom_result
    
    def _calculate_dom_confidence(self, result: ExtractionResult) -> float:
        """计算DOM提取置信度"""
        confidence = 0.0
        
        # 标题质量评分
        if result.title:
            title_len = len(result.title)
            if 10 <= title_len <= 100:
                confidence += 0.3
            elif 5 <= title_len <= 200:
                confidence += 0.2
        
        # 内容质量评分
        if result.content:
            content_len = len(result.content)
            if content_len >= 500:
                confidence += 0.4
            elif content_len >= 100:
                confidence += 0.3
            elif content_len >= 50:
                confidence += 0.2
        
        # 作者信息评分
        if result.author:
            confidence += 0.1
        
        # 时间信息评分
        if result.publish_time:
            confidence += 0.1
        
        # 标签和链接评分
        if result.tags:
            confidence += 0.05
        if result.images:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _clean_and_standardize(self, result: ExtractionResult) -> ExtractionResult:
        """内容清洗和标准化"""
        try:
            # 清洗标题
            if result.title:
                result.title = self._clean_text(result.title)
                result.title = result.title[:200]  # 限制长度
            
            # 清洗内容
            if result.content:
                result.content = self._clean_text(result.content)
                result.content = self._normalize_whitespace(result.content)
            
            # 清洗作者
            if result.author:
                result.author = self._clean_text(result.author)
                result.author = result.author[:100]  # 限制长度
            
            # 标准化时间格式
            if result.publish_time:
                result.publish_time = self._standardize_time(result.publish_time)
            
            # 清洗标签
            if result.tags:
                result.tags = [self._clean_text(tag)[:50] for tag in result.tags if tag.strip()]
                result.tags = list(set(result.tags))[:20]  # 去重并限制数量
            
            # 验证URL
            if result.images:
                result.images = [url for url in result.images if self._is_valid_image_url(url)]
            if result.links:
                result.links = [url for url in result.links if self._is_valid_link_url(url)]
            
            return result
            
        except Exception as e:
            logger.error(f"内容清洗失败: {str(e)}")
            result.metadata['cleaning_error'] = str(e)
            return result
    
    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        if not text:
            return ""
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 移除HTML实体
        import html
        text = html.unescape(text)
        
        return text.strip()
    
    def _normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        if not text:
            return ""
        
        # 标准化换行符
        text = re.sub(r'\r\n|\r', '\n', text)
        
        # 移除多余的空行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        return text
    
    def _standardize_time(self, time_str: str) -> str:
        """标准化时间格式"""
        if not time_str:
            return ""
        
        try:
            # 尝试解析常见时间格式
            import dateutil.parser
            parsed_time = dateutil.parser.parse(time_str)
            return parsed_time.isoformat()
        except:
            # 如果解析失败，返回原始字符串
            return time_str.strip()
    
    def _assess_quality(self, result: ExtractionResult) -> ExtractionResult:
        """评估内容质量"""
        try:
            quality_score = 0.0
            
            # 标题质量评分
            if result.title:
                title_len = len(result.title)
                if self.quality_thresholds['min_title_length'] <= title_len <= self.quality_thresholds['max_title_length']:
                    quality_score += 0.3
                elif result.title:
                    quality_score += 0.1
            
            # 内容质量评分
            if result.content:
                content_len = len(result.content)
                if content_len >= self.quality_thresholds['min_content_length'] * 5:
                    quality_score += 0.4
                elif content_len >= self.quality_thresholds['min_content_length']:
                    quality_score += 0.3
                elif content_len >= 50:
                    quality_score += 0.2
            
            # 结构化信息评分
            if result.author:
                quality_score += 0.1
            if result.publish_time:
                quality_score += 0.1
            if result.tags:
                quality_score += 0.05
            if result.images:
                quality_score += 0.05
            
            # 结合置信度
            final_score = (quality_score + result.confidence) / 2
            
            # 确定质量等级
            if final_score >= self.quality_thresholds['high_quality_threshold']:
                result.quality = ContentQuality.HIGH
            elif final_score >= self.quality_thresholds['medium_quality_threshold']:
                result.quality = ContentQuality.MEDIUM
            elif final_score >= self.quality_thresholds['min_confidence']:
                result.quality = ContentQuality.LOW
            else:
                result.quality = ContentQuality.FAILED
            
            # 更新最终置信度
            result.confidence = final_score
            
            # 添加质量评估元数据
            result.metadata.update({
                'quality_assessment': {
                    'quality_score': quality_score,
                    'final_score': final_score,
                    'title_length': len(result.title) if result.title else 0,
                    'content_length': len(result.content) if result.content else 0,
                    'has_author': bool(result.author),
                    'has_time': bool(result.publish_time),
                    'tag_count': len(result.tags) if result.tags else 0,
                    'image_count': len(result.images) if result.images else 0
                }
            })
            
            return result
            
        except Exception as e:
            logger.error(f"质量评估失败: {str(e)}")
            result.quality = ContentQuality.FAILED
            result.confidence = 0.0
            result.metadata['quality_assessment_error'] = str(e)
            return result
    
    async def extract_with_fallback(self, page: Page, url: str, platform: str = None) -> ExtractionResult:
        """带降级处理的内容提取"""
        try:
            # 首先尝试标准提取
            result = await self.extract_content(page, url, platform)
            
            # 如果质量不佳，尝试Crawl4AI降级
            if result.quality == ContentQuality.FAILED or result.confidence < 0.4:
                logger.info(f"标准提取质量不佳，尝试Crawl4AI降级: {url}")
                fallback_result = await self._crawl4ai_fallback(url, platform)
                
                if fallback_result and fallback_result.quality != ContentQuality.FAILED:
                    fallback_result.extraction_method = ExtractionMethod.CRAWL4AI_FALLBACK
                    return fallback_result
            
            return result
            
        except Exception as e:
            logger.error(f"带降级处理的内容提取失败: {url}, 错误: {str(e)}")
            return ExtractionResult(
                quality=ContentQuality.FAILED,
                confidence=0.0,
                metadata={'error': str(e)}
            )
    
    async def _crawl4ai_fallback(self, url: str, platform: str = None) -> Optional[ExtractionResult]:
        """Crawl4AI降级处理"""
        try:
            # 调用Crawl4AI服务
            crawl4ai_url = "http://localhost:8001/crawl"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    crawl4ai_url,
                    json={"url": url, "platform": platform},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_crawl4ai_result(data, url, platform)
            
            return None
            
        except Exception as e:
            logger.error(f"Crawl4AI降级处理失败: {url}, 错误: {str(e)}")
            return None
    
    def _parse_crawl4ai_result(self, data: Dict, url: str, platform: str) -> ExtractionResult:
        """解析Crawl4AI结果"""
        try:
            result = ExtractionResult(
                title=data.get('title', ''),
                content=data.get('content', ''),
                author=data.get('author', ''),
                publish_time=data.get('publish_time', ''),
                tags=data.get('tags', []),
                images=data.get('images', []),
                links=data.get('links', []),
                summary=data.get('summary', ''),
                extraction_method=ExtractionMethod.CRAWL4AI_FALLBACK,
                metadata={
                    'platform': platform,
                    'crawl4ai_success': data.get('success', False),
                    'crawl4ai_method': data.get('method', 'unknown')
                }
            )
            
            # 清洗和评估质量
            result = self._clean_and_standardize(result)
            result = self._assess_quality(result)
            
            return result
            
        except Exception as e:
            logger.error(f"解析Crawl4AI结果失败: {url}, 错误: {str(e)}")
            return ExtractionResult(
                quality=ContentQuality.FAILED,
                extraction_method=ExtractionMethod.CRAWL4AI_FALLBACK,
                metadata={'parse_error': str(e)}
            )
    
    def to_dict(self, result: ExtractionResult) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(result)
    
    def from_dict(self, data: Dict[str, Any]) -> ExtractionResult:
        """从字典创建结果对象"""
        # 处理枚举类型
        if 'quality' in data and isinstance(data['quality'], str):
            data['quality'] = ContentQuality(data['quality'])
        if 'extraction_method' in data and isinstance(data['extraction_method'], str):
            data['extraction_method'] = ExtractionMethod(data['extraction_method'])
        
        return ExtractionResult(**data)