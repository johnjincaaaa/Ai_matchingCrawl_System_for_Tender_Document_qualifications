#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动运行全流程脚本（命令行版本，不依赖Streamlit）
自动执行爬虫、解析、AI分析、生成报告等全流程
"""

import sys
import os
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
                    
                    success_count = 0
                    error_count = 0
                    
                    for project in projects:
                        try:
                            if not project.evaluation_content:
                                logger.warning(f"项目 {project.id} 解析内容为空，跳过分析")
                                # 自动重置为DOWNLOADED状态，以便重新解析
                                logger.info(f"🔄 项目 {project.id} 解析内容为空，自动重置为DOWNLOADED状态，等待重新解析")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.DOWNLOADED,
                                    "error_msg": "解析内容为空，已重置状态等待重新解析",
                                    "evaluation_content": None  # 清空空内容
                                })
                                db.commit()
                                error_count += 1
                                continue
                            
                            logger.info(f"开始分析项目：{project.project_name}（ID：{project.id}）")

                            # 前置过滤A：非招标文件（中标结果/更正/图纸/工程量清单等）→ 跳过AI分析，直接排除
                            try:
                                from utils.pre_filter import check_non_tender, check_bid_security
                                _nt_hit, _nt_reason = check_non_tender(project.project_name, project.file_path)
                            except Exception as _e:
                                logger.warning(f"前置过滤(非招标)调用失败，跳过该过滤：{_e}")
                                _nt_hit, _nt_reason = False, ""
                            if _nt_hit:
                                logger.info(f"⏭️ 项目 {project.id} {_nt_reason}，跳过AI分析并排除")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.EXCLUDED,
                                    "error_msg": _nt_reason,
                                })
                                db.commit()
                                continue

                            # 前置过滤B：投标保证金 → 优先AI语义判断（正确识别"不需要投标保证金"及
                            # 履约/质量保证金），未启用或不可用时回退关键词过滤；需要投标保证金则设为不推荐
                            try:
                                from config import AI_CONFIG as _AI_CFG
                                if _AI_CFG.get("bid_security_check", {}).get("enable", False):
                                    _bs_hit, _bs_reason = analyzer.check_bid_security_ai(project.evaluation_content, project.project_name)
                                else:
                                    _bs_hit, _bs_reason = check_bid_security(project.evaluation_content, project.project_name)
                            except Exception as _e:
                                logger.warning(f"前置过滤(投标保证金)调用失败，跳过该过滤：{_e}")
                                _bs_hit, _bs_reason = False, ""
                            if _bs_hit:
                                logger.info(f"⏭️ 项目 {project.id} 需要投标保证金（{_bs_reason}），中断分析并设为不推荐")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.EXCLUDED,
                                    "final_decision": "不推荐",
                                    "error_msg": f"需要投标保证金：{_bs_reason}",
                                })
                                db.commit()
                                continue

                            # 0. 先判断是否是服务类项目
                            is_service, reason = analyzer.is_service_project(project.evaluation_content)
                            
                            # 检查是否是因为功能被禁用而返回False
                            try:
                                service_check_enabled = config.AI_CONFIG.get("service_check", {}).get("enable", False)
                                enable_keyword_check = config.AI_CONFIG.get("qualification_keyword_check", {}).get("enable", False)
                            except Exception as e:
                                logger.warning(f"访问config.AI_CONFIG失败，使用默认值：{str(e)}")
                                service_check_enabled = False  # 默认禁用服务类检查
                                enable_keyword_check = False  # 默认禁用关键词检查
                            
                            if is_service and service_check_enabled:
                                # 只有当服务类判断功能启用且项目确实是服务类时，才标记为已排除
                                logger.info(f"⚠️ 项目 {project.id} 是服务类项目，标记为已排除：{reason}")
                                # 更新项目状态为已排除，而不是删除，避免下次重复爬取
                                update_project(db, project.id, {
                                    "status": ProjectStatus.EXCLUDED,
                                    "error_msg": f"服务类项目：{reason}"
                                })
                                db.commit()
                                logger.info(f"✅ 服务类项目已标记为已排除：{project.project_name}（ID：{project.id}）")
                                continue  # 跳过后续分析
                            elif is_service and not service_check_enabled:
                                # 当服务类判断功能被禁用时，跳过判断，继续分析所有项目
                                logger.info(f"服务类判断功能已禁用，跳过判断，继续分析项目 {project.id}")
                            else:
                                # 项目不是服务类，继续分析
                                logger.info(f"项目 {project.id} 不是服务类项目，继续分析")
                            
                            # 检查项目是否包含资质相关关键词（如果包含则删除，避免不必要的分析）
                            
                            has_qualification_keywords = False
                            matched_keywords = []
                            
                            if enable_keyword_check:
                                qualification_keywords = ['资质', '许可证', '认证', '备案', '执业资格', '许可', '等级证书']
                                
                                for keyword in qualification_keywords:
                                    if keyword in project.evaluation_content:
                                        has_qualification_keywords = True
                                        matched_keywords.append(keyword)
                                
                                if has_qualification_keywords:
                                    reason = f"项目包含资质相关关键词：{', '.join(matched_keywords)}"
                                    logger.info(f"⚠️ 项目 {project.id} 包含资质关键词，标记为已排除：{reason}")
                                    # 更新项目状态为已排除，而不是删除，避免下次重复爬取
                                    update_project(db, project.id, {
                                        "status": ProjectStatus.EXCLUDED,
                                        "error_msg": f"含资质关键词：{reason}"
                                    })
                                    db.commit()
                                    logger.info(f"✅ 含资质关键词项目已标记为已排除：{project.project_name}（ID：{project.id}）")
                                    continue  # 跳过后续分析
                                
                                logger.info(f"项目 {project.id} 不包含资质关键词，继续分析")
                            else:
                                logger.info(f"资质关键词检查已禁用，跳过检查，继续分析项目 {project.id}")
                            
                            # 1. 提取资质要求（与流程控制保持一致）
                            project_requirements = analyzer.extract_requirements(project.evaluation_content)
                            
                            # 2. 比对资质（与流程控制保持一致，使用AI进行详细比对）
                            comparison_result, final_decision = analyzer.compare_qualifications(project_requirements)
                            
                            # 3. 根据丢分阈值调整最终决策（与流程控制保持一致）
                            from config import OBJECTIVE_SCORE_CONFIG
                            import re

                            def _extract_loss_score(text: str) -> float:
                                loss = 0.0
                                # 优先通过“客观分总满分 / 客观分可得分”计算丢分
                                total_m = re.search(r'客观分总满分[：: ]*([0-9]+\.?[0-9]*)分', text)
                                gain_m = re.search(r'客观分可得分[：: ]*([0-9]+\.?[0-9]*)分', text)
                                if total_m and gain_m:
                                    try:
                                        total_s = float(total_m.group(1))
                                        gain_s = float(gain_m.group(1))
                                        loss = max(total_s - gain_s, 0.0)
                                    except ValueError:
                                        loss = 0.0
                                # 如果仍为0，再尝试匹配“丢分/失分 X 分”
                                if loss == 0.0:
                                    m = re.search(r'[丢失]分.*?([0-9]+\.?[0-9]*)分', text)
                                    if m:
                                        try:
                                            loss = float(m.group(1))
                                        except ValueError:
                                            loss = 0.0
                                return loss

                            if "客观分不满分" in final_decision:
                                # 检查是否需要根据丢分阈值改为"推荐参与"
                                loss_score = _extract_loss_score(comparison_result)
                                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                if loss_score <= threshold:
                                    # 丢分≤阈值，改为"推荐参与"
                                    original_decision = final_decision
                                    final_decision = "推荐参与"
                                    comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：推荐参与"
                            elif "推荐参与" in final_decision:
                                # 检查是否需要根据丢分阈值改为"不推荐参与"
                                loss_score = _extract_loss_score(comparison_result)
                                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                if loss_score > threshold:
                                    # 丢分>阈值，改为"不推荐参与"
                                    original_decision = final_decision
                                    final_decision = "不推荐参与"
                                    comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：不推荐参与"
                            
                            # 4. 确保结果是中文的
                            if not ("符合" in comparison_result and ("可以参与" in comparison_result or "不可以参与" in comparison_result)):
                                comparison_result = f"资质比对结果：{comparison_result}\n\n（注：以上为AI原始输出，已转换为中文显示）"
                            
                            # 5. 更新项目状态（与流程控制保持一致）
                            update_project(db, project.id, {
                                "project_requirements": project_requirements,
                                "ai_extracted_text": project_requirements,  # 保存AI提取的原始文本
                                "comparison_result": comparison_result,
                                "final_decision": final_decision or "未判定",
                                "status": ProjectStatus.COMPARED
                            })
                            
                            success_count += 1
                            logger.info(f"✅ 项目分析完成：{project.project_name}（成功：{success_count}，失败：{error_count}）")
                            
                        except KeyboardInterrupt:
                            logger.warning("⚠️ AI分析被用户中断")
                            raise  # 重新抛出，让上层处理
                        except Exception as e:
                            error_count += 1
                            error_msg = str(e)[:500]
                            
                            # 检查失败次数
                            import re
                            analysis_fail_count = 0
                            if project.error_msg:
                                # 检查error_msg中是否包含AI分析失败计数标记
                                match = re.search(r'\[AI分析失败(\d+)次\]', project.error_msg)
                                if match:
                                    analysis_fail_count = int(match.group(1)) + 1
                                else:
                                    # 检查是否是相同类型的错误
                                    base_error = re.sub(r'\[AI分析失败\d+次\].*', '', project.error_msg).strip()
                                    current_base_error = re.sub(r'\[AI分析失败\d+次\].*', '', error_msg).strip()
                                    if base_error == current_base_error or current_base_error in base_error:
                                        analysis_fail_count = 2  # 相同错误，设为2次（下次就是3次）
                                    else:
                                        analysis_fail_count = 1  # 不同错误，重新计数
                            else:
                                analysis_fail_count = 1
                            
                            if analysis_fail_count >= 3:
                                # 3次都失败，标记为异常
                                error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次] [跳过-多次失败]"
                                logger.warning(f"⚠️ 项目 {project.project_name}（ID：{project.id}）AI分析已失败{analysis_fail_count}次，标记为跳过")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.ERROR,
                                    "error_msg": error_msg_full
                                })
                            else:
                                # 自动重试：重置状态为PARSED，让它重新进入AI分析流程
                                error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次]"
                                logger.info(f"🔄 项目 {project.project_name}（ID：{project.id}）AI分析失败第{analysis_fail_count}次，自动重置状态准备重试")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.PARSED,  # 重置为PARSED状态，下次分析时会重新处理
                                    "error_msg": error_msg_full,
                                    "project_requirements": None,  # 清空之前可能的部分分析结果
                                    "comparison_result": None,
                                    "final_decision": None
                                })
                            
                            logger.error(f"❌ 项目分析失败：ID={project.id}，错误：{error_msg}")
                            # 继续处理下一个项目，不中断整个任务
                            continue
                    
                    logger.info(f"✅ 第 {current_round} 轮AI分析完成（成功：{success_count}，失败：{error_count}）")
                    
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
