#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存储服务模块
提供 MinIO 文件存储功能
"""

import os
import logging
import asyncio
import aiohttp
import aiofiles
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from minio import Minio
from minio.error import S3Error
import tempfile
import hashlib
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

class StorageClient:
    """MinIO 存储客户端"""
    
    def __init__(self):
        self.minio_client = None
        self.bucket_name = os.getenv('MINIO_BUCKET_NAME', 'newshub-media')
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化 MinIO 客户端"""
        try:
            endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
            access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
            secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
            use_ssl = os.getenv('MINIO_USE_SSL', 'false').lower() == 'true'
            
            self.minio_client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=use_ssl
            )
            
            # 确保 bucket 存在
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(f"创建 MinIO bucket: {self.bucket_name}")
            
            logger.info(f"MinIO 客户端初始化成功: {endpoint}")
            
        except Exception as e:
            logger.error(f"MinIO 客户端初始化失败: {e}")
            self.minio_client = None
    
    def upload_media_files(self, images: List[str] = None, video_url: str = None) -> Dict[str, Any]:
        """上传媒体文件到 MinIO"""
        result = {
            'images': [],
            'video_url': None,
            'errors': []
        }
        
        if not self.minio_client:
            result['errors'].append("MinIO 客户端未初始化")
            return result
        
        try:
            # 处理图片
            if images:
                for i, image_url in enumerate(images):
                    try:
                        uploaded_url = self._upload_image(image_url, f"images/{datetime.now().strftime('%Y%m%d')}")
                        if uploaded_url:
                            result['images'].append(uploaded_url)
                        else:
                            result['errors'].append(f"图片上传失败: {image_url}")
                    except Exception as e:
                        logger.error(f"图片上传失败 {image_url}: {e}")
                        result['errors'].append(f"图片上传异常: {image_url} - {str(e)}")
            
            # 处理视频
            if video_url:
                try:
                    uploaded_url = self._upload_video(video_url, f"videos/{datetime.now().strftime('%Y%m%d')}")
                    result['video_url'] = uploaded_url
                except Exception as e:
                    logger.error(f"视频上传失败 {video_url}: {e}")
                    result['errors'].append(f"视频上传异常: {video_url} - {str(e)}")
            
            return result
            
        except Exception as e:
            logger.error(f"媒体文件上传失败: {e}")
            result['errors'].append(f"上传过程异常: {str(e)}")
            return result
    
    def _upload_image(self, image_url: str, folder: str) -> Optional[str]:
        """上传单个图片"""
        try:
            # 下载图片
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # 生成文件名
            file_extension = self._get_file_extension(image_url, response.headers.get('content-type', ''))
            file_name = f"{folder}/{hashlib.md5(image_url.encode()).hexdigest()}{file_extension}"
            
            # 上传到 MinIO
            self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_name,
                data=response.content,
                length=len(response.content),
                content_type=response.headers.get('content-type', 'image/jpeg')
            )
            
            # 返回访问 URL
            return f"http://{self.minio_client._endpoint_url.netloc}/{self.bucket_name}/{file_name}"
            
        except Exception as e:
            logger.error(f"图片上传失败 {image_url}: {e}")
            return None
    
    def _upload_video(self, video_url: str, folder: str) -> Optional[str]:
        """上传单个视频"""
        try:
            # 下载视频
            response = requests.get(video_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # 生成文件名
            file_extension = self._get_file_extension(video_url, response.headers.get('content-type', ''))
            file_name = f"{folder}/{hashlib.md5(video_url.encode()).hexdigest()}{file_extension}"
            
            # 上传到 MinIO
            self.minio_client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_name,
                data=response.raw,
                content_type=response.headers.get('content-type', 'video/mp4')
            )
            
            # 返回访问 URL
            return f"http://{self.minio_client._endpoint_url.netloc}/{self.bucket_name}/{file_name}"
            
        except Exception as e:
            logger.error(f"视频上传失败 {video_url}: {e}")
            return None
    
    def _get_file_extension(self, url: str, content_type: str) -> str:
        """获取文件扩展名"""
        # 从 URL 中提取扩展名
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        if '.jpg' in path or '.jpeg' in path or 'image/jpeg' in content_type:
            return '.jpg'
        elif '.png' in path or 'image/png' in content_type:
            return '.png'
        elif '.gif' in path or 'image/gif' in content_type:
            return '.gif'
        elif '.webp' in path or 'image/webp' in content_type:
            return '.webp'
        elif '.mp4' in path or 'video/mp4' in content_type:
            return '.mp4'
        elif '.avi' in path or 'video/avi' in content_type:
            return '.avi'
        elif '.mov' in path or 'video/quicktime' in content_type:
            return '.mov'
        else:
            return '.jpg'  # 默认扩展名

# 全局存储客户端实例
_storage_client = None

def get_storage_client() -> StorageClient:
    """获取存储客户端实例"""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client

def cleanup_storage_client():
    """清理存储客户端"""
    global _storage_client
    _storage_client = None
