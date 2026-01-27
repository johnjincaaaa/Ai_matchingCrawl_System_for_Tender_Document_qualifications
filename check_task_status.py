#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查任务状态诊断脚本
用于检查后台任务是否卡住
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_DIR

def check_log_status():
    """检查日志文件状态"""
    log_file = os.path.join(LOG_DIR, "tender_system.log")
    
    if not os.path.exists(log_file):
        print("❌ 日志文件不存在")
        return
    
    # 获取文件最后修改时间
    file_mtime = os.path.getmtime(log_file)
    file_mtime_dt = datetime.fromtimestamp(file_mtime)
    now = datetime.now()
    time_diff = now - file_mtime_dt
    
    print(f"日志文件状态：")
    print(f"   - 文件路径：{log_file}")
    print(f"   - 最后修改时间：{file_mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   - 距离现在：{int(time_diff.total_seconds())} 秒（{int(time_diff.total_seconds() / 60)} 分钟）")
    
    # 读取最后20行日志
    print(f"\n最后20条日志：")
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            last_lines = lines[-20:] if len(lines) > 20 else lines
            for line in last_lines:
                print(f"   {line.strip()}")
    except Exception as e:
        print(f"   ❌ 读取日志失败：{str(e)}")
    
    # 检查是否有AI分析相关的日志
    print(f"\nAI分析相关日志（最近10条）：")
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            ai_logs = [line for line in lines if 'qualification_analyzer' in line or 'AI分析' in line or 'extract_requirements' in line or 'compare_qualifications' in line]
            last_ai_logs = ai_logs[-10:] if len(ai_logs) > 10 else ai_logs
            for line in last_ai_logs:
                print(f"   {line.strip()}")
    except Exception as e:
        print(f"   ❌ 读取AI分析日志失败：{str(e)}")

def check_database_status():
    """检查数据库中的项目状态"""
    try:
        from utils.db import get_db, TenderProject, ProjectStatus
        
        db = next(get_db())
        try:
            # 统计各状态的项目数量
            stats = {}
            for status in ProjectStatus:
                count = db.query(TenderProject).filter(TenderProject.status == status).count()
                stats[status.value] = count
            
            print(f"\n数据库项目状态统计：")
            for status, count in stats.items():
                print(f"   - {status}：{count} 个")
            
            # 检查最近更新的项目
            print(f"\n最近更新的项目（最后5个）：")
            recent_projects = db.query(TenderProject).order_by(TenderProject.update_time.desc()).limit(5).all()
            for project in recent_projects:
                update_time = project.update_time.strftime('%Y-%m-%d %H:%M:%S') if project.update_time else "未知"
                print(f"   - ID={project.id}, 状态={project.status.value if project.status else '未知'}, 更新时间={update_time}, 名称={project.project_name[:50]}")
            
            # 检查是否有正在分析的项目（状态为PARSED但未完成）
            parsed_projects = db.query(TenderProject).filter(TenderProject.status == ProjectStatus.PARSED).count()
            print(f"\n待分析项目（PARSED状态）：{parsed_projects} 个")
            
        finally:
            db.close()
    except Exception as e:
        print(f"   ❌ 检查数据库状态失败：{str(e)}")

if __name__ == "__main__":
    import sys
    import io
    # 设置输出编码为UTF-8
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("任务状态诊断")
    print("=" * 60)
    
    check_log_status()
    check_database_status()
    
    print("\n" + "=" * 60)
    print("建议：")
    print("   1. 如果日志超过5分钟未更新，可能是AI分析卡住了")
    print("   2. 检查Ollama服务是否正常运行：curl http://localhost:11434/api/tags")
    print("   3. 如果某个项目一直卡住，可以在流程执行页面点击'终止'按钮")
    print("=" * 60)

