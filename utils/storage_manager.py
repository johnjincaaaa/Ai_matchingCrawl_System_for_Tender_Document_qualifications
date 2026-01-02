"""
存储空间管理模块
用于自动清理旧文件、监控存储空间、管理文件生命周期
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from utils.log import log
from config import FILES_DIR, REPORT_DIR, LOG_DIR, BASE_DIR


class StorageManager:
    """存储空间管理器"""
    
    def __init__(self):
        self.files_dir = FILES_DIR
        self.report_dir = REPORT_DIR
        self.log_dir = LOG_DIR
        self.base_dir = BASE_DIR
    
    def get_directory_size(self, directory: str) -> int:
        """获取目录总大小（字节）"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        pass
        except Exception as e:
            log.error(f"计算目录大小失败 {directory}: {str(e)}")
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def get_storage_info(self) -> Dict:
        """获取存储空间信息"""
        info = {
            "files_dir": {
                "path": self.files_dir,
                "size": self.get_directory_size(self.files_dir),
                "file_count": self._count_files(self.files_dir)
            },
            "report_dir": {
                "path": self.report_dir,
                "size": self.get_directory_size(self.report_dir),
                "file_count": self._count_files(self.report_dir)
            },
            "log_dir": {
                "path": self.log_dir,
                "size": self.get_directory_size(self.log_dir),
                "file_count": self._count_files(self.log_dir)
            },
            "db_file": {
                "path": os.path.join(self.base_dir, "tender_system.db"),
                "size": os.path.getsize(os.path.join(self.base_dir, "tender_system.db")) if os.path.exists(os.path.join(self.base_dir, "tender_system.db")) else 0
            }
        }
        
        # 计算总大小
        total_size = sum([
            info["files_dir"]["size"],
            info["report_dir"]["size"],
            info["log_dir"]["size"],
            info["db_file"]["size"]
        ])
        
        info["total_size"] = total_size
        
        return info
    
    def _count_files(self, directory: str) -> int:
        """统计目录中的文件数量"""
        count = 0
        try:
            for root, dirs, files in os.walk(directory):
                count += len(files)
        except Exception as e:
            log.error(f"统计文件数量失败 {directory}: {str(e)}")
        return count
    
    def clean_old_files(self, days: int = 30, dry_run: bool = False) -> Dict:
        """
        清理指定天数之前的文件
        
        Args:
            days: 保留最近N天的文件
            dry_run: 是否为试运行（不实际删除）
        
        Returns:
            清理统计信息
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        stats = {
            "files_deleted": 0,
            "files_size_freed": 0,
            "files_skipped": 0,
            "errors": []
        }
        
        # 清理标书文件
        files_cleaned = self._clean_directory(
            self.files_dir, cutoff_date, dry_run
        )
        stats["files_deleted"] += files_cleaned["deleted"]
        stats["files_size_freed"] += files_cleaned["size_freed"]
        stats["files_skipped"] += files_cleaned["skipped"]
        stats["errors"].extend(files_cleaned["errors"])
        
        # 清理报告文件
        reports_cleaned = self._clean_directory(
            self.report_dir, cutoff_date, dry_run
        )
        stats["files_deleted"] += reports_cleaned["deleted"]
        stats["files_size_freed"] += reports_cleaned["size_freed"]
        stats["files_skipped"] += reports_cleaned["skipped"]
        stats["errors"].extend(reports_cleaned["errors"])
        
        return stats
    
    def _clean_directory(self, directory: str, cutoff_date: datetime, dry_run: bool) -> Dict:
        """清理目录中的旧文件"""
        stats = {
            "deleted": 0,
            "size_freed": 0,
            "skipped": 0,
            "errors": []
        }
        
        try:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        # 获取文件修改时间
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        if mtime < cutoff_date:
                            file_size = os.path.getsize(filepath)
                            
                            if not dry_run:
                                if os.path.isfile(filepath):
                                    os.remove(filepath)
                                    log.info(f"删除旧文件: {filepath} (修改时间: {mtime.strftime('%Y-%m-%d')})")
                                elif os.path.isdir(filepath):
                                    shutil.rmtree(filepath)
                                    log.info(f"删除旧目录: {filepath}")
                            
                            stats["deleted"] += 1
                            stats["size_freed"] += file_size
                        else:
                            stats["skipped"] += 1
                    except Exception as e:
                        error_msg = f"处理文件失败 {filepath}: {str(e)}"
                        stats["errors"].append(error_msg)
                        log.error(error_msg)
        except Exception as e:
            error_msg = f"清理目录失败 {directory}: {str(e)}"
            stats["errors"].append(error_msg)
            log.error(error_msg)
        
        return stats
    
    def clean_empty_directories(self, directory: str) -> int:
        """清理空目录"""
        deleted_count = 0
        try:
            for root, dirs, files in os.walk(directory, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # 目录为空
                            os.rmdir(dir_path)
                            deleted_count += 1
                            log.info(f"删除空目录: {dir_path}")
                    except Exception as e:
                        log.warning(f"删除空目录失败 {dir_path}: {str(e)}")
        except Exception as e:
            log.error(f"清理空目录失败 {directory}: {str(e)}")
        return deleted_count
    
    def clean_by_status(self, status_list: List[str], dry_run: bool = False) -> Dict:
        """
        根据项目状态清理文件
        
        Args:
            status_list: 要清理的项目状态列表（如：["已比对", "异常"]）
            dry_run: 是否为试运行
        
        Returns:
            清理统计信息
        """
        from utils.db import get_db, TenderProject, ProjectStatus
        
        stats = {
            "files_deleted": 0,
            "files_size_freed": 0,
            "projects_processed": 0,
            "errors": []
        }
        
        try:
            db = next(get_db())
            
            # 查询指定状态的项目
            projects = db.query(TenderProject).filter(
                TenderProject.status.in_([ProjectStatus[s] for s in status_list])
            ).all()
            
            stats["projects_processed"] = len(projects)
            
            for project in projects:
                if project.file_path:
                    file_path = project.file_path
                    
                    # 处理相对路径
                    if not os.path.isabs(file_path):
                        file_path = os.path.join(self.files_dir, file_path)
                    
                    if os.path.exists(file_path):
                        try:
                            file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else self.get_directory_size(file_path)
                            
                            if not dry_run:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                elif os.path.isdir(file_path):
                                    shutil.rmtree(file_path)
                                
                                log.info(f"删除项目文件: {file_path} (项目ID: {project.id})")
                            
                            stats["files_deleted"] += 1
                            stats["files_size_freed"] += file_size
                        except Exception as e:
                            error_msg = f"删除项目文件失败 {file_path}: {str(e)}"
                            stats["errors"].append(error_msg)
                            log.error(error_msg)
            
            db.close()
        except Exception as e:
            error_msg = f"根据状态清理文件失败: {str(e)}"
            stats["errors"].append(error_msg)
            log.error(error_msg)
        
        return stats
    
    def get_disk_usage(self) -> Dict:
        """获取磁盘使用情况"""
        import shutil
        
        try:
            total, used, free = shutil.disk_usage(self.base_dir)
            return {
                "total": total,
                "used": used,
                "free": free,
                "percent_used": (used / total) * 100 if total > 0 else 0
            }
        except Exception as e:
            log.error(f"获取磁盘使用情况失败: {str(e)}")
            return {
                "total": 0,
                "used": 0,
                "free": 0,
                "percent_used": 0
            }
    
    def check_storage_threshold(self, threshold_percent: float = 80.0) -> Tuple[bool, Dict]:
        """
        检查存储空间是否超过阈值
        
        Args:
            threshold_percent: 警告阈值（百分比）
        
        Returns:
            (是否超过阈值, 详细信息)
        """
        disk_usage = self.get_disk_usage()
        storage_info = self.get_storage_info()
        
        is_over_threshold = disk_usage["percent_used"] >= threshold_percent
        
        return is_over_threshold, {
            "disk_usage": disk_usage,
            "storage_info": storage_info,
            "threshold": threshold_percent
        }


def auto_cleanup_old_files(days: int = 30):
    """自动清理旧文件的便捷函数"""
    manager = StorageManager()
    stats = manager.clean_old_files(days=days, dry_run=False)
    
    log.info("=" * 60)
    log.info("自动清理旧文件完成")
    log.info(f"删除文件数: {stats['files_deleted']}")
    log.info(f"释放空间: {manager.format_size(stats['files_size_freed'])}")
    log.info(f"跳过文件数: {stats['files_skipped']}")
    if stats['errors']:
        log.warning(f"错误数: {len(stats['errors'])}")
    log.info("=" * 60)
    
    return stats

