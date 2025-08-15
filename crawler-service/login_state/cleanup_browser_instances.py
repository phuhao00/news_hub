#!/usr/bin/env python3
"""
数据库清理脚本 - 清理无效的浏览器实例记录
用于解决小红书等平台的浏览器实例限制问题
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import sys

# 数据库配置
MONGODB_URL = "mongodb://localhost:27017"
DATABASE_NAME = "crawler_service"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrowserInstanceCleaner:
    def __init__(self, mongodb_url: str, database_name: str):
        self.mongodb_url = mongodb_url
        self.database_name = database_name
        self.client = None
        self.db = None
    
    async def connect(self):
        """连接到MongoDB数据库"""
        try:
            self.client = AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client[self.database_name]
            # 测试连接
            await self.client.admin.command('ping')
            logger.info(f"成功连接到数据库: {self.database_name}")
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    async def disconnect(self):
        """断开数据库连接"""
        if self.client:
            self.client.close()
            logger.info("数据库连接已关闭")
    
    async def get_instance_stats(self, platform: str = None):
        """获取实例统计信息"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$platform",
                        "total_instances": {"$sum": 1},
                        "active_instances": {
                            "$sum": {
                                "$cond": [
                                    {"$and": [
                                        {"$eq": ["$is_active", True]},
                                        {"$gt": ["$expires_at", datetime.utcnow()]}
                                    ]},
                                    1, 0
                                ]
                            }
                        },
                        "expired_instances": {
                            "$sum": {
                                "$cond": [
                                    {"$lt": ["$expires_at", datetime.utcnow()]},
                                    1, 0
                                ]
                            }
                        },
                        "inactive_instances": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$is_active", False]},
                                    1, 0
                                ]
                            }
                        }
                    }
                }
            ]
            
            if platform:
                pipeline.insert(0, {"$match": {"platform": platform}})
            
            stats = await self.db.browser_instances.aggregate(pipeline).to_list(None)
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return []
    
    async def cleanup_expired_instances(self, platform: str = None, dry_run: bool = True):
        """清理过期的实例"""
        try:
            query = {"expires_at": {"$lt": datetime.utcnow()}}
            if platform:
                query["platform"] = platform
            
            if dry_run:
                count = await self.db.browser_instances.count_documents(query)
                logger.info(f"[DRY RUN] 将清理 {count} 个过期实例")
                return count
            else:
                result = await self.db.browser_instances.delete_many(query)
                logger.info(f"已清理 {result.deleted_count} 个过期实例")
                return result.deleted_count
        except Exception as e:
            logger.error(f"清理过期实例失败: {e}")
            return 0
    
    async def cleanup_old_inactive_instances(self, platform: str = None, days_old: int = 7, dry_run: bool = True):
        """清理旧的非活跃实例"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            query = {
                "is_active": False,
                "created_at": {"$lt": cutoff_date}
            }
            if platform:
                query["platform"] = platform
            
            if dry_run:
                count = await self.db.browser_instances.count_documents(query)
                logger.info(f"[DRY RUN] 将清理 {count} 个超过{days_old}天的非活跃实例")
                return count
            else:
                result = await self.db.browser_instances.delete_many(query)
                logger.info(f"已清理 {result.deleted_count} 个超过{days_old}天的非活跃实例")
                return result.deleted_count
        except Exception as e:
            logger.error(f"清理旧的非活跃实例失败: {e}")
            return 0
    
    async def cleanup_abnormal_active_instances(self, platform: str = None, hours_old: int = 6, dry_run: bool = True):
        """清理异常的活跃实例（长时间无活动但仍标记为活跃）"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours_old)
            query = {
                "is_active": True,
                "last_activity": {"$lt": cutoff_date}
            }
            if platform:
                query["platform"] = platform
            
            if dry_run:
                count = await self.db.browser_instances.count_documents(query)
                logger.info(f"[DRY RUN] 将清理 {count} 个超过{hours_old}小时无活动的异常活跃实例")
                return count
            else:
                # 将这些实例标记为非活跃而不是删除
                result = await self.db.browser_instances.update_many(
                    query,
                    {
                        "$set": {
                            "is_active": False,
                            "closed_at": datetime.utcnow(),
                            "cleanup_reason": "abnormal_active_cleanup"
                        }
                    }
                )
                logger.info(f"已标记 {result.modified_count} 个异常活跃实例为非活跃")
                return result.modified_count
        except Exception as e:
            logger.error(f"清理异常活跃实例失败: {e}")
            return 0
    
    async def force_cleanup_platform_instances(self, platform: str, keep_newest: int = 2, dry_run: bool = True):
        """强制清理指定平台的实例，保留最新的几个"""
        try:
            # 获取所有活跃实例，按最后活动时间排序
            query = {
                "platform": platform,
                "is_active": True
            }
            
            instances = await self.db.browser_instances.find(query).sort("last_activity", -1).to_list(None)
            
            if len(instances) <= keep_newest:
                logger.info(f"平台 {platform} 只有 {len(instances)} 个活跃实例，无需清理")
                return 0
            
            # 保留最新的实例，清理其余的
            instances_to_cleanup = instances[keep_newest:]
            instance_ids = [instance["_id"] for instance in instances_to_cleanup]
            
            if dry_run:
                logger.info(f"[DRY RUN] 将强制清理平台 {platform} 的 {len(instance_ids)} 个实例，保留最新的 {keep_newest} 个")
                for instance in instances_to_cleanup:
                    logger.info(f"  - 实例 {instance['instance_id']} (会话: {instance['session_id']}, 最后活动: {instance.get('last_activity', 'N/A')})")
                return len(instance_ids)
            else:
                result = await self.db.browser_instances.update_many(
                    {"_id": {"$in": instance_ids}},
                    {
                        "$set": {
                            "is_active": False,
                            "closed_at": datetime.utcnow(),
                            "cleanup_reason": "force_platform_cleanup"
                        }
                    }
                )
                logger.info(f"已强制清理平台 {platform} 的 {result.modified_count} 个实例")
                return result.modified_count
        except Exception as e:
            logger.error(f"强制清理平台实例失败: {e}")
            return 0
    
    async def print_detailed_stats(self, platform: str = None):
        """打印详细的统计信息"""
        try:
            stats = await self.get_instance_stats(platform)
            
            if not stats:
                logger.info("没有找到实例数据")
                return
            
            logger.info("=== 浏览器实例统计 ===")
            for stat in stats:
                platform_name = stat["_id"] or "未知平台"
                logger.info(f"平台: {platform_name}")
                logger.info(f"  总实例数: {stat['total_instances']}")
                logger.info(f"  活跃实例: {stat['active_instances']}")
                logger.info(f"  过期实例: {stat['expired_instances']}")
                logger.info(f"  非活跃实例: {stat['inactive_instances']}")
                logger.info("")
        except Exception as e:
            logger.error(f"打印统计信息失败: {e}")

async def main():
    parser = argparse.ArgumentParser(description='清理浏览器实例数据库记录')
    parser.add_argument('--platform', type=str, help='指定平台 (weibo, xiaohongshu, douyin)')
    parser.add_argument('--dry-run', action='store_true', default=True, help='仅显示将要执行的操作，不实际执行')
    parser.add_argument('--execute', action='store_true', help='实际执行清理操作')
    parser.add_argument('--force-cleanup', action='store_true', help='强制清理指定平台的实例')
    parser.add_argument('--keep', type=int, default=2, help='强制清理时保留的最新实例数量')
    parser.add_argument('--stats-only', action='store_true', help='仅显示统计信息')
    
    args = parser.parse_args()
    
    # 如果指定了execute，则关闭dry_run
    if args.execute:
        args.dry_run = False
    
    cleaner = BrowserInstanceCleaner(MONGODB_URL, DATABASE_NAME)
    
    try:
        await cleaner.connect()
        
        # 显示统计信息
        await cleaner.print_detailed_stats(args.platform)
        
        if args.stats_only:
            return
        
        if args.force_cleanup and args.platform:
            # 强制清理指定平台
            await cleaner.force_cleanup_platform_instances(
                args.platform, 
                keep_newest=args.keep, 
                dry_run=args.dry_run
            )
        else:
            # 常规清理
            logger.info("开始清理操作...")
            
            # 清理过期实例
            await cleaner.cleanup_expired_instances(args.platform, args.dry_run)
            
            # 清理旧的非活跃实例
            await cleaner.cleanup_old_inactive_instances(args.platform, days_old=7, dry_run=args.dry_run)
            
            # 清理异常活跃实例
            await cleaner.cleanup_abnormal_active_instances(args.platform, hours_old=6, dry_run=args.dry_run)
        
        # 显示清理后的统计信息
        if not args.dry_run:
            logger.info("清理完成，更新后的统计信息:")
            await cleaner.print_detailed_stats(args.platform)
        
    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}")
        return 1
    finally:
        await cleaner.disconnect()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)