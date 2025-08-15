#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl4AI降级处理服务
当内容提取失败时自动切换到Crawl4AI进行重新爬取
实现智能降级、错误恢复和质量保证机制
"""

import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy, CosineStrategy
from crawl4ai.chunking_strategy import RegexChunking
from crawl4ai.content_filter_strategy import BM25ContentFilter

from extraction.enhanced_extractor import (
    ExtractionResult, ContentQuality, ExtractionMethod
)
from storage.persistence_manager import get_persistence_manager

logger = logging.getLogger(__name__)

class FallbackTrigger(Enum):
    """降级触发原因"""
    EXTRACTION_FAILED = "extraction_failed"          # 内容提取失败
    LOW_QUALITY = "low_quality"                      # 内容质量过低
    TIMEOUT = "timeout"                              # 提取超时
    NETWORK_ERROR = "network_error"                  # 网络错误
    PARSING_ERROR = "parsing_error"                  # 解析错误
    SCREENSHOT_FAILED = "screenshot_failed"          # 截图失败
    DOM_ANALYSIS_FAILED = "dom_analysis_failed"      # DOM分析失败
    MANUAL_TRIGGER = "manual_trigger"                # 手动触发

class FallbackStrategy(Enum):
    """降级策略"""
    BASIC_CRAWL4AI = "basic_crawl4ai"                # 基础Crawl4AI爬取
    LLM_EXTRACTION = "llm_extraction"                # LLM智能提取
    COSINE_SIMILARITY = "cosine_similarity"          # 余弦相似度提取
    MULTI_STRATEGY = "multi_strategy"                # 多策略组合
    CUSTOM_EXTRACTION = "custom_extraction"          # 自定义提取

@dataclass
class FallbackConfig:
    """降级配置"""
    enabled: bool = True
    max_retries: int = 3
    timeout: int = 60
    quality_threshold: float = 0.3
    strategies: List[FallbackStrategy] = None
    llm_config: Dict[str, Any] = None
    custom_selectors: Dict[str, List[str]] = None
    
    def __post_init__(self):
        if self.strategies is None:
            self.strategies = [
                FallbackStrategy.BASIC_CRAWL4AI,
                FallbackStrategy.LLM_EXTRACTION,
                FallbackStrategy.COSINE_SIMILARITY
            ]
        if self.llm_config is None:
            self.llm_config = {
                'provider': 'openai',
                'model': 'gpt-3.5-turbo',
                'api_token': None
            }
        if self.custom_selectors is None:
            self.custom_selectors = {}

@dataclass
class FallbackResult:
    """降级结果"""
    success: bool
    strategy_used: FallbackStrategy
    extraction_result: Optional[ExtractionResult]
    processing_time: float
    error_message: str = ""
    retry_count: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class Crawl4AIFallbackService:
    """Crawl4AI降级处理服务"""
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.crawler = None
        self.persistence_manager = None
        
        # 统计信息
        self.stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'strategy_usage': {strategy.value: 0 for strategy in FallbackStrategy},
            'trigger_reasons': {trigger.value: 0 for trigger in FallbackTrigger},
            'average_processing_time': 0.0,
            'last_fallback_time': None
        }
        
        # 平台特定配置
        self.platform_configs = {
            'weibo': {
                'selectors': {
                    'title': ['.WB_text', '.txt', '[node-type="feed_list_content"]'],
                    'content': ['.WB_text', '.txt', '[node-type="feed_list_content"]'],
                    'author': ['.WB_info a', '.name', '[usercard]'],
                    'time': ['.WB_from', '.time', '[date]']
                },
                'wait_for': '.WB_cardwrap',
                'scroll_pause_time': 2
            },
            'xiaohongshu': {
                'selectors': {
                    'title': ['.note-item .title', '.content .title'],
                    'content': ['.note-item .desc', '.content .desc'],
                    'author': ['.note-item .name', '.author .name'],
                    'time': ['.note-item .time', '.publish-time']
                },
                'wait_for': '.note-item',
                'scroll_pause_time': 3
            },
            'douyin': {
                'selectors': {
                    'title': ['.video-info .title', '.aweme-video-info .title'],
                    'content': ['.video-info .desc', '.aweme-video-info .desc'],
                    'author': ['.author-info .name', '.author .name'],
                    'time': ['.video-info .time', '.publish-time']
                },
                'wait_for': '.video-info',
                'scroll_pause_time': 2
            }
        }
    
    async def initialize(self) -> bool:
        """初始化降级服务"""
        try:
            logger.info("初始化Crawl4AI降级服务...")
            
            # 初始化Crawl4AI爬虫
            self.crawler = AsyncWebCrawler(
                headless=True,
                browser_type="chromium",
                verbose=False
            )
            await self.crawler.start()
            
            # 获取持久化管理器
            self.persistence_manager = await get_persistence_manager()
            
            logger.info("Crawl4AI降级服务初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化Crawl4AI降级服务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def trigger_fallback(
        self,
        task_id: str,
        url: str,
        platform: str,
        trigger_reason: FallbackTrigger,
        original_error: str = "",
        context: Dict[str, Any] = None
    ) -> FallbackResult:
        """触发降级处理"""
        start_time = time.time()
        
        try:
            logger.info(
                f"触发Crawl4AI降级处理: {task_id}, URL: {url}, "
                f"平台: {platform}, 原因: {trigger_reason.value}"
            )
            
            # 更新统计信息
            self.stats['total_fallbacks'] += 1
            self.stats['trigger_reasons'][trigger_reason.value] += 1
            self.stats['last_fallback_time'] = datetime.now(timezone.utc)
            
            # 记录降级触发日志
            await self._log_fallback_trigger(
                task_id, url, platform, trigger_reason, original_error, context
            )
            
            # 执行降级策略
            result = await self._execute_fallback_strategies(
                task_id, url, platform, trigger_reason, context or {}
            )
            
            # 计算处理时间
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            
            # 更新统计信息
            if result.success:
                self.stats['successful_fallbacks'] += 1
                self.stats['strategy_usage'][result.strategy_used.value] += 1
            else:
                self.stats['failed_fallbacks'] += 1
            
            # 更新平均处理时间
            total_time = self.stats['average_processing_time'] * (self.stats['total_fallbacks'] - 1)
            self.stats['average_processing_time'] = (total_time + processing_time) / self.stats['total_fallbacks']
            
            # 记录降级结果
            await self._log_fallback_result(task_id, result)
            
            logger.info(
                f"降级处理完成: {task_id}, 成功: {result.success}, "
                f"策略: {result.strategy_used.value}, 耗时: {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"降级处理异常: {str(e)}"
            logger.error(f"{error_message}, 任务: {task_id}")
            logger.error(traceback.format_exc())
            
            self.stats['failed_fallbacks'] += 1
            
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.BASIC_CRAWL4AI,
                extraction_result=None,
                processing_time=processing_time,
                error_message=error_message
            )
    
    async def _execute_fallback_strategies(
        self,
        task_id: str,
        url: str,
        platform: str,
        trigger_reason: FallbackTrigger,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """执行降级策略"""
        last_error = ""
        
        for strategy in self.config.strategies:
            try:
                logger.info(f"尝试降级策略: {strategy.value}, 任务: {task_id}")
                
                result = await self._execute_single_strategy(
                    strategy, task_id, url, platform, context
                )
                
                if result.success and self._is_quality_acceptable(result.extraction_result):
                    logger.info(f"降级策略成功: {strategy.value}, 任务: {task_id}")
                    result.strategy_used = strategy
                    return result
                else:
                    last_error = result.error_message or "质量不达标"
                    logger.warning(
                        f"降级策略失败: {strategy.value}, 任务: {task_id}, "
                        f"错误: {last_error}"
                    )
                    
            except Exception as e:
                last_error = f"策略执行异常: {str(e)}"
                logger.error(f"降级策略异常: {strategy.value}, 任务: {task_id}, 错误: {last_error}")
                continue
        
        # 所有策略都失败了
        return FallbackResult(
            success=False,
            strategy_used=self.config.strategies[0] if self.config.strategies else FallbackStrategy.BASIC_CRAWL4AI,
            extraction_result=None,
            processing_time=0.0,
            error_message=f"所有降级策略都失败: {last_error}"
        )
    
    async def _execute_single_strategy(
        self,
        strategy: FallbackStrategy,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """执行单个降级策略"""
        try:
            if strategy == FallbackStrategy.BASIC_CRAWL4AI:
                return await self._basic_crawl4ai_extraction(task_id, url, platform, context)
            elif strategy == FallbackStrategy.LLM_EXTRACTION:
                return await self._llm_extraction(task_id, url, platform, context)
            elif strategy == FallbackStrategy.COSINE_SIMILARITY:
                return await self._cosine_similarity_extraction(task_id, url, platform, context)
            elif strategy == FallbackStrategy.MULTI_STRATEGY:
                return await self._multi_strategy_extraction(task_id, url, platform, context)
            elif strategy == FallbackStrategy.CUSTOM_EXTRACTION:
                return await self._custom_extraction(task_id, url, platform, context)
            else:
                return FallbackResult(
                    success=False,
                    strategy_used=strategy,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"未知的降级策略: {strategy.value}"
                )
                
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=strategy,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"策略执行失败: {str(e)}"
            )
    
    async def _basic_crawl4ai_extraction(
        self,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """基础Crawl4AI提取"""
        try:
            # 获取平台配置
            platform_config = self.platform_configs.get(platform, {})
            
            # 执行爬取
            result = await self.crawler.arun(
                url=url,
                word_count_threshold=10,
                bypass_cache=True,
                process_iframes=True,
                remove_overlay_elements=True,
                simulate_user=True,
                override_navigator=True,
                wait_for=platform_config.get('wait_for'),
                delay_before_return_html=platform_config.get('scroll_pause_time', 2)
            )
            
            if not result.success:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.BASIC_CRAWL4AI,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"Crawl4AI爬取失败: {result.error_message}"
                )
            
            # 解析结果
            extraction_result = self._parse_crawl4ai_result(
                result, url, platform, ExtractionMethod.CRAWL4AI_BASIC
            )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.BASIC_CRAWL4AI,
                extraction_result=extraction_result,
                processing_time=0.0,
                metadata={
                    'crawl4ai_success': result.success,
                    'content_length': len(result.cleaned_html or ''),
                    'links_found': len(result.links or {})
                }
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.BASIC_CRAWL4AI,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"基础Crawl4AI提取异常: {str(e)}"
            )
    
    async def _llm_extraction(
        self,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """LLM智能提取"""
        try:
            if not self.config.llm_config.get('api_token'):
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.LLM_EXTRACTION,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message="LLM API Token未配置"
                )
            
            # 构建提取策略
            extraction_strategy = LLMExtractionStrategy(
                provider=self.config.llm_config['provider'],
                api_token=self.config.llm_config['api_token'],
                schema={
                    "name": "NewsArticle",
                    "baseModel": "BaseModel",
                    "fields": {
                        "title": {"type": "string", "description": "文章标题"},
                        "content": {"type": "string", "description": "文章正文内容"},
                        "author": {"type": "string", "description": "作者姓名"},
                        "publish_time": {"type": "string", "description": "发布时间"},
                        "tags": {"type": "list", "description": "文章标签"},
                        "summary": {"type": "string", "description": "文章摘要"}
                    }
                },
                extraction_type="schema",
                instruction=f"从{platform}平台的页面中提取新闻文章信息，确保内容准确完整。"
            )
            
            # 执行爬取
            result = await self.crawler.arun(
                url=url,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                word_count_threshold=10
            )
            
            if not result.success:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.LLM_EXTRACTION,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"LLM提取失败: {result.error_message}"
                )
            
            # 解析LLM提取结果
            extraction_result = self._parse_llm_result(
                result, url, platform, ExtractionMethod.LLM_ENHANCED
            )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.LLM_EXTRACTION,
                extraction_result=extraction_result,
                processing_time=0.0,
                metadata={
                    'llm_provider': self.config.llm_config['provider'],
                    'llm_model': self.config.llm_config.get('model', 'unknown'),
                    'extracted_data': result.extracted_content
                }
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.LLM_EXTRACTION,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"LLM提取异常: {str(e)}"
            )
    
    async def _cosine_similarity_extraction(
        self,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """余弦相似度提取"""
        try:
            # 构建余弦相似度策略
            extraction_strategy = CosineStrategy(
                semantic_filter="新闻文章内容",
                word_count_threshold=10,
                max_dist=0.2,
                linkage_method="ward",
                top_k=3
            )
            
            # 执行爬取
            result = await self.crawler.arun(
                url=url,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                chunking_strategy=RegexChunking(),
                content_filter=BM25ContentFilter(user_query="新闻文章内容")
            )
            
            if not result.success:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.COSINE_SIMILARITY,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"余弦相似度提取失败: {result.error_message}"
                )
            
            # 解析余弦相似度结果
            extraction_result = self._parse_cosine_result(
                result, url, platform, ExtractionMethod.COSINE_SIMILARITY
            )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.COSINE_SIMILARITY,
                extraction_result=extraction_result,
                processing_time=0.0,
                metadata={
                    'similarity_threshold': 0.2,
                    'chunks_found': len(result.extracted_content) if result.extracted_content else 0
                }
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.COSINE_SIMILARITY,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"余弦相似度提取异常: {str(e)}"
            )
    
    async def _multi_strategy_extraction(
        self,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """多策略组合提取"""
        try:
            # 执行多个策略并合并结果
            strategies = [
                FallbackStrategy.BASIC_CRAWL4AI,
                FallbackStrategy.COSINE_SIMILARITY
            ]
            
            results = []
            for strategy in strategies:
                try:
                    result = await self._execute_single_strategy(
                        strategy, task_id, url, platform, context
                    )
                    if result.success:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"多策略中的单策略失败: {strategy.value}, 错误: {str(e)}")
                    continue
            
            if not results:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.MULTI_STRATEGY,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message="所有子策略都失败"
                )
            
            # 合并结果
            merged_result = self._merge_extraction_results(
                [r.extraction_result for r in results if r.extraction_result],
                url, platform
            )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.MULTI_STRATEGY,
                extraction_result=merged_result,
                processing_time=0.0,
                metadata={
                    'strategies_used': [r.strategy_used.value for r in results],
                    'results_merged': len(results)
                }
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.MULTI_STRATEGY,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"多策略提取异常: {str(e)}"
            )
    
    async def _custom_extraction(
        self,
        task_id: str,
        url: str,
        platform: str,
        context: Dict[str, Any]
    ) -> FallbackResult:
        """自定义提取"""
        try:
            # 获取平台特定的选择器
            platform_config = self.platform_configs.get(platform, {})
            selectors = platform_config.get('selectors', {})
            
            if not selectors:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.CUSTOM_EXTRACTION,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"平台 {platform} 没有配置自定义选择器"
                )
            
            # 执行基础爬取
            result = await self.crawler.arun(
                url=url,
                bypass_cache=True,
                word_count_threshold=10,
                wait_for=platform_config.get('wait_for'),
                delay_before_return_html=platform_config.get('scroll_pause_time', 2)
            )
            
            if not result.success:
                return FallbackResult(
                    success=False,
                    strategy_used=FallbackStrategy.CUSTOM_EXTRACTION,
                    extraction_result=None,
                    processing_time=0.0,
                    error_message=f"自定义提取爬取失败: {result.error_message}"
                )
            
            # 使用自定义选择器提取内容
            extraction_result = self._extract_with_selectors(
                result.cleaned_html, selectors, url, platform
            )
            
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.CUSTOM_EXTRACTION,
                extraction_result=extraction_result,
                processing_time=0.0,
                metadata={
                    'selectors_used': list(selectors.keys()),
                    'platform_config': platform
                }
            )
            
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.CUSTOM_EXTRACTION,
                extraction_result=None,
                processing_time=0.0,
                error_message=f"自定义提取异常: {str(e)}"
            )
    
    def _parse_crawl4ai_result(
        self,
        result: Any,
        url: str,
        platform: str,
        method: ExtractionMethod
    ) -> ExtractionResult:
        """解析Crawl4AI结果"""
        try:
            # 提取基础信息
            title = self._extract_title_from_html(result.cleaned_html) or "未知标题"
            content = result.markdown or result.cleaned_html or ""
            
            # 计算质量分数
            quality = self._calculate_content_quality(title, content)
            confidence = 0.7 if quality != ContentQuality.LOW else 0.3
            
            return ExtractionResult(
                title=title,
                content=content,
                author="",
                publish_time=None,
                tags=[],
                images=list(result.media.get('images', {}).keys()) if result.media else [],
                links=list(result.links.keys()) if result.links else [],
                summary=content[:200] + "..." if len(content) > 200 else content,
                quality=quality,
                confidence=confidence,
                extraction_method=method,
                processing_time=0.0,
                metadata={
                    'url': url,
                    'platform': platform,
                    'crawl4ai_success': result.success,
                    'content_length': len(content)
                }
            )
            
        except Exception as e:
            logger.error(f"解析Crawl4AI结果失败: {str(e)}")
            return ExtractionResult(
                title="解析失败",
                content="",
                quality=ContentQuality.LOW,
                confidence=0.1,
                extraction_method=method,
                metadata={'error': str(e)}
            )
    
    def _parse_llm_result(
        self,
        result: Any,
        url: str,
        platform: str,
        method: ExtractionMethod
    ) -> ExtractionResult:
        """解析LLM结果"""
        try:
            extracted_data = result.extracted_content
            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)
            
            title = extracted_data.get('title', '未知标题')
            content = extracted_data.get('content', '')
            author = extracted_data.get('author', '')
            publish_time = extracted_data.get('publish_time')
            tags = extracted_data.get('tags', [])
            summary = extracted_data.get('summary', '')
            
            # 计算质量分数
            quality = self._calculate_content_quality(title, content)
            confidence = 0.9 if quality == ContentQuality.HIGH else 0.6
            
            return ExtractionResult(
                title=title,
                content=content,
                author=author,
                publish_time=publish_time,
                tags=tags if isinstance(tags, list) else [],
                images=[],
                links=[],
                summary=summary or (content[:200] + "..." if len(content) > 200 else content),
                quality=quality,
                confidence=confidence,
                extraction_method=method,
                processing_time=0.0,
                metadata={
                    'url': url,
                    'platform': platform,
                    'llm_extracted': True,
                    'raw_extraction': extracted_data
                }
            )
            
        except Exception as e:
            logger.error(f"解析LLM结果失败: {str(e)}")
            return ExtractionResult(
                title="LLM解析失败",
                content="",
                quality=ContentQuality.LOW,
                confidence=0.1,
                extraction_method=method,
                metadata={'error': str(e)}
            )
    
    def _parse_cosine_result(
        self,
        result: Any,
        url: str,
        platform: str,
        method: ExtractionMethod
    ) -> ExtractionResult:
        """解析余弦相似度结果"""
        try:
            content = result.extracted_content or ""
            if isinstance(content, list):
                content = "\n".join(str(item) for item in content)
            
            title = self._extract_title_from_html(result.cleaned_html) or "余弦相似度提取"
            
            # 计算质量分数
            quality = self._calculate_content_quality(title, content)
            confidence = 0.8 if quality != ContentQuality.LOW else 0.4
            
            return ExtractionResult(
                title=title,
                content=content,
                author="",
                publish_time=None,
                tags=[],
                images=[],
                links=[],
                summary=content[:200] + "..." if len(content) > 200 else content,
                quality=quality,
                confidence=confidence,
                extraction_method=method,
                processing_time=0.0,
                metadata={
                    'url': url,
                    'platform': platform,
                    'cosine_similarity': True,
                    'content_length': len(content)
                }
            )
            
        except Exception as e:
            logger.error(f"解析余弦相似度结果失败: {str(e)}")
            return ExtractionResult(
                title="余弦相似度解析失败",
                content="",
                quality=ContentQuality.LOW,
                confidence=0.1,
                extraction_method=method,
                metadata={'error': str(e)}
            )
    
    def _extract_with_selectors(
        self,
        html: str,
        selectors: Dict[str, List[str]],
        url: str,
        platform: str
    ) -> ExtractionResult:
        """使用选择器提取内容"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            extracted = {}
            
            for field, selector_list in selectors.items():
                for selector in selector_list:
                    try:
                        elements = soup.select(selector)
                        if elements:
                            if field in ['tags']:
                                extracted[field] = [elem.get_text(strip=True) for elem in elements]
                            else:
                                extracted[field] = elements[0].get_text(strip=True)
                            break
                    except Exception as e:
                        logger.debug(f"选择器失败 {selector}: {str(e)}")
                        continue
            
            title = extracted.get('title', '自定义提取')
            content = extracted.get('content', '')
            author = extracted.get('author', '')
            tags = extracted.get('tags', [])
            
            # 计算质量分数
            quality = self._calculate_content_quality(title, content)
            confidence = 0.8 if quality != ContentQuality.LOW else 0.5
            
            return ExtractionResult(
                title=title,
                content=content,
                author=author,
                publish_time=extracted.get('time'),
                tags=tags,
                images=[],
                links=[],
                summary=content[:200] + "..." if len(content) > 200 else content,
                quality=quality,
                confidence=confidence,
                extraction_method=ExtractionMethod.CUSTOM_SELECTORS,
                processing_time=0.0,
                metadata={
                    'url': url,
                    'platform': platform,
                    'custom_selectors': True,
                    'extracted_fields': list(extracted.keys())
                }
            )
            
        except Exception as e:
            logger.error(f"选择器提取失败: {str(e)}")
            return ExtractionResult(
                title="选择器提取失败",
                content="",
                quality=ContentQuality.LOW,
                confidence=0.1,
                extraction_method=ExtractionMethod.CUSTOM_SELECTORS,
                metadata={'error': str(e)}
            )
    
    def _merge_extraction_results(
        self,
        results: List[ExtractionResult],
        url: str,
        platform: str
    ) -> ExtractionResult:
        """合并多个提取结果"""
        if not results:
            return ExtractionResult(
                title="合并失败",
                content="",
                quality=ContentQuality.LOW,
                confidence=0.1,
                extraction_method=ExtractionMethod.HYBRID
            )
        
        # 选择质量最高的结果作为基础
        best_result = max(results, key=lambda r: r.confidence)
        
        # 合并内容
        merged_content = best_result.content
        merged_tags = list(set(best_result.tags))
        merged_images = list(set(best_result.images))
        merged_links = list(set(best_result.links))
        
        # 从其他结果中补充信息
        for result in results:
            if result != best_result:
                if not best_result.author and result.author:
                    best_result.author = result.author
                if not best_result.publish_time and result.publish_time:
                    best_result.publish_time = result.publish_time
                
                merged_tags.extend(result.tags)
                merged_images.extend(result.images)
                merged_links.extend(result.links)
        
        # 去重
        merged_tags = list(set(merged_tags))
        merged_images = list(set(merged_images))
        merged_links = list(set(merged_links))
        
        # 计算合并后的质量和置信度
        avg_confidence = sum(r.confidence for r in results) / len(results)
        quality = self._calculate_content_quality(best_result.title, merged_content)
        
        return ExtractionResult(
            title=best_result.title,
            content=merged_content,
            author=best_result.author,
            publish_time=best_result.publish_time,
            tags=merged_tags,
            images=merged_images,
            links=merged_links,
            summary=best_result.summary,
            quality=quality,
            confidence=min(avg_confidence + 0.1, 1.0),  # 合并提升置信度
            extraction_method=ExtractionMethod.HYBRID,
            processing_time=0.0,
            metadata={
                'url': url,
                'platform': platform,
                'merged_results': len(results),
                'base_method': best_result.extraction_method.value
            }
        )
    
    def _extract_title_from_html(self, html: str) -> Optional[str]:
        """从HTML中提取标题"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 尝试多种标题选择器
            title_selectors = [
                'title',
                'h1',
                '.title',
                '[data-title]',
                '.article-title',
                '.post-title'
            ]
            
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if title and len(title) > 5:  # 标题长度合理
                        return title
            
            return None
            
        except Exception as e:
            logger.debug(f"提取标题失败: {str(e)}")
            return None
    
    def _calculate_content_quality(self, title: str, content: str) -> ContentQuality:
        """计算内容质量"""
        try:
            # 基础质量检查
            if not title or not content:
                return ContentQuality.LOW
            
            # 长度检查
            if len(content) < 50:
                return ContentQuality.LOW
            elif len(content) < 200:
                return ContentQuality.MEDIUM
            
            # 标题质量检查
            if len(title) < 5 or len(title) > 200:
                return ContentQuality.MEDIUM
            
            # 内容质量检查
            if len(content) > 500 and len(title) > 10:
                return ContentQuality.HIGH
            
            return ContentQuality.MEDIUM
            
        except Exception as e:
            logger.debug(f"计算内容质量失败: {str(e)}")
            return ContentQuality.LOW
    
    def _is_quality_acceptable(self, result: Optional[ExtractionResult]) -> bool:
        """检查质量是否可接受"""
        if not result:
            return False
        
        return (
            result.confidence >= self.config.quality_threshold and
            result.quality != ContentQuality.LOW and
            len(result.content) >= 50
        )
    
    async def _log_fallback_trigger(
        self,
        task_id: str,
        url: str,
        platform: str,
        trigger_reason: FallbackTrigger,
        original_error: str,
        context: Dict[str, Any]
    ):
        """记录降级触发日志"""
        try:
            if self.persistence_manager:
                await self.persistence_manager.persist_error_log(
                    task_id=task_id,
                    error_type="fallback_trigger",
                    error_message=f"触发Crawl4AI降级: {trigger_reason.value}",
                    stack_trace=original_error,
                    context={
                        'url': url,
                        'platform': platform,
                        'trigger_reason': trigger_reason.value,
                        'original_error': original_error,
                        'context': context
                    }
                )
        except Exception as e:
            logger.error(f"记录降级触发日志失败: {str(e)}")
    
    async def _log_fallback_result(
        self,
        task_id: str,
        result: FallbackResult
    ):
        """记录降级结果日志"""
        try:
            if self.persistence_manager:
                if result.success:
                    # 记录成功的降级结果
                    await self.persistence_manager.persist_crawl_result(
                        task_id=task_id,
                        url=result.extraction_result.metadata.get('url', ''),
                        platform=result.extraction_result.metadata.get('platform', ''),
                        extraction_result=result.extraction_result
                    )
                else:
                    # 记录失败的降级尝试
                    await self.persistence_manager.persist_error_log(
                        task_id=task_id,
                        error_type="fallback_failed",
                        error_message=result.error_message,
                        context={
                            'strategy_used': result.strategy_used.value,
                            'processing_time': result.processing_time,
                            'retry_count': result.retry_count,
                            'metadata': result.metadata
                        }
                    )
        except Exception as e:
            logger.error(f"记录降级结果日志失败: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            crawler_healthy = self.crawler is not None
            persistence_healthy = self.persistence_manager is not None
            
            return {
                'status': 'healthy' if crawler_healthy and persistence_healthy else 'unhealthy',
                'crawler_initialized': crawler_healthy,
                'persistence_connected': persistence_healthy,
                'config_enabled': self.config.enabled,
                'strategies_available': len(self.config.strategies),
                'stats': self.get_stats(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def shutdown(self):
        """关闭降级服务"""
        try:
            logger.info("关闭Crawl4AI降级服务...")
            
            if self.crawler:
                await self.crawler.close()
                self.crawler = None
            
            logger.info("Crawl4AI降级服务已关闭")
            
        except Exception as e:
            logger.error(f"关闭降级服务失败: {str(e)}")

# 全局降级服务实例
_fallback_service = None

async def get_fallback_service(config: FallbackConfig = None) -> Crawl4AIFallbackService:
    """获取降级服务实例"""
    global _fallback_service
    
    if _fallback_service is None:
        if config is None:
            config = FallbackConfig()
        
        _fallback_service = Crawl4AIFallbackService(config)
        
        if not await _fallback_service.initialize():
            raise RuntimeError("Crawl4AI降级服务初始化失败")
    
    return _fallback_service

async def shutdown_fallback_service():
    """关闭降级服务"""
    global _fallback_service
    
    if _fallback_service:
        await _fallback_service.shutdown()
        _fallback_service = None