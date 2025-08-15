#!/usr/bin/env python3
"""
数据库清理脚本 - 强制清理无效的浏览器实例记录
用于解决小红书平台实例限制问题中的僵尸实例
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from login_state.database import get_database
from login_state.models import BrowserInstance

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BrowserInstanceCleaner:
    """浏览器实例清理器"""
    
    def __init__(self):
        self.db = get_database()
        
    async def cleanup_zombie_instances(self, platform: str = None, dry_run: bool = True) -> Dict[str, Any]:
        """清理僵尸实例
        
        Args:
            platform: 指定平台，None表示所有平台
            dry_run: 是否为试运行模式
            
        Returns:
            清理结果统计
        """
        logger.info(f"开始清理僵尸实例 - 平台: {platform or '所有'}, 试运行: {dry_run}")
        
        # 构建查询条件
        query = {"is_active": True}
        if platform:
            query["platform"] = platform
            
        # 查找所有活跃实例
        active_instances = list(self.db.browser_instances.find(query))
        logger.info(f"找到 {len(active_instances)} 个活跃实例")
        
        stats = {
            "total_found": len(active_instances),
            "expired_instances": 0,
            "old_instances": 0,
            "cleaned_instances": 0,
            "errors": []
        }
        
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=2)  # 2小时前的实例视为可疑
        
        for instance in active_instances:
            try:
                instance_id = instance["instance_id"]
                created_at = instance.get("created_at")
                expires_at = instance.get("expires_at")
                last_activity = instance.get("last_activity")
                
                should_cleanup = False
                reason = ""
                
                # 检查是否已过期
                if expires_at and expires_at < current_time:
                    should_cleanup = True
                    reason = "已过期"
                    stats["expired_instances"] += 1
                    
                # 检查是否为长时间未活动的实例
                elif last_activity and last_activity < cutoff_time:
                    should_cleanup = True
                    reason = "长时间未活动"
                    stats["old_instances"] += 1
                    
                # 检查创建时间异常的实例
                elif not created_at or created_at < current_time - timedelta(days=1):
                    should_cleanup = True
                    reason = "创建时间异常"
                    stats["old_instances"] += 1
                
                if should_cleanup:
                    logger.info(f"标记清理实例 {instance_id}: {reason}")
                    
                    if not dry_run:
                        # 执行清理
                        result = self.db.browser_instances.update_one(
                            {"instance_id": instance_id},
                            {
                                "$set": {
                                    "is_active": False,
                                    "closed_at": current_time,
                                    "cleanup_reason": f"自动清理: {reason}"
                                }
                            }
                        )
                        
                        if result.modified_count > 0:
                            stats["cleaned_instances"] += 1
                            logger.info(f"成功清理实例 {instance_id}")
                        else:
                            error_msg = f"清理实例 {instance_id} 失败"
                            logger.error(error_msg)
                            stats["errors"].append(error_msg)
                    else:
                        stats["cleaned_instances"] += 1
                        
            except Exception as e:
                error_msg = f"处理实例 {instance.get('instance_id', 'unknown')} 时出错: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        logger.info(f"清理完成 - 统计: {stats}")
        return stats
    
    async def force_cleanup_platform(self, platform: str, max_instances: int = 3, dry_run: bool = True) -> Dict[str, Any]:
        """强制清理指定平台的实例，保留最新的几个
        
        Args:
            platform: 平台名称
            max_instances: 保留的最大实例数
            dry_run: 是否为试运行模式
            
        Returns:
            清理结果统计
        """
        logger.info(f"强制清理平台 {platform} 实例，保留最新 {max_instances} 个")
        
        # 查找平台的所有活跃实例，按最后活动时间排序
        active_instances = list(
            self.db.browser_instances.find(
                {"platform": platform, "is_active": True}
            ).sort("last_activity", -1)  # 降序，最新的在前
        )
        
        stats = {
            "total_found": len(active_instances),
            "to_keep": min(len(active_instances), max_instances),
            "to_cleanup": max(0, len(active_instances) - max_instances),
            "cleaned_instances": 0,
            "errors": []
        }
        
        # 如果实例数量超过限制，清理多余的
        if len(active_instances) > max_instances:
            instances_to_cleanup = active_instances[max_instances:]
            current_time = datetime.utcnow()
            
            for instance in instances_to_cleanup:
                try:
                    instance_id = instance["instance_id"]
                    logger.info(f"强制清理实例 {instance_id}")
                    
                    if not dry_run:
                        result = self.db.browser_instances.update_one(
                            {"instance_id": instance_id},
                            {
                                "$set": {
                                    "is_active": False,
                                    "closed_at": current_time,
                                    "cleanup_reason": "强制清理: 超出平台实例限制"
                                }
                            }
                        )
                        
                        if result.modified_count > 0:
                            stats["cleaned_instances"] += 1
                            logger.info(f"成功强制清理实例 {instance_id}")
                        else:
                            error_msg = f"强制清理实例 {instance_id} 失败"
                            logger.error(error_msg)
                            stats["errors"].append(error_msg)
                    else:
                        stats["cleaned_instances"] += 1
                        
                except Exception as e:
                    error_msg = f"强制清理实例 {instance.get('instance_id', 'unknown')} 时出错: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
        
        logger.info(f"强制清理完成 - 统计: {stats}")
        return stats
    
    async def get_instance_stats(self) -> Dict[str, Any]:
        """获取实例统计信息"""
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "platform": "$platform",
                        "is_active": "$is_active"
                    },
                    "count": {"$sum": 1}
                }
            }
        ]
        
        results = list(self.db.browser_instances.aggregate(pipeline))
        
        stats = {}
        for result in results:
            platform = result["_id"]["platform"]
            is_active = result["_id"]["is_active"]
            count = result["count"]
            
            if platform not in stats:
                stats[platform] = {"active": 0, "inactive": 0, "total": 0}
            
            if is_active:
                stats[platform]["active"] = count
            else:
                stats[platform]["inactive"] = count
            
            stats[platform]["total"] = stats[platform]["active"] + stats[platform]["inactive"]
        
        return stats

async def main():
    """主函数"""
    cleaner = BrowserInstanceCleaner()
    
    print("=== 浏览器实例清理工具 ===")
    print("1. 查看当前实例统计")
    print("2. 清理僵尸实例 (试运行)")
    print("3. 清理僵尸实例 (执行)")
    print("4. 强制清理小红书实例 (试运行)")
    print("5. 强制清理小红书实例 (执行)")
    print("6. 清理所有平台僵尸实例 (执行)")
    
    choice = input("请选择操作 (1-6): ").strip()
    
    if choice == "1":
        stats = await cleaner.get_instance_stats()
        print("\n=== 当前实例统计 ===")
        for platform, data in stats.items():
            print(f"{platform}: 活跃={data['active']}, 非活跃={data['inactive']}, 总计={data['total']}")
    
    elif choice == "2":
        result = await cleaner.cleanup_zombie_instances(dry_run=True)
        print(f"\n=== 试运行结果 ===")
        print(f"找到实例: {result['total_found']}")
        print(f"过期实例: {result['expired_instances']}")
        print(f"旧实例: {result['old_instances']}")
        print(f"将清理: {result['cleaned_instances']}")
        if result['errors']:
            print(f"错误: {len(result['errors'])}")
    
    elif choice == "3":
        result = await cleaner.cleanup_zombie_instances(dry_run=False)
        print(f"\n=== 执行结果 ===")
        print(f"找到实例: {result['total_found']}")
        print(f"已清理: {result['cleaned_instances']}")
        if result['errors']:
            print(f"错误: {len(result['errors'])}")
            for error in result['errors']:
                print(f"  - {error}")
    
    elif choice == "4":
        result = await cleaner.force_cleanup_platform("xiaohongshu", max_instances=3, dry_run=True)
        print(f"\n=== 小红书强制清理试运行结果 ===")
        print(f"找到实例: {result['total_found']}")
        print(f"保留实例: {result['to_keep']}")
        print(f"将清理: {result['to_cleanup']}")
    
    elif choice == "5":
        result = await cleaner.force_cleanup_platform("xiaohongshu", max_instances=3, dry_run=False)
        print(f"\n=== 小红书强制清理执行结果 ===")
        print(f"找到实例: {result['total_found']}")
        print(f"保留实例: {result['to_keep']}")
        print(f"已清理: {result['cleaned_instances']}")
        if result['errors']:
            print(f"错误: {len(result['errors'])}")
            for error in result['errors']:
                print(f"  - {error}")
    
    elif choice == "6":
        result = await cleaner.cleanup_zombie_instances(dry_run=False)
        print(f"\n=== 全平台清理执行结果 ===")
        print(f"找到实例: {result['total_found']}")
        print(f"已清理: {result['cleaned_instances']}")
        if result['errors']:
            print(f"错误: {len(result['errors'])}")
            for error in result['errors']:
                print(f"  - {error}")
    
    else:
        print("无效选择")

if __name__ == "__main__":
    asyncio.run(main())