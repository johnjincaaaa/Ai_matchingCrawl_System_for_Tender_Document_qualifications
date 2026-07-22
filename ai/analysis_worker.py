# -*- coding: utf-8 -*-
"""AI分析单项目worker（供并发线程池调用，被 auto_run_full_process.py 与 app.py 共享）。

抽成中立模块避免代码重复，也避免直接 import 大脚本触发其模块级副作用（建日志文件、注册爬虫等）。
"""
import re
from utils.log import log


def analyze_one_project(analyzer, project_id, project_name):
    """分析单个项目（线程安全，供并发线程池调用）。

    线程安全要点：**每个线程用自己的 DB session**（SQLAlchemy Session 非线程安全），
    处理完立即 commit/close，让 SQLite 的单写锁尽快释放给其他线程。analyzer 实例可共享
    （其 chain 调用无状态，RateLimiter 已加锁）。

    Returns:
        tuple(status: str, project_id, project_name, detail)
        status ∈ {"success", "excluded", "empty", "failed"}，detail 为附加说明或异常信息。
    """
    from utils.db import SessionLocal, TenderProject, ProjectStatus, update_project
    from config import AI_CONFIG as _AI_CFG

    db = SessionLocal()
    try:
        project = db.query(TenderProject).filter_by(id=project_id).first()
        if not project:
            return ("failed", project_id, project_name, "项目不存在")

        # 内容为空：重置为DOWNLOADED等待重新解析
        if not project.evaluation_content:
            update_project(db, project_id, {
                "status": ProjectStatus.DOWNLOADED,
                "error_msg": "解析内容为空，已重置状态等待重新解析",
                "evaluation_content": None,
            })
            db.commit()
            return ("empty", project_id, project_name, "解析内容为空，已重置")

        log.info(f"开始分析项目：{project_name}（ID：{project_id}）")
        return _do_analyze(db, analyzer, project, project_id, project_name, _AI_CFG)
    except Exception as e:
        return _handle_failure(db, e, project_id, project_name)
    finally:
        db.close()


def _do_analyze(db, analyzer, project, project_id, project_name, _AI_CFG):
    """前置过滤 → 服务类判断 → 提取要求 → 比对 → 写库。异常向上抛给 analyze_one_project 统一处理。"""
    from utils.db import TenderProject, ProjectStatus, update_project
    import config

    # 前置过滤A：非招标文件（中标结果/更正/图纸/工程量清单等）→ 跳过AI分析，直接排除
    check_bid_security = None
    try:
        from utils.pre_filter import check_non_tender, check_bid_security
        _nt_hit, _nt_reason = check_non_tender(project.project_name, project.file_path)
    except Exception as _e:
        log.warning(f"前置过滤(非招标)调用失败，跳过该过滤：{_e}")
        _nt_hit, _nt_reason = False, ""
    if _nt_hit:
        log.info(f"⏭️ 项目 {project_id} {_nt_reason}，跳过AI分析并排除")
        update_project(db, project_id, {"status": ProjectStatus.EXCLUDED, "error_msg": _nt_reason})
        db.commit()
        return ("excluded", project_id, project_name, _nt_reason)

    # 前置过滤B：投标保证金 → 优先AI语义判断，未启用/不可用时回退关键词过滤
    try:
        if _AI_CFG.get("bid_security_check", {}).get("enable", False):
            _bs_hit, _bs_reason = analyzer.check_bid_security_ai(project.evaluation_content, project.project_name)
        elif check_bid_security is not None:
            _bs_hit, _bs_reason = check_bid_security(project.evaluation_content, project.project_name)
        else:
            _bs_hit, _bs_reason = False, ""
    except Exception as _e:
        log.warning(f"前置过滤(投标保证金)调用失败，跳过该过滤：{_e}")
        _bs_hit, _bs_reason = False, ""
    if _bs_hit:
        log.info(f"⏭️ 项目 {project_id} 需要投标保证金（{_bs_reason}），中断分析并设为不推荐")
        update_project(db, project_id, {
            "status": ProjectStatus.EXCLUDED, "final_decision": "不推荐",
            "error_msg": f"需要投标保证金：{_bs_reason}",
        })
        db.commit()
        return ("excluded", project_id, project_name, f"需要投标保证金：{_bs_reason}")

    # 0. 服务类项目判断
    is_service, reason = analyzer.is_service_project(project.evaluation_content)
    try:
        service_check_enabled = config.AI_CONFIG.get("service_check", {}).get("enable", False)
        enable_keyword_check = config.AI_CONFIG.get("qualification_keyword_check", {}).get("enable", False)
    except Exception as e:
        log.warning(f"访问config.AI_CONFIG失败，使用默认值：{str(e)}")
        service_check_enabled = False
        enable_keyword_check = False

    if is_service and service_check_enabled:
        log.info(f"⚠️ 项目 {project_id} 是服务类项目，标记为已排除：{reason}")
        update_project(db, project_id, {"status": ProjectStatus.EXCLUDED, "error_msg": f"服务类项目：{reason}"})
        db.commit()
        return ("excluded", project_id, project_name, f"服务类项目：{reason}")

    # 资质关键词检查（默认禁用）
    if enable_keyword_check:
        qualification_keywords = ['资质', '许可证', '认证', '备案', '执业资格', '许可', '等级证书']
        matched = [k for k in qualification_keywords if k in project.evaluation_content]
        if matched:
            reason = f"项目包含资质相关关键词：{', '.join(matched)}"
            log.info(f"⚠️ 项目 {project_id} 含资质关键词，标记为已排除：{reason}")
            update_project(db, project_id, {"status": ProjectStatus.EXCLUDED, "error_msg": f"含资质关键词：{reason}"})
            db.commit()
            return ("excluded", project_id, project_name, reason)

    # 1. 提取资质要求
    project_requirements = analyzer.extract_requirements(project.evaluation_content)

    # 2. 比对资质（最终判定与丢分阈值调整已在 compare_qualifications 内统一处理，此处不再二次调整）
    comparison_result, final_decision = analyzer.compare_qualifications(project_requirements)

    # 3. 确保结果是中文的
    if not ("符合" in comparison_result and ("可以参与" in comparison_result or "不可以参与" in comparison_result)):
        comparison_result = f"资质比对结果：{comparison_result}\n\n（注：以上为AI原始输出，已转换为中文显示）"

    # 4. 更新项目状态
    update_project(db, project_id, {
        "project_requirements": project_requirements,
        "ai_extracted_text": project_requirements,
        "comparison_result": comparison_result,
        "final_decision": final_decision or "未判定",
        "status": ProjectStatus.COMPARED,
    })
    db.commit()
    log.info(f"✅ 项目分析完成：{project_name}（ID：{project_id}，判定：{final_decision}）")
    return ("success", project_id, project_name, final_decision)


def _handle_failure(db, e, project_id, project_name):
    """失败处理：按失败次数决定重试(重置PARSED)或标记ERROR。"""
    from utils.db import TenderProject, ProjectStatus, update_project

    error_msg = str(e)[:500]
    try:
        db.rollback()
    except Exception:
        pass
    try:
        project = db.query(TenderProject).filter_by(id=project_id).first()
        prev_error = project.error_msg if project else None
        analysis_fail_count = 0
        if prev_error:
            match = re.search(r'\[AI分析失败(\d+)次\]', prev_error)
            if match:
                analysis_fail_count = int(match.group(1)) + 1
            else:
                base_error = re.sub(r'\[AI分析失败\d+次\].*', '', prev_error).strip()
                current_base_error = re.sub(r'\[AI分析失败\d+次\].*', '', error_msg).strip()
                if base_error == current_base_error or current_base_error in base_error:
                    analysis_fail_count = 2
                else:
                    analysis_fail_count = 1
        else:
            analysis_fail_count = 1

        if analysis_fail_count >= 3:
            error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次] [跳过-多次失败]"
            log.warning(f"⚠️ 项目 {project_name}（ID：{project_id}）AI分析已失败{analysis_fail_count}次，标记为跳过")
            update_project(db, project_id, {"status": ProjectStatus.ERROR, "error_msg": error_msg_full})
        else:
            error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次]"
            log.info(f"🔄 项目 {project_name}（ID：{project_id}）AI分析失败第{analysis_fail_count}次，自动重置状态准备重试")
            update_project(db, project_id, {
                "status": ProjectStatus.PARSED, "error_msg": error_msg_full,
                "project_requirements": None, "comparison_result": None, "final_decision": None,
            })
        db.commit()
    except Exception as inner:
        log.error(f"记录失败状态时再次出错（ID：{project_id}）：{inner}")
    log.error(f"❌ 项目分析失败：ID={project_id}，错误：{error_msg}")
    return ("failed", project_id, project_name, error_msg)
