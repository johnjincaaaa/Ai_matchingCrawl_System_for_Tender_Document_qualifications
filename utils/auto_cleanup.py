#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动清理脚本
用于定期清理旧文件，释放存储空间
可以设置为Windows计划任务定期执行
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.storage_manager import StorageManager, auto_cleanup_old_files
from utils.log import log
from config import STORAGE_CONFIG


def main():
    """主函数"""
    log.info("=" * 60)
    log.info("开始执行自动清理任务")
    log.info("=" * 60)
    
    try:
        storage_manager = StorageManager()
        
        # 检查存储空间
        is_over_threshold, info = storage_manager.check_storage_threshold(
            threshold_percent=STORAGE_CONFIG.get("disk_warning_threshold", 80.0)
        )
        
        log.info(f"磁盘使用率: {info['disk_usage']['percent_used']:.1f}%")
        log.info(f"总容量: {storage_manager.format_size(info['disk_usage']['total'])}")
        log.info(f"已使用: {storage_manager.format_size(info['disk_usage']['used'])}")
        log.info(f"可用空间: {storage_manager.format_size(info['disk_usage']['free'])}")
        
        if is_over_threshold:
            log.warning(f"⚠️ 磁盘使用率超过阈值（{STORAGE_CONFIG.get('disk_warning_threshold', 80.0)}%），开始清理...")
        else:
            log.info("磁盘使用率正常，执行常规清理...")
        
        # 执行自动清理
        cleanup_days = STORAGE_CONFIG.get("cleanup_interval_days", 30)
        log.info(f"清理策略：保留最近 {cleanup_days} 天的文件")
        
        stats = auto_cleanup_old_files(days=cleanup_days)
        
        # 清理空目录
        log.info("清理空目录...")
        empty_dirs_deleted = 0
        empty_dirs_deleted += storage_manager.clean_empty_directories(storage_manager.files_dir)
        empty_dirs_deleted += storage_manager.clean_empty_directories(storage_manager.report_dir)
        log.info(f"删除了 {empty_dirs_deleted} 个空目录")
        
        # 再次检查存储空间
        disk_usage_after = storage_manager.get_disk_usage()
        log.info("=" * 60)
        log.info("清理完成后的存储情况：")
        log.info(f"磁盘使用率: {disk_usage_after['percent_used']:.1f}%")
        log.info(f"可用空间: {storage_manager.format_size(disk_usage_after['free'])}")
        log.info("=" * 60)
        
        log.info("✅ 自动清理任务执行完成")
        return 0
        
    except Exception as e:
        log.error(f"❌ 自动清理任务执行失败：{str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

