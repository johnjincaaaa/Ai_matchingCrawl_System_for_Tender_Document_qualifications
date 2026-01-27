#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的项目数据
"""

import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.db import Base, TenderProject

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_database():
    """检查数据库中的项目数据"""
    try:
        # 数据库连接配置
        DATABASE_URL = "sqlite:///tender_system.db"
        engine = create_engine(DATABASE_URL, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # 创建数据库表（如果不存在）
        Base.metadata.create_all(bind=engine)
        
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 查询所有项目
            projects = db.query(TenderProject).all()
            
            print(f"共有 {len(projects)} 个项目")
            print("=" * 100)
            
            # 统计fileServiceId包含old的项目
            old_count = 0
            new_count = 0
            
            for project in projects:
                # 检查file_path字段
                if project.file_path:
                    if "old" in project.file_path.lower():
                        old_count += 1
                    else:
                        new_count += 1
            
            print(f"file_path包含'old'的项目: {old_count}")
            print(f"file_path不包含'old'的项目: {new_count}")
            
            # 检查项目名称
            for project in projects:
                print(f"项目ID: {project.id}")
                print(f"项目名称: {project.project_name}")
                print(f"发布时间: {project.publish_time}")
                print(f"下载URL: {project.download_url}")
                if project.file_path:
                    print(f"文件路径: {project.file_path}")
                print("-" * 50)
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"检查数据库失败: {str(e)}")

if __name__ == "__main__":
    check_database()
