#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量评估系统
实现内容质量评分算法、智能重试策略和质量监控机制
提供全面的数据质量保障和自动化质量控制
"""

import asyncio
import json
import logging
import re
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import statistics
import hashlib
import difflib
from urllib.parse import urlparse

# NLP相关库
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logging.warning("jieba未安装，将使用基础文本分析")

from storage.persistence_manager import get_persistence_manager

logger = logging.getLogger(__name__)

class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"     # 优秀 (90-100)
    GOOD = "good"               # 良好 (70-89)
    FAIR = "fair"               # 一般 (50-69)
    POOR = "poor"               # 较差 (30-49)
    VERY_POOR = "very_poor"     # 很差 (0-29)

class QualityDimension(Enum):
    """质量维度"""
    COMPLETENESS = "completeness"       # 完整性
    ACCURACY = "accuracy"               # 准确性
    CONSISTENCY = "consistency"         # 一致性
    RELEVANCE = "relevance"             # 相关性
    FRESHNESS = "freshness"             # 时效性
    UNIQUENESS = "uniqueness"           # 唯一性
    READABILITY = "readability"         # 可读性
    STRUCTURE = "structure"             # 结构性

class RetryReason(Enum):
    """重试原因"""
    LOW_QUALITY = "low_quality"         # 质量过低
    INCOMPLETE_DATA = "incomplete_data" # 数据不完整
    EXTRACTION_ERROR = "extraction_error" # 提取错误
    VALIDATION_FAILED = "validation_failed" # 验证失败
    TIMEOUT = "timeout"                 # 超时
    NETWORK_ERROR = "network_error"     # 网络错误
    CONTENT_CHANGED = "content_changed" # 内容变化
    CUSTOM = "custom"                   # 自定义原因

@dataclass
class QualityMetrics:
    """质量指标"""
    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    quality_level: QualityLevel = QualityLevel.POOR
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class ContentAnalysis:
    """内容分析结果"""
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    unique_words: int = 0
    readability_score: float = 0.0
    keyword_density: Dict[str, float] = field(default_factory=dict)
    language_detected: str = "unknown"
    encoding_issues: bool = False
    html_tags_count: int = 0
    links_count: int = 0
    images_count: int = 0
    content_hash: str = ""
    duplicate_sentences: int = 0
    avg_sentence_length: float = 0.0

@dataclass
class RetryStrategy:
    """重试策略"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_conditions: List[RetryReason] = field(default_factory=list)
    quality_threshold: float = 0.5
    timeout_multiplier: float = 1.5
    custom_conditions: List[Callable] = field(default_factory=list)

@dataclass
class QualityConfig:
    """质量评估配置"""
    # 权重配置
    dimension_weights: Dict[str, float] = field(default_factory=lambda: {
        'completeness': 0.25,
        'accuracy': 0.20,
        'consistency': 0.15,
        'relevance': 0.15,
        'freshness': 0.10,
        'uniqueness': 0.10,
        'readability': 0.03,
        'structure': 0.02
    })
    
    # 阈值配置
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'min_word_count': 10,
        'max_word_count': 50000,
        'min_sentence_count': 1,
        'max_duplicate_ratio': 0.3,
        'min_readability_score': 0.3,
        'max_html_ratio': 0.2,
        'min_content_length': 50,
        'max_extraction_time': 30.0
    })
    
    # 平台特定配置
    platform_configs: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'weibo': {
            'min_word_count': 5,
            'max_word_count': 2000,
            'relevance_keywords': ['微博', '转发', '评论', '点赞'],
            'structure_requirements': ['author', 'content', 'publish_time']
        },
        'xiaohongshu': {
            'min_word_count': 10,
            'max_word_count': 5000,
            'relevance_keywords': ['小红书', '笔记', '种草', '分享'],
            'structure_requirements': ['title', 'content', 'author', 'tags']
        },
        'douyin': {
            'min_word_count': 5,
            'max_word_count': 1000,
            'relevance_keywords': ['抖音', '视频', '短视频'],
            'structure_requirements': ['title', 'author', 'video_url']
        }
    })
    
    # 重试策略
    default_retry_strategy: RetryStrategy = field(default_factory=lambda: RetryStrategy(
        max_retries=3,
        base_delay=2.0,
        retry_conditions=[RetryReason.LOW_QUALITY, RetryReason.INCOMPLETE_DATA]
    ))
    
    # 监控配置
    monitoring: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'sample_rate': 0.1,
        'alert_threshold': 0.3,
        'trend_window': 100,
        'report_interval': 300
    })

class QualityAssessor:
    """数据质量评估器"""
    
    def __init__(self, config: QualityConfig):
        self.config = config
        self.persistence_manager = None
        
        # 质量历史记录
        self.quality_history: deque = deque(maxlen=10000)
        self.platform_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_assessments': 0,
            'average_quality': 0.0,
            'quality_distribution': defaultdict(int),
            'common_issues': defaultdict(int),
            'retry_stats': defaultdict(int)
        })
        
        # 缓存和优化
        self.content_cache: Dict[str, QualityMetrics] = {}
        self.analysis_cache: Dict[str, ContentAnalysis] = {}
        
        # 监控状态
        self.monitoring_enabled = config.monitoring.get('enabled', True)
        self.quality_trends: deque = deque(maxlen=1000)
        
        # 锁
        self.cache_lock = threading.RLock()
        self.stats_lock = threading.RLock()
        
        # 初始化NLP工具
        self._init_nlp_tools()
    
    def _init_nlp_tools(self):
        """初始化NLP工具"""
        try:
            if JIEBA_AVAILABLE:
                # 添加自定义词典
                jieba.add_word('小红书')
                jieba.add_word('抖音')
                jieba.add_word('微博')
                logger.info("jieba分词工具初始化成功")
            else:
                logger.warning("jieba不可用，将使用基础文本分析")
        except Exception as e:
            logger.error(f"初始化NLP工具失败: {str(e)}")
    
    async def initialize(self):
        """初始化评估器"""
        try:
            self.persistence_manager = await get_persistence_manager()
            logger.info("质量评估器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化质量评估器失败: {str(e)}")
            return False
    
    async def assess_quality(
        self,
        content: Dict[str, Any],
        platform: str = "unknown",
        url: str = "",
        extraction_time: float = 0.0,
        context: Dict[str, Any] = None
    ) -> QualityMetrics:
        """评估内容质量"""
        try:
            start_time = time.time()
            
            # 检查缓存
            content_hash = self._calculate_content_hash(content)
            cached_metrics = self._get_cached_metrics(content_hash)
            if cached_metrics:
                return cached_metrics
            
            # 内容分析
            analysis = await self._analyze_content(content, platform, url)
            
            # 计算各维度分数
            dimension_scores = await self._calculate_dimension_scores(
                content, analysis, platform, extraction_time, context
            )
            
            # 计算总分
            overall_score = self._calculate_overall_score(dimension_scores)
            
            # 确定质量等级
            quality_level = self._determine_quality_level(overall_score)
            
            # 生成问题和建议
            issues, suggestions = await self._generate_feedback(
                content, analysis, dimension_scores, platform
            )
            
            # 计算置信度
            confidence = self._calculate_confidence(analysis, dimension_scores)
            
            # 创建质量指标
            metrics = QualityMetrics(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                quality_level=quality_level,
                confidence=confidence,
                issues=issues,
                suggestions=suggestions,
                metadata={
                    'platform': platform,
                    'url': url,
                    'extraction_time': extraction_time,
                    'assessment_time': time.time() - start_time,
                    'content_hash': content_hash,
                    'analysis': asdict(analysis)
                }
            )
            
            # 缓存结果
            self._cache_metrics(content_hash, metrics)
            
            # 更新统计
            await self._update_statistics(platform, metrics)
            
            # 记录历史
            self.quality_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"质量评估失败: {str(e)}")
            return QualityMetrics(
                overall_score=0.0,
                quality_level=QualityLevel.VERY_POOR,
                issues=[f"评估失败: {str(e)}"],
                metadata={'error': str(e)}
            )
    
    async def _analyze_content(self, content: Dict[str, Any], platform: str, url: str) -> ContentAnalysis:
        """分析内容"""
        try:
            # 提取文本内容
            text_content = self._extract_text_content(content)
            
            # 基础统计
            word_count = len(text_content.split()) if text_content else 0
            sentences = re.split(r'[.!?。！？]', text_content) if text_content else []
            sentence_count = len([s for s in sentences if s.strip()])
            paragraphs = text_content.split('\n\n') if text_content else []
            paragraph_count = len([p for p in paragraphs if p.strip()])
            
            # 唯一词汇统计
            words = text_content.lower().split() if text_content else []
            unique_words = len(set(words))
            
            # 可读性评分
            readability_score = self._calculate_readability(text_content, word_count, sentence_count)
            
            # 关键词密度
            keyword_density = self._calculate_keyword_density(text_content, platform)
            
            # 语言检测
            language_detected = self._detect_language(text_content)
            
            # 编码问题检测
            encoding_issues = self._detect_encoding_issues(text_content)
            
            # HTML标签统计
            html_content = str(content)
            html_tags_count = len(re.findall(r'<[^>]+>', html_content))
            
            # 链接和图片统计
            links_count = len(re.findall(r'https?://[^\s]+', html_content))
            images_count = len(re.findall(r'<img[^>]*>|\.(jpg|jpeg|png|gif|webp)', html_content, re.IGNORECASE))
            
            # 内容哈希
            content_hash = self._calculate_content_hash(content)
            
            # 重复句子检测
            duplicate_sentences = self._count_duplicate_sentences(sentences)
            
            # 平均句子长度
            valid_sentences = [s.strip() for s in sentences if s.strip()]
            avg_sentence_length = statistics.mean([len(s.split()) for s in valid_sentences]) if valid_sentences else 0.0
            
            return ContentAnalysis(
                word_count=word_count,
                sentence_count=sentence_count,
                paragraph_count=paragraph_count,
                unique_words=unique_words,
                readability_score=readability_score,
                keyword_density=keyword_density,
                language_detected=language_detected,
                encoding_issues=encoding_issues,
                html_tags_count=html_tags_count,
                links_count=links_count,
                images_count=images_count,
                content_hash=content_hash,
                duplicate_sentences=duplicate_sentences,
                avg_sentence_length=avg_sentence_length
            )
            
        except Exception as e:
            logger.error(f"内容分析失败: {str(e)}")
            return ContentAnalysis()
    
    def _extract_text_content(self, content: Dict[str, Any]) -> str:
        """提取文本内容"""
        try:
            text_parts = []
            
            # 提取各种文本字段
            text_fields = ['title', 'content', 'description', 'summary', 'text']
            for field in text_fields:
                if field in content and content[field]:
                    text_parts.append(str(content[field]))
            
            # 清理HTML标签
            text = ' '.join(text_parts)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
            
        except Exception as e:
            logger.error(f"提取文本内容失败: {str(e)}")
            return ""
    
    def _calculate_readability(self, text: str, word_count: int, sentence_count: int) -> float:
        """计算可读性分数"""
        try:
            if not text or word_count == 0 or sentence_count == 0:
                return 0.0
            
            # 简化的可读性评分算法
            avg_sentence_length = word_count / sentence_count
            
            # 复杂词汇比例（长度>6的词）
            words = text.split()
            complex_words = sum(1 for word in words if len(word) > 6)
            complex_ratio = complex_words / word_count if word_count > 0 else 0
            
            # 可读性分数 (0-1)
            readability = 1.0 - min(1.0, (avg_sentence_length / 20.0 + complex_ratio) / 2.0)
            
            return max(0.0, readability)
            
        except Exception as e:
            logger.error(f"计算可读性失败: {str(e)}")
            return 0.0
    
    def _calculate_keyword_density(self, text: str, platform: str) -> Dict[str, float]:
        """计算关键词密度"""
        try:
            if not text:
                return {}
            
            # 获取平台相关关键词
            platform_config = self.config.platform_configs.get(platform, {})
            relevance_keywords = platform_config.get('relevance_keywords', [])
            
            # 分词
            if JIEBA_AVAILABLE:
                words = list(jieba.cut(text.lower()))
            else:
                words = text.lower().split()
            
            total_words = len(words)
            if total_words == 0:
                return {}
            
            # 计算关键词密度
            keyword_density = {}
            for keyword in relevance_keywords:
                count = words.count(keyword.lower())
                density = count / total_words
                if density > 0:
                    keyword_density[keyword] = density
            
            # 提取高频词
            if JIEBA_AVAILABLE:
                try:
                    top_keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=True)
                    for keyword, weight in top_keywords:
                        if keyword not in keyword_density:
                            keyword_density[keyword] = weight
                except:
                    pass
            
            return keyword_density
            
        except Exception as e:
            logger.error(f"计算关键词密度失败: {str(e)}")
            return {}
    
    def _detect_language(self, text: str) -> str:
        """检测语言"""
        try:
            if not text:
                return "unknown"
            
            # 简单的中英文检测
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            english_chars = len(re.findall(r'[a-zA-Z]', text))
            total_chars = len(text)
            
            if chinese_chars / total_chars > 0.3:
                return "chinese"
            elif english_chars / total_chars > 0.5:
                return "english"
            else:
                return "mixed"
                
        except Exception as e:
            logger.error(f"语言检测失败: {str(e)}")
            return "unknown"
    
    def _detect_encoding_issues(self, text: str) -> bool:
        """检测编码问题"""
        try:
            if not text:
                return False
            
            # 检测常见编码问题标志
            encoding_issues = [
                '\ufffd',  # 替换字符
                '\u0000',  # 空字符
                '\x00',    # 空字节
                '\\x',     # 转义序列
                '\\u',     # Unicode转义
            ]
            
            return any(issue in text for issue in encoding_issues)
            
        except Exception as e:
            logger.error(f"编码问题检测失败: {str(e)}")
            return False
    
    def _count_duplicate_sentences(self, sentences: List[str]) -> int:
        """统计重复句子"""
        try:
            if not sentences:
                return 0
            
            # 清理句子
            clean_sentences = [s.strip().lower() for s in sentences if s.strip()]
            
            # 统计重复
            sentence_counts = defaultdict(int)
            for sentence in clean_sentences:
                sentence_counts[sentence] += 1
            
            # 计算重复句子数
            duplicates = sum(count - 1 for count in sentence_counts.values() if count > 1)
            
            return duplicates
            
        except Exception as e:
            logger.error(f"统计重复句子失败: {str(e)}")
            return 0
    
    async def _calculate_dimension_scores(
        self,
        content: Dict[str, Any],
        analysis: ContentAnalysis,
        platform: str,
        extraction_time: float,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """计算各维度分数"""
        try:
            scores = {}
            
            # 完整性评分
            scores['completeness'] = await self._score_completeness(content, platform)
            
            # 准确性评分
            scores['accuracy'] = await self._score_accuracy(content, analysis, platform)
            
            # 一致性评分
            scores['consistency'] = await self._score_consistency(content, analysis)
            
            # 相关性评分
            scores['relevance'] = await self._score_relevance(content, analysis, platform)
            
            # 时效性评分
            scores['freshness'] = await self._score_freshness(content, extraction_time)
            
            # 唯一性评分
            scores['uniqueness'] = await self._score_uniqueness(content, analysis)
            
            # 可读性评分
            scores['readability'] = analysis.readability_score
            
            # 结构性评分
            scores['structure'] = await self._score_structure(content, platform)
            
            return scores
            
        except Exception as e:
            logger.error(f"计算维度分数失败: {str(e)}")
            return {dim: 0.0 for dim in QualityDimension}
    
    async def _score_completeness(self, content: Dict[str, Any], platform: str) -> float:
        """评分完整性"""
        try:
            platform_config = self.config.platform_configs.get(platform, {})
            required_fields = platform_config.get('structure_requirements', [])
            
            if not required_fields:
                # 通用必需字段
                required_fields = ['title', 'content', 'author']
            
            # 检查必需字段
            present_fields = 0
            for field in required_fields:
                if field in content and content[field] and str(content[field]).strip():
                    present_fields += 1
            
            completeness_score = present_fields / len(required_fields) if required_fields else 1.0
            
            # 检查内容长度
            text_content = self._extract_text_content(content)
            min_length = self.config.quality_thresholds.get('min_content_length', 50)
            
            if len(text_content) < min_length:
                completeness_score *= 0.5
            
            return min(1.0, completeness_score)
            
        except Exception as e:
            logger.error(f"完整性评分失败: {str(e)}")
            return 0.0
    
    async def _score_accuracy(self, content: Dict[str, Any], analysis: ContentAnalysis, platform: str) -> float:
        """评分准确性"""
        try:
            accuracy_score = 1.0
            
            # 检查编码问题
            if analysis.encoding_issues:
                accuracy_score *= 0.7
            
            # 检查HTML标签比例
            text_length = len(self._extract_text_content(content))
            if text_length > 0:
                html_ratio = analysis.html_tags_count / text_length
                max_html_ratio = self.config.quality_thresholds.get('max_html_ratio', 0.2)
                if html_ratio > max_html_ratio:
                    accuracy_score *= (1.0 - min(0.5, html_ratio - max_html_ratio))
            
            # 检查重复内容
            if analysis.sentence_count > 0:
                duplicate_ratio = analysis.duplicate_sentences / analysis.sentence_count
                max_duplicate_ratio = self.config.quality_thresholds.get('max_duplicate_ratio', 0.3)
                if duplicate_ratio > max_duplicate_ratio:
                    accuracy_score *= (1.0 - min(0.4, duplicate_ratio - max_duplicate_ratio))
            
            return max(0.0, accuracy_score)
            
        except Exception as e:
            logger.error(f"准确性评分失败: {str(e)}")
            return 0.0
    
    async def _score_consistency(self, content: Dict[str, Any], analysis: ContentAnalysis) -> float:
        """评分一致性"""
        try:
            consistency_score = 1.0
            
            # 检查字段一致性
            title = content.get('title', '')
            text_content = self._extract_text_content(content)
            
            if title and text_content:
                # 标题和内容的相似性
                similarity = self._calculate_text_similarity(title, text_content[:200])
                if similarity < 0.1:  # 相似性过低
                    consistency_score *= 0.8
            
            # 检查语言一致性
            if analysis.language_detected == "mixed":
                consistency_score *= 0.9
            
            # 检查句子长度一致性
            if analysis.avg_sentence_length > 0:
                # 句子长度变异系数
                if analysis.sentence_count > 1:
                    # 这里简化处理，实际应该计算标准差
                    consistency_score *= 0.95
            
            return max(0.0, consistency_score)
            
        except Exception as e:
            logger.error(f"一致性评分失败: {str(e)}")
            return 0.0
    
    async def _score_relevance(self, content: Dict[str, Any], analysis: ContentAnalysis, platform: str) -> float:
        """评分相关性"""
        try:
            platform_config = self.config.platform_configs.get(platform, {})
            relevance_keywords = platform_config.get('relevance_keywords', [])
            
            if not relevance_keywords:
                return 0.8  # 默认相关性
            
            # 计算关键词匹配度
            keyword_matches = 0
            for keyword in relevance_keywords:
                if keyword.lower() in analysis.keyword_density:
                    keyword_matches += 1
            
            relevance_score = keyword_matches / len(relevance_keywords) if relevance_keywords else 0.8
            
            # 考虑关键词密度
            total_density = sum(analysis.keyword_density.values())
            if total_density > 0.1:  # 关键词密度过高可能是垃圾内容
                relevance_score *= 0.9
            
            return min(1.0, relevance_score)
            
        except Exception as e:
            logger.error(f"相关性评分失败: {str(e)}")
            return 0.0
    
    async def _score_freshness(self, content: Dict[str, Any], extraction_time: float) -> float:
        """评分时效性"""
        try:
            # 检查发布时间
            publish_time = content.get('publish_time') or content.get('created_at')
            if publish_time:
                try:
                    if isinstance(publish_time, str):
                        # 尝试解析时间字符串
                        from dateutil import parser
                        publish_dt = parser.parse(publish_time)
                    else:
                        publish_dt = publish_time
                    
                    # 计算时间差
                    now = datetime.now(timezone.utc)
                    if publish_dt.tzinfo is None:
                        publish_dt = publish_dt.replace(tzinfo=timezone.utc)
                    
                    time_diff = (now - publish_dt).total_seconds()
                    
                    # 时效性评分（24小时内为1.0，逐渐递减）
                    if time_diff < 86400:  # 24小时
                        freshness_score = 1.0
                    elif time_diff < 604800:  # 7天
                        freshness_score = 0.8
                    elif time_diff < 2592000:  # 30天
                        freshness_score = 0.6
                    else:
                        freshness_score = 0.4
                    
                    return freshness_score
                    
                except Exception:
                    pass
            
            # 如果没有发布时间，根据提取时间评估
            if extraction_time > 0:
                max_extraction_time = self.config.quality_thresholds.get('max_extraction_time', 30.0)
                if extraction_time > max_extraction_time:
                    return 0.6  # 提取时间过长可能内容已过时
            
            return 0.7  # 默认时效性
            
        except Exception as e:
            logger.error(f"时效性评分失败: {str(e)}")
            return 0.0
    
    async def _score_uniqueness(self, content: Dict[str, Any], analysis: ContentAnalysis) -> float:
        """评分唯一性"""
        try:
            # 检查内容哈希是否已存在
            content_hash = analysis.content_hash
            
            # 这里应该查询数据库检查重复内容
            # 简化处理，基于重复句子比例评估
            if analysis.sentence_count > 0:
                duplicate_ratio = analysis.duplicate_sentences / analysis.sentence_count
                uniqueness_score = 1.0 - min(0.8, duplicate_ratio * 2)
            else:
                uniqueness_score = 0.5
            
            # 检查词汇多样性
            if analysis.word_count > 0:
                vocabulary_diversity = analysis.unique_words / analysis.word_count
                if vocabulary_diversity < 0.3:  # 词汇多样性过低
                    uniqueness_score *= 0.8
            
            return max(0.0, uniqueness_score)
            
        except Exception as e:
            logger.error(f"唯一性评分失败: {str(e)}")
            return 0.0
    
    async def _score_structure(self, content: Dict[str, Any], platform: str) -> float:
        """评分结构性"""
        try:
            structure_score = 1.0
            
            # 检查必需字段的数据类型
            type_checks = {
                'title': str,
                'content': str,
                'author': str,
                'publish_time': (str, datetime),
                'tags': (list, str),
                'links': list,
                'images': list
            }
            
            for field, expected_type in type_checks.items():
                if field in content and content[field] is not None:
                    if not isinstance(content[field], expected_type):
                        structure_score *= 0.95
            
            # 检查嵌套结构
            if isinstance(content, dict):
                # 检查是否有过深的嵌套
                max_depth = self._calculate_dict_depth(content)
                if max_depth > 5:
                    structure_score *= 0.9
            
            return max(0.0, structure_score)
            
        except Exception as e:
            logger.error(f"结构性评分失败: {str(e)}")
            return 0.0
    
    def _calculate_dict_depth(self, d: dict, depth: int = 0) -> int:
        """计算字典嵌套深度"""
        if not isinstance(d, dict):
            return depth
        
        max_depth = depth
        for value in d.values():
            if isinstance(value, dict):
                max_depth = max(max_depth, self._calculate_dict_depth(value, depth + 1))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        max_depth = max(max_depth, self._calculate_dict_depth(item, depth + 1))
        
        return max_depth
    
    def _calculate_overall_score(self, dimension_scores: Dict[str, float]) -> float:
        """计算总分"""
        try:
            total_score = 0.0
            total_weight = 0.0
            
            for dimension, score in dimension_scores.items():
                weight = self.config.dimension_weights.get(dimension, 0.0)
                total_score += score * weight
                total_weight += weight
            
            if total_weight == 0:
                return 0.0
            
            return min(1.0, total_score / total_weight)
            
        except Exception as e:
            logger.error(f"计算总分失败: {str(e)}")
            return 0.0
    
    def _determine_quality_level(self, overall_score: float) -> QualityLevel:
        """确定质量等级"""
        if overall_score >= 0.9:
            return QualityLevel.EXCELLENT
        elif overall_score >= 0.7:
            return QualityLevel.GOOD
        elif overall_score >= 0.5:
            return QualityLevel.FAIR
        elif overall_score >= 0.3:
            return QualityLevel.POOR
        else:
            return QualityLevel.VERY_POOR
    
    async def _generate_feedback(
        self,
        content: Dict[str, Any],
        analysis: ContentAnalysis,
        dimension_scores: Dict[str, float],
        platform: str
    ) -> Tuple[List[str], List[str]]:
        """生成问题和建议"""
        try:
            issues = []
            suggestions = []
            
            # 检查各维度问题
            for dimension, score in dimension_scores.items():
                if score < 0.5:
                    issue, suggestion = self._get_dimension_feedback(dimension, score, content, analysis, platform)
                    if issue:
                        issues.append(issue)
                    if suggestion:
                        suggestions.append(suggestion)
            
            # 通用问题检查
            if analysis.word_count < self.config.quality_thresholds.get('min_word_count', 10):
                issues.append("内容过短")
                suggestions.append("增加内容长度，提供更详细的信息")
            
            if analysis.encoding_issues:
                issues.append("存在编码问题")
                suggestions.append("检查内容编码，确保文本正确显示")
            
            if analysis.duplicate_sentences > analysis.sentence_count * 0.3:
                issues.append("重复内容过多")
                suggestions.append("减少重复句子，提高内容原创性")
            
            return issues, suggestions
            
        except Exception as e:
            logger.error(f"生成反馈失败: {str(e)}")
            return [], []
    
    def _get_dimension_feedback(self, dimension: str, score: float, content: Dict, analysis: ContentAnalysis, platform: str) -> Tuple[str, str]:
        """获取维度反馈"""
        feedback_map = {
            'completeness': (
                f"内容完整性不足 (分数: {score:.2f})",
                "补充缺失的必需字段，如标题、作者、发布时间等"
            ),
            'accuracy': (
                f"内容准确性有问题 (分数: {score:.2f})",
                "检查并修正编码错误、HTML标签和重复内容"
            ),
            'consistency': (
                f"内容一致性较差 (分数: {score:.2f})",
                "确保标题与内容匹配，保持语言和格式一致"
            ),
            'relevance': (
                f"内容相关性不高 (分数: {score:.2f})",
                f"增加与{platform}平台相关的关键词和内容"
            ),
            'freshness': (
                f"内容时效性较差 (分数: {score:.2f})",
                "确保内容是最新的，或标注发布时间"
            ),
            'uniqueness': (
                f"内容唯一性不足 (分数: {score:.2f})",
                "提高内容原创性，减少重复和模板化内容"
            ),
            'readability': (
                f"内容可读性较差 (分数: {score:.2f})",
                "优化句子长度和词汇选择，提高可读性"
            ),
            'structure': (
                f"内容结构性有问题 (分数: {score:.2f})",
                "规范数据格式和字段类型，优化内容结构"
            )
        }
        
        return feedback_map.get(dimension, ("", ""))
    
    def _calculate_confidence(self, analysis: ContentAnalysis, dimension_scores: Dict[str, float]) -> float:
        """计算置信度"""
        try:
            confidence_factors = []
            
            # 内容长度因子
            if analysis.word_count > 50:
                confidence_factors.append(0.9)
            elif analysis.word_count > 20:
                confidence_factors.append(0.7)
            else:
                confidence_factors.append(0.5)
            
            # 结构完整性因子
            structure_score = dimension_scores.get('structure', 0.0)
            confidence_factors.append(structure_score)
            
            # 分析质量因子
            if not analysis.encoding_issues:
                confidence_factors.append(0.9)
            else:
                confidence_factors.append(0.6)
            
            # 维度分数一致性
            scores = list(dimension_scores.values())
            if scores:
                score_variance = statistics.variance(scores) if len(scores) > 1 else 0
                consistency_factor = max(0.5, 1.0 - score_variance)
                confidence_factors.append(consistency_factor)
            
            return statistics.mean(confidence_factors) if confidence_factors else 0.5
            
        except Exception as e:
            logger.error(f"计算置信度失败: {str(e)}")
            return 0.5
    
    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        """计算内容哈希"""
        try:
            # 提取关键内容
            key_content = {
                'title': content.get('title', ''),
                'content': content.get('content', ''),
                'author': content.get('author', '')
            }
            
            content_str = json.dumps(key_content, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(content_str.encode('utf-8')).hexdigest()
            
        except Exception as e:
            logger.error(f"计算内容哈希失败: {str(e)}")
            return ""
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似性"""
        try:
            if not text1 or not text2:
                return 0.0
            
            # 使用序列匹配器计算相似性
            matcher = difflib.SequenceMatcher(None, text1.lower(), text2.lower())
            return matcher.ratio()
            
        except Exception as e:
            logger.error(f"计算文本相似性失败: {str(e)}")
            return 0.0
    
    def _get_cached_metrics(self, content_hash: str) -> Optional[QualityMetrics]:
        """获取缓存的质量指标"""
        try:
            with self.cache_lock:
                return self.content_cache.get(content_hash)
        except Exception as e:
            logger.error(f"获取缓存失败: {str(e)}")
            return None
    
    def _cache_metrics(self, content_hash: str, metrics: QualityMetrics):
        """缓存质量指标"""
        try:
            with self.cache_lock:
                # 限制缓存大小
                if len(self.content_cache) > 1000:
                    # 删除最旧的缓存
                    oldest_hash = next(iter(self.content_cache))
                    del self.content_cache[oldest_hash]
                
                self.content_cache[content_hash] = metrics
        except Exception as e:
            logger.error(f"缓存质量指标失败: {str(e)}")
    
    async def _update_statistics(self, platform: str, metrics: QualityMetrics):
        """更新统计信息"""
        try:
            with self.stats_lock:
                stats = self.platform_stats[platform]
                
                # 更新基础统计
                stats['total_assessments'] += 1
                
                # 更新平均质量
                current_avg = stats['average_quality']
                total_count = stats['total_assessments']
                stats['average_quality'] = (current_avg * (total_count - 1) + metrics.overall_score) / total_count
                
                # 更新质量分布
                stats['quality_distribution'][metrics.quality_level.value] += 1
                
                # 更新常见问题
                for issue in metrics.issues:
                    stats['common_issues'][issue] += 1
                
                # 更新质量趋势
                self.quality_trends.append({
                    'timestamp': metrics.timestamp,
                    'platform': platform,
                    'score': metrics.overall_score,
                    'level': metrics.quality_level.value
                })
                
        except Exception as e:
            logger.error(f"更新统计信息失败: {str(e)}")
    
    async def should_retry(
        self,
        metrics: QualityMetrics,
        retry_count: int = 0,
        strategy: RetryStrategy = None
    ) -> Tuple[bool, RetryReason, float]:
        """判断是否应该重试"""
        try:
            if strategy is None:
                strategy = self.config.default_retry_strategy
            
            # 检查重试次数
            if retry_count >= strategy.max_retries:
                return False, RetryReason.CUSTOM, 0.0
            
            # 检查质量阈值
            if metrics.overall_score < strategy.quality_threshold:
                delay = min(
                    strategy.base_delay * (strategy.backoff_factor ** retry_count),
                    strategy.max_delay
                )
                
                if strategy.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)
                
                return True, RetryReason.LOW_QUALITY, delay
            
            # 检查特定条件
            for condition in strategy.retry_conditions:
                should_retry_condition = await self._check_retry_condition(condition, metrics)
                if should_retry_condition:
                    delay = min(
                        strategy.base_delay * (strategy.backoff_factor ** retry_count),
                        strategy.max_delay
                    )
                    return True, condition, delay
            
            # 检查自定义条件
            for custom_condition in strategy.custom_conditions:
                try:
                    if custom_condition(metrics):
                        delay = strategy.base_delay
                        return True, RetryReason.CUSTOM, delay
                except Exception as e:
                    logger.error(f"自定义重试条件检查失败: {str(e)}")
            
            return False, RetryReason.CUSTOM, 0.0
            
        except Exception as e:
            logger.error(f"重试判断失败: {str(e)}")
            return False, RetryReason.CUSTOM, 0.0
    
    async def _check_retry_condition(self, condition: RetryReason, metrics: QualityMetrics) -> bool:
        """检查重试条件"""
        try:
            if condition == RetryReason.LOW_QUALITY:
                return metrics.overall_score < 0.5
            
            elif condition == RetryReason.INCOMPLETE_DATA:
                completeness_score = metrics.dimension_scores.get('completeness', 0.0)
                return completeness_score < 0.6
            
            elif condition == RetryReason.EXTRACTION_ERROR:
                return 'extraction_error' in [issue.lower() for issue in metrics.issues]
            
            elif condition == RetryReason.VALIDATION_FAILED:
                return 'validation' in [issue.lower() for issue in metrics.issues]
            
            return False
            
        except Exception as e:
            logger.error(f"检查重试条件失败: {str(e)}")
            return False
    
    def get_quality_statistics(self, platform: str = None) -> Dict[str, Any]:
        """获取质量统计信息"""
        try:
            with self.stats_lock:
                if platform:
                    return dict(self.platform_stats.get(platform, {}))
                else:
                    return {
                        'platforms': dict(self.platform_stats),
                        'total_assessments': sum(stats['total_assessments'] for stats in self.platform_stats.values()),
                        'overall_average_quality': statistics.mean(
                            [stats['average_quality'] for stats in self.platform_stats.values() if stats['average_quality'] > 0]
                        ) if self.platform_stats else 0.0,
                        'quality_trends': list(self.quality_trends)[-100:],  # 最近100条趋势
                        'cache_size': len(self.content_cache)
                    }
        except Exception as e:
            logger.error(f"获取质量统计失败: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            stats = self.get_quality_statistics()
            
            # 计算健康分数
            health_score = 1.0
            issues = []
            
            # 检查评估数量
            total_assessments = stats.get('total_assessments', 0)
            if total_assessments == 0:
                health_score *= 0.5
                issues.append("尚未进行质量评估")
            
            # 检查平均质量
            avg_quality = stats.get('overall_average_quality', 0.0)
            if avg_quality < 0.5:
                health_score *= 0.7
                issues.append(f"平均质量较低: {avg_quality:.2f}")
            
            # 检查缓存大小
            cache_size = stats.get('cache_size', 0)
            if cache_size > 800:
                health_score *= 0.9
                issues.append("缓存使用率较高")
            
            # 检查NLP工具
            if not JIEBA_AVAILABLE:
                health_score *= 0.8
                issues.append("NLP工具不可用")
            
            status = 'healthy'
            if health_score < 0.5:
                status = 'unhealthy'
            elif health_score < 0.8:
                status = 'degraded'
            
            return {
                'status': status,
                'health_score': health_score,
                'issues': issues,
                'stats': stats,
                'nlp_available': JIEBA_AVAILABLE,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# 全局质量评估器实例
_assessor = None

async def get_quality_assessor(config: QualityConfig = None) -> QualityAssessor:
    """获取质量评估器实例"""
    global _assessor
    
    if _assessor is None:
        if config is None:
            config = QualityConfig()
        
        _assessor = QualityAssessor(config)
        await _assessor.initialize()
    
    return _assessor

async def shutdown_assessor():
    """关闭质量评估器"""
    global _assessor
    
    if _assessor:
        _assessor = None