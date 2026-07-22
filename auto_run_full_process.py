#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动运行全流程脚本（命令行版本，不依赖Streamlit）
自动执行爬虫、解析、AI分析、生成报告等全流程
"""

import sys
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用项目统一的日志配置
from utils.log import log as logger
from loguru import logger as loguru_logger

# 创建专门的自动运行日志文件
auto_run_log_file = f'logs/auto_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
loguru_logger.add(
    sink=auto_run_log_file,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
logger.info(f"📝 自动运行日志文件: {auto_run_log_file}")

# 导入项目模块
try:
    import config
    from config import SPIDER_CONFIG, TEST_CONFIG
    from spider import SpiderManager
    from parser.file_parser import FileParser
    from ai.qualification_analyzer import AIAnalyzer
    from report.report_generator import ReportGenerator
    from utils.db import get_db, save_project, ProjectStatus
    from datetime import datetime
    logger.info("✅ 成功导入项目模块")
except Exception as e:
    logger.error(f"❌ 导入项目模块失败: {str(e)}", exc_info=True)
    sys.exit(1)


# 单项目分析worker抽到 ai/analysis_worker.py，与 app.py 共享，避免逻辑重复
from ai.analysis_worker import analyze_one_project as _analyze_one_project


def run_full_process_cli(daily_limit=None, days_before=None, model_type=None, enabled_platforms=None):
    """
    命令行版本的全流程执行函数（不依赖Streamlit）
    
    Args:
        daily_limit: 每日爬取限制，None时使用config中的默认值
        days_before: 时间间隔，爬取指定天数之前的文件（None或0表示只爬取当日文件）
        model_type: AI模型类型（'local' 或 'cloud'），None时使用config中的默认值
    
    Returns:
        bool: 是否成功完成
    """
    try:
        # 1. 爬虫阶段
        logger.info("=" * 60)
        logger.info("📥 第一步：开始爬取项目")
        logger.info("=" * 60)
        
        if TEST_CONFIG.get("enable_test_mode", False):
            # 测试模式：使用本地文件
            logger.info("⚠️ 启用测试模式，跳过爬虫，使用本地测试文件")
            db = next(get_db())
            all_projects = []
            
            for file_path in TEST_CONFIG.get("test_files", []):
                if not os.path.exists(file_path):
                    logger.warning(f"测试文件不存在：{file_path}，跳过")
                    continue
                
                file_name = os.path.basename(file_path)
                project_name = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
                file_format = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "未知"
                
                project_data = {
                    "project_name": project_name,
                    "site_name": "本地测试文件",
                    "publish_time": datetime.now(),
                    "download_url": f"local_file://{file_path}",
                    "file_path": file_path,
                    "file_format": file_format,
                    "status": ProjectStatus.DOWNLOADED
                }
                
                try:
                    saved_project = save_project(db, project_data)
                    all_projects.append(saved_project)
                    logger.info(f"✅ 已添加本地测试项目：{project_name}")
                except Exception as e:
                    logger.error(f"❌ 添加测试项目失败：{project_name}，错误：{str(e)}")
            
            db.close()
            logger.info(f"📊 测试项目加载完成，共 {len(all_projects)} 个项目")
            
            if len(all_projects) == 0:
                logger.warning("⚠️ 未找到有效测试文件，任务终止")
                return False
        else:
            # 正常模式：执行爬虫
            try:
                all_projects = SpiderManager.run_all_spiders(
                    days_before=days_before, 
                    enabled_platforms=enabled_platforms,
                    total_limit=daily_limit
                )
                logger.info(f"✅ 爬虫完成，共获取 {len(all_projects)} 个项目")
            except Exception as e:
                logger.error(f"❌ 爬虫执行失败：{str(e)}", exc_info=True)
                raise
            
            if len(all_projects) == 0:
                logger.warning("⚠️ 未爬取到有效项目，跳过后续步骤")
                return False
        
        # 2. 文件解析和AI分析阶段（循环执行，直到所有项目处理完成或达到最大重试次数）
        max_rounds = 3  # 最多执行3轮（每轮包括解析和分析）
        current_round = 0
        
        while current_round < max_rounds:
            current_round += 1
            logger.info("=" * 60)
            logger.info(f"📄 第 {current_round} 轮：开始解析项目文件")
            logger.info("=" * 60)
            
            # 2.1 文件解析阶段
            try:
                parser = FileParser()
                parser.run()  # 解析所有状态为 DOWNLOADED 或 ERROR 的项目
                logger.info("✅ 文件解析完成")
            except KeyboardInterrupt:
                logger.warning("⚠️ 文件解析被用户中断")
                raise  # 重新抛出，让上层处理
            except Exception as parse_error:
                logger.error(f"❌ 文件解析阶段发生错误：{str(parse_error)}", exc_info=True)
                logger.warning("⚠️ 文件解析阶段出错，但将继续执行后续步骤（AI分析）")
                # 不抛出异常，允许继续执行AI分析步骤
            
            # 2.2 AI分析阶段
            logger.info("=" * 60)
            logger.info(f"🤖 第 {current_round} 轮：开始AI资质分析与比对")
            logger.info("=" * 60)
            
            try:
                # 使用与流程控制相同的分析流程
                from utils.db import get_db, TenderProject, ProjectStatus, update_project
                analyzer = AIAnalyzer(model_type=model_type)
                
                db = next(get_db())
                try:
                    # 查询待分析的项目（包括刚解析完成的项目和重置为PARSED状态的项目）
                    projects = db.query(TenderProject).filter(
                        TenderProject.status == ProjectStatus.PARSED
                    ).all()
                    
                    logger.info(f"待分析项目数：{len(projects)}")
                    
                    if len(projects) == 0:
                        logger.info("✅ 没有待分析的项目，所有项目已处理完成")
                        break  # 没有待处理项目，退出循环
                    
                    # 收集待处理项目ID（不跨线程共享ORM对象/Session）
                    project_infos = [(p.id, p.project_name) for p in projects]

                    success_count = 0
                    error_count = 0
                    excluded_count = 0

                    # 并发线程数（I/O密集：等待DashScope返回，用多线程并发提速）
                    try:
                        max_workers = config.AI_CONFIG.get("analysis_concurrency", {}).get("max_workers", 4)
                    except Exception:
                        max_workers = 4
                    max_workers = max(1, min(int(max_workers), len(project_infos)))
                    logger.info(f"🧵 使用 {max_workers} 个线程并发分析 {len(project_infos)} 个项目")

                    # 每个worker内部自建DB session；analyzer实例可安全共享
                    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai-analyze") as executor:
                        future_to_info = {
                            executor.submit(_analyze_one_project, analyzer, pid, pname): (pid, pname)
                            for pid, pname in project_infos
                        }
                        for future in as_completed(future_to_info):
                            pid, pname = future_to_info[future]
                            try:
                                status, _pid, _pname, detail = future.result()
                            except Exception as e:
                                error_count += 1
                                logger.error(f"❌ 项目分析线程异常：ID={pid}，错误：{str(e)[:300]}")
                                continue
                            if status == "success":
                                success_count += 1
                            elif status == "excluded":
                                excluded_count += 1
                            elif status == "empty":
                                error_count += 1
                            else:  # failed
                                error_count += 1

                    logger.info(f"✅ 第 {current_round} 轮并发分析结束（成功：{success_count}，排除：{excluded_count}，失败/空：{error_count}）")

                    # 检查是否还有待处理的项目（DOWNLOADED或PARSED状态）
                    remaining_downloaded = db.query(TenderProject).filter(
                        TenderProject.status == ProjectStatus.DOWNLOADED
                    ).count()
                    remaining_parsed = db.query(TenderProject).filter(
                        TenderProject.status == ProjectStatus.PARSED
                    ).count()
                    
                    if remaining_downloaded == 0 and remaining_parsed == 0:
                        logger.info("✅ 所有项目已处理完成，退出循环")
                        break  # 没有待处理项目，退出循环
                    else:
                        logger.info(f"📊 还有 {remaining_downloaded} 个待解析项目和 {remaining_parsed} 个待分析项目，继续下一轮")
                        
                finally:
                    db.close()
            except KeyboardInterrupt:
                logger.warning("⚠️ AI分析被用户中断")
                raise  # 重新抛出，让上层处理
            except Exception as ai_error:
                logger.error(f"❌ AI分析阶段发生严重错误：{str(ai_error)}", exc_info=True)
                # 继续下一轮，不中断整个流程
                continue
        
        logger.info("=" * 60)
        logger.info(f"✅ 文件解析和AI分析完成（共执行 {current_round} 轮）")
        logger.info("=" * 60)
        
        # 4. 生成报告阶段（添加异常处理，确保报告生成失败不会导致整个任务失败）
        logger.info("=" * 60)
        logger.info("📊 第四步：开始生成每日报告")
        logger.info("=" * 60)
        
        try:
            generator = ReportGenerator()
            report_path = generator.generate_report()
            logger.info(f"✅ 报告生成完成：{report_path}")
        except Exception as report_error:
            logger.error(f"❌ 报告生成失败：{str(report_error)}", exc_info=True)
            logger.warning("⚠️ 报告生成失败，但不影响任务完成状态")
        
        logger.info("=" * 60)
        logger.info("🎉 全流程执行完成！")
        logger.info("=" * 60)
        return True
        
    except KeyboardInterrupt:
        logger.warning("⚠️ 全流程被用户中断")
        return False
    except Exception as e:
        logger.error(f"❌ 全流程执行失败：{str(e)}", exc_info=True)
        return False


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='自动运行标书资质匹配全流程')
    parser.add_argument('--daily-limit', type=int, default=None, 
                       help='每日爬取数量限制（默认使用config中的配置，测试模式时自动设为2）')
    parser.add_argument('--days-before', type=int, default=0,
                       help='时间间隔，爬取指定天数之前的文件（0表示只爬取当日文件，7表示爬取7天前及更早的文件）')
    parser.add_argument('--model-type', type=str, default=None,
                       choices=['local', 'cloud'],
                       help='AI模型类型（local或cloud），默认使用config中的配置')
    parser.add_argument('--enabled-platforms', type=str, default=None,
                       help='启用的平台列表，逗号分隔（例如：ningbo,hangzhou），默认爬取所有平台')
    parser.add_argument('--test-mode', action='store_true',
                       help='测试模式：只爬取2个文件')
    
    args = parser.parse_args()
    
    logger.info("🚀 开始自动运行全流程（命令行版本）")
    
    # 测试模式：自动设置爬取数量为2
    if args.test_mode:
        args.daily_limit = 2
        logger.info("⚠️ 测试模式：限制爬取数量为2个文件")
    
    if args.daily_limit:
        logger.info(f"📊 爬取数量限制：{args.daily_limit}")
    else:
        logger.info(f"📊 爬取数量限制：使用config中的默认配置")
    if args.days_before and args.days_before > 0:
        logger.info(f"📅 时间间隔：爬取 {args.days_before} 天前及更早的文件")
    else:
        logger.info(f"📅 时间间隔：只爬取当日文件")
    if args.model_type:
        logger.info(f"🤖 AI模型类型：{args.model_type}")
    if args.enabled_platforms:
        enabled_platforms = [p.strip() for p in args.enabled_platforms.split(',')]
        logger.info(f"🌐 启用的平台：{', '.join(enabled_platforms)}")
    else:
        logger.info(f"🌐 启用的平台：所有平台")
    
    try:
        # 执行全流程（使用命令行参数）
        days_before = args.days_before if args.days_before > 0 else None
        enabled_platforms = [p.strip() for p in args.enabled_platforms.split(',')] if args.enabled_platforms else None
        result = run_full_process_cli(
            daily_limit=args.daily_limit,
            days_before=days_before,
            model_type=args.model_type,
            enabled_platforms=enabled_platforms
        )
        
        if result:
            logger.info("✅ 全流程执行成功")
            sys.exit(0)
        else:
            logger.warning("⚠️ 全流程执行失败或被中断")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 发生未预期的错误：{str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # 清理资源
        logger.info("🔄 清理资源...")
        try:
            db_gen = get_db()
            db = next(db_gen)
            db.close()
            logger.info("✅ 数据库连接已关闭")
        except Exception as e:
            logger.debug(f"清理数据库连接时出错（可忽略）：{str(e)}")
        
        logger.info("🏁 自动运行脚本结束")


if __name__ == "__main__":
    main()
