import os
import logging
from minio import Minio
from minio.error import S3Error
from typing import Optional

logger = logging.getLogger(__name__)

class StorageClient:
    """MinIO存储客户端"""
    
    def __init__(self, endpoint: str = None, access_key: str = None, secret_key: str = None, secure: bool = False):
        self.endpoint = endpoint or os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.access_key = access_key or os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        self.secret_key = secret_key or os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
        self.secure = secure
        self.bucket_name = os.getenv('MINIO_BUCKET_NAME', 'newshub')
        
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            logger.info(f"MinIO客户端初始化成功: {self.endpoint}")
        except Exception as e:
            logger.error(f"MinIO客户端初始化失败: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if not self.client:
            return False
        try:
            # 尝试列出存储桶来测试连接
            list(self.client.list_buckets())
            return True
        except Exception as e:
            logger.error(f"MinIO连接测试失败: {e}")
            return False
    
    def ensure_bucket_exists(self) -> bool:
        """确保存储桶存在"""
        if not self.client:
            return False
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建存储桶: {self.bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"存储桶操作失败: {e}")
            return False
    
    def upload_file(self, file_path: str, object_name: str) -> bool:
        """上传文件"""
        if not self.client:
            return False
        try:
            self.ensure_bucket_exists()
            self.client.fput_object(self.bucket_name, object_name, file_path)
            logger.info(f"文件上传成功: {object_name}")
            return True
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            return False
    
    def get_file_url(self, object_name: str) -> Optional[str]:
        """获取文件访问URL"""
        if not self.client:
            return None
        try:
            protocol = 'https' if self.secure else 'http'
            return f"{protocol}://{self.endpoint}/{self.bucket_name}/{object_name}"
        except Exception as e:
            logger.error(f"获取文件URL失败: {e}")
            return None

# 全局存储客户端实例
_storage_client = None

def get_storage_client() -> StorageClient:
    """获取存储客户端实例"""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client

def init_storage_client(endpoint: str = None, access_key: str = None, secret_key: str = None, secure: bool = False) -> StorageClient:
    """初始化存储客户端"""
    global _storage_client
    _storage_client = StorageClient(endpoint, access_key, secret_key, secure)
    return _storage_client