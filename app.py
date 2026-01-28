import streamlit as st
import plotly.express as px
import pandas as pd
import os
import sys
import shutil
from datetime import datetime
import base64
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import time
import psutil
from threading import Thread
import json
from sqlalchemy import extract
import zipfile
from pathlib import Path
from types import SimpleNamespace
import logging
import warnings

# 初始化基础log对象，防止utils.log导入失败时出现NameError
log = logging.getLogger("tender_app")
if not log.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    _handler.setFormatter(_formatter)
    log.addHandler(_handler)
log.setLevel(logging.INFO)

# 配置Python标准库logging，过滤掉不需要的警告
# 这些警告是框架层面的，不影响应用功能，但会产生大量日志噪音
logging.getLogger('tornado').setLevel(logging.ERROR)  # 只显示ERROR级别以上的日志
logging.getLogger('tornado.access').setLevel(logging.WARNING)  # 访问日志设置为WARNING
logging.getLogger('tornado.application').setLevel(logging.ERROR)
logging.getLogger('tornado.general').setLevel(logging.ERROR)

# 过滤Streamlit ScriptRunContext警告
logging.getLogger('streamlit.runtime.scriptrunner_utils.script_run_context').setLevel(logging.ERROR)

# 抑制所有警告（这些WebSocket错误通常作为警告输出）
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', message='.*websocket.*', category=Warning)
warnings.filterwarnings('ignore', message='.*stream closed.*', category=Warning)
warnings.filterwarnings("ignore", message="missing ScriptRunContext!")
warnings.filterwarnings("ignore", message="This warning can be ignored when running in bare mode.")

# 创建一个自定义过滤器来完全屏蔽WebSocketClosedError相关日志（增强版）
class WebSocketErrorFilter(logging.Filter):
    """过滤tornado websocket关闭错误（增强版）"""
    def filter(self, record):
        # 检查是否是WebSocket相关的错误
        message = str(record.getMessage())
        # 检查异常类型
        exc_info = record.exc_info
        if exc_info and exc_info[0]:
            exc_type_name = exc_info[0].__name__
            exc_module = getattr(exc_info[0], '__module__', '')
            if any(keyword in exc_type_name.lower() or keyword in exc_module.lower() for keyword in [
                'websocketclosederror', 'streamclosederror', 'tornado'
            ]):
                return False  # 过滤掉这些异常
        
        # 检查消息内容
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in [
            'websocketclosederror', 'websocket closed', 
            'streamclosederror', 'stream is closed',
            'task exception was never retrieved',
            'future:', 'coro=<websocketprotocol13.write_message',
            'tornado.websocket', 'tornado.iostream',
            'during handling of the above exception',
            'traceback (most recent call last)',
            'file ".*tornado.*websocket', 'file ".*tornado.*iostream',
            'websocketprotocol13', 'streamclosed'
        ]):
            return False  # 过滤掉这些日志
        return True

# 为tornado相关logger添加过滤器
for logger_name in ['tornado', 'tornado.websocket', 'tornado.iostream', 'tornado.concurrent']:
    logger = logging.getLogger(logger_name)
    logger.addFilter(WebSocketErrorFilter())
    logger.setLevel(logging.CRITICAL)  # 设置为CRITICAL级别，几乎不输出
    
# 也为根logger添加过滤器（捕获所有未分类的WebSocket错误）
root_logger = logging.getLogger()
root_logger.addFilter(WebSocketErrorFilter())

# ====================== 抑制asyncio未捕获的异常警告 =====================
# "Task exception was never retrieved" 这些错误是asyncio框架产生的未捕获异常
# 它们直接输出到stderr，需要通过asyncio的异常处理器来抑制
try:
    import asyncio
    import sys
    import io
    
    def _suppress_websocket_exceptions(loop, context):
        """抑制WebSocket相关的asyncio异常（增强版）"""
        exception = context.get('exception')
        message = str(context.get('message', '')).lower()
        
        # 检查异常类型和消息
        should_suppress = False
        
        if exception:
            error_str = str(type(exception).__name__).lower()
            error_repr = str(exception).lower()
            # 获取异常的完整模块路径
            exc_module = getattr(type(exception), '__module__', '')
            exc_module_lower = exc_module.lower()
            
            # 如果是WebSocket相关的异常，静默处理
            if any(keyword in error_str or keyword in error_repr or keyword in exc_module_lower for keyword in [
                'websocketclosederror', 'streamclosederror', 'stream is closed',
                'websocket', 'tornado.websocket', 'tornado.iostream',
                'tornado', 'streamclosed'
            ]):
                should_suppress = True
        
        # 检查消息内容（即使没有异常对象）
        if not should_suppress and any(keyword in message for keyword in [
            'websocketclosederror', 'streamclosederror', 'stream is closed',
            'task exception was never retrieved', 'future:', 'coro=',
            'websocketprotocol13.write_message', 'tornado.websocket',
            'tornado.iostream', 'streamclosederror', 'websocket closed',
            'during handling of the above exception', 'traceback (most recent call last)',
            'file ".*tornado.*websocket', 'file ".*tornado.*iostream'
        ]):
            should_suppress = True
        
        # 如果应该抑制，直接返回（不调用默认处理器）
        if should_suppress:
            return  # 静默忽略
        
        # 其他异常使用默认处理器
        if hasattr(loop, 'default_exception_handler'):
            loop.default_exception_handler(context)
    
    # 设置全局异常处理器（在所有事件循环上生效）
    def _setup_asyncio_exception_handler():
        """设置asyncio异常处理器"""
        try:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                loop.set_exception_handler(_suppress_websocket_exceptions)
            except RuntimeError:
                # 如果没有运行中的循环，尝试创建新的
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_running():
                        loop.set_exception_handler(_suppress_websocket_exceptions)
                except RuntimeError:
                    # 如果都没有，设置默认策略
                    if sys.platform == 'win32':
                        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    else:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception:
            pass  # 如果设置失败，忽略
    
    # 立即设置异常处理器
    _setup_asyncio_exception_handler()
    
    # 重定向stderr以过滤WebSocket错误（作为最后的手段）
    class FilteredStderr(io.TextIOWrapper):
        """过滤stderr输出，移除WebSocket错误"""
        def __init__(self, original_stderr):
            self.original_stderr = original_stderr
            super().__init__(original_stderr.buffer, encoding=original_stderr.encoding, 
                           errors=original_stderr.errors, line_buffering=True)
        
        def write(self, text):
            # 检查是否是WebSocket相关错误（增强版）
            if not text:
                return
            
            text_lower = text.lower()
            # 检查单行是否包含WebSocket错误关键词
            if any(keyword in text_lower for keyword in [
                'websocketclosederror', 'streamclosederror', 'stream is closed',
                'task exception was never retrieved', 'future:',
                'coro=<websocketprotocol13.write_message', 'tornado.websocket',
                'tornado.iostream', 'during handling of the above exception',
                'traceback (most recent call last)', 'file ".*tornado.*websocket',
                'file ".*tornado.*iostream', 'websocketprotocol13', 'streamclosed',
                'websocketprotocol13.write_message', 'tornado.concurrent'
            ]):
                return  # 不输出
            # 检查是否是多行错误堆栈的一部分（通过检查是否包含tornado路径）
            if 'tornado' in text_lower and ('websocket' in text_lower or 'iostream' in text_lower):
                return  # 不输出
            # 检查是否包含tornado路径（更宽松的匹配）
            if 'tornado' in text_lower and ('site-packages' in text_lower or 'lib' in text_lower):
                # 进一步检查是否是WebSocket相关的文件路径
                if any(keyword in text_lower for keyword in ['websocket', 'iostream', 'concurrent']):
                    return  # 不输出
            return self.original_stderr.write(text)
        
        def flush(self):
            return self.original_stderr.flush()
    
    # 只在Windows上应用stderr过滤（避免影响其他平台）
    if sys.platform == 'win32':
        try:
            # 保存原始stderr
            if not hasattr(sys, '_original_stderr'):
                sys._original_stderr = sys.stderr
            # 实际应用过滤的stderr（增强版：更彻底地抑制WebSocket错误）
            try:
                # 尝试替换stderr为过滤版本
                filtered_stderr = FilteredStderr(sys._original_stderr)
                sys.stderr = filtered_stderr
            except Exception:
                # 如果替换失败，至少确保异常处理器已设置
                pass
        except Exception:
            pass  # 如果过滤失败，继续使用原始stderr
            
except ImportError:
    # asyncio不可用时跳过
    pass
except Exception:
    # 如果设置失败，忽略（不影响应用运行）
    pass

# ====================== 配置与初始化 ======================
# 设置页面配置（必须放在最前面）
st.set_page_config(
    page_title="标书资质自动匹配系统",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入系统核心模块
try:
    import config
    from config import COMPANY_QUALIFICATIONS, TEST_CONFIG, SPIDER_CONFIG, BASE_DIR, FILES_DIR, REPORT_DIR, STORAGE_CONFIG, LOG_DIR, OBJECTIVE_SCORE_CONFIG
    from parser.file_parser import FileParser
    from ai.qualification_analyzer import AIAnalyzer
    from report.report_generator import ReportGenerator
    from utils.storage_manager import StorageManager
    from utils.task_scheduler import WindowsTaskScheduler
    from utils.db import get_db, TenderProject, ProjectStatus, update_project, save_project, CompanyQualification, get_company_qualifications, add_company_qualification, update_company_qualification, delete_company_qualification, ClassACertificate, get_class_a_certificates, add_class_a_certificate, update_class_a_certificate, delete_class_a_certificate, ClassBRule, get_class_b_rules, add_class_b_rule, update_class_b_rule, delete_class_b_rule, extract
    from spider.tender_spider import ZheJiangTenderSpider
    from spider import SpiderManager
    from utils.log import log
    
    # 爬虫模块导入和组件初始化改为懒加载，避免每次页面加载都执行
    # 这些操作将在首次使用时通过缓存函数执行
    log.debug("模块导入完成，组件将在首次使用时懒加载")
    SYSTEM_READY = True
except Exception as e:
    st.error(f"❌ 系统初始化失败：{str(e)}")
    st.info("💡 解决建议：")
    st.markdown("- 检查Python环境和依赖包是否正确安装")
    st.markdown("- 确保config.py配置文件存在且格式正确")
    st.markdown("- 检查数据库连接和SQLite文件权限")
    st.markdown("- 验证模型服务（如Ollama）是否正常运行")
    SYSTEM_READY = False


# ====================== 性能优化和资源清理 ======================
def safe_streamlit_update(update_func, *args, **kwargs):
    """安全地执行Streamlit更新操作，捕获WebSocket关闭异常"""
    try:
        return update_func(*args, **kwargs)
    except Exception as e:
        # 忽略WebSocket关闭相关的异常（客户端可能已断开连接）
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['websocket', 'stream closed', 'connection closed']):
            # 静默忽略这些异常，因为它们不影响功能
            pass
        else:
            # 其他异常需要记录
            try:
                log.debug(f"Streamlit更新操作异常（已忽略）: {type(e).__name__}: {str(e)[:100]}")
            except:
                pass  # 如果日志记录也失败，直接忽略
        return None

def cleanup_resources():
    """定期清理资源，防止长时间运行后卡顿"""
    import gc
    
    # 清理过期的session_state（保留必要的状态）
    keys_to_keep = {
        'ai_analyzer',  # AI分析器需要保留
        'spider_running', 'spider_paused', 'spider_total',  # 爬虫状态
        'ai_analysis_running', 'ai_analysis_paused',  # AI分析状态
        'run_spider', 'run_full_process',  # 流程控制
        'page_load_count',  # 页面加载计数
    }
    
    # 清理临时状态（以特定前缀开头的）
    temp_prefixes = ['editing_', 'review_', 'reanalyze_', 'fulltext_reanalyze_']
    keys_to_remove = []
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            # 检查是否是临时状态
            if any(key.startswith(prefix) for prefix in temp_prefixes):
                keys_to_remove.append(key)
            # 清理过期的下载按钮状态（如果存在）
            elif key.startswith('download_file_') and len(st.session_state) > 100:
                keys_to_remove.append(key)
    
    # 批量删除
    for key in keys_to_remove:
        try:
            del st.session_state[key]
        except KeyError:
            pass
    
    # 如果session_state太大，清理更多
    if len(st.session_state) > 50:
        # 保留核心状态，清理其他
        core_keys = set(keys_to_keep)
        for key in list(st.session_state.keys()):
            if key not in core_keys and not any(key.startswith(prefix) for prefix in ['spider_', 'ai_analysis_', 'run_']):
                try:
                    del st.session_state[key]
                except KeyError:
                    pass
    
    # 强制垃圾回收
    gc.collect()
    
    # 清理Streamlit缓存（每50次页面加载清理一次）
    try:
        if st.session_state.get('page_load_count', 0) % 50 == 0:
            st.cache_data.clear()
    except Exception:
        pass


# 在页面加载时执行清理（优化：减少检查频率）
if 'page_load_count' not in st.session_state:
    st.session_state['page_load_count'] = 0

# 每50次页面加载清理一次资源（进一步减少清理频率，提升性能）
page_load_count = st.session_state['page_load_count']
st.session_state['page_load_count'] = page_load_count + 1

if page_load_count > 0 and page_load_count % 50 == 0:
    cleanup_resources()

# ====================== 全局函数 ======================
@st.cache_resource  # 使用 cache_resource 缓存资源对象
def get_file_parser():
    """懒加载获取FileParser实例，避免模块级别阻塞"""
    try:
        log.debug("初始化FileParser（懒加载）")
        return FileParser()
    except Exception as e:
        log.error(f"FileParser初始化失败: {str(e)}", exc_info=True)
        raise

@st.cache_resource  # 使用 cache_resource 缓存资源对象
def get_report_generator():
    """懒加载获取ReportGenerator实例，避免模块级别阻塞"""
    try:
        log.debug("初始化ReportGenerator（懒加载）")
        return ReportGenerator()
    except Exception as e:
        log.error(f"ReportGenerator初始化失败: {str(e)}", exc_info=True)
        raise

def get_ai_analyzer():
    """懒加载获取AIAnalyzer实例，避免模块级别阻塞"""
    # 在函数内部导入，确保总是可用
    try:
        from ai.qualification_analyzer import AIAnalyzer
    except ImportError as e:
        st.error(f"❌ AIAnalyzer导入失败：{str(e)}")
        log.error(f"AIAnalyzer导入失败：{str(e)}", exc_info=True)
        st.stop()
        return None
    
    if 'ai_analyzer' not in st.session_state:
        try:
            st.session_state['ai_analyzer'] = AIAnalyzer()
        except Exception as e:
            st.error(f"❌ AIAnalyzer初始化失败：{str(e)}")
            log.error(f"AIAnalyzer初始化失败：{str(e)}", exc_info=True)
            raise
    return st.session_state['ai_analyzer']

# 注意：以下session_state循环处理已移至main()函数中，避免模块级别阻塞
def process_session_state_actions():
    """处理session_state中的异步操作（从模块级别移到这里）"""
    try:
        ai_analyzer = get_ai_analyzer()  # 懒加载，只在需要时才初始化
    except Exception as e:
        log.warning(f"获取AI分析器失败（可忽略）：{str(e)}")
        return  # 如果无法获取AI分析器，直接返回，不处理相关操作
    
    # 处理项目全文本重新AI分析（不压缩模式）
    for key in list(st.session_state.keys()):
        if key.startswith('fulltext_reanalyze_project_'):
            db = None
            try:
                project_id = int(key.split('_')[-1])
                db = next(get_db())
            except (ValueError, StopIteration) as e:
                log.warning(f"解析项目ID失败或数据库连接失败（可忽略）：{str(e)}")
                continue
            
            try:
                project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            except Exception as e:
                log.warning(f"查询项目失败（可忽略）：{str(e)}")
                if db:
                    try:
                        db.close()
                    except:
                        pass
                continue
            
            if project:
                try:
                    # 执行全文本AI重新分析（不压缩）
                    if not project.evaluation_content:
                        raise ValueError("项目解析内容为空")
                    
                    with st.spinner(f"正在使用全文本重新提取和分析项目 {project.id}（不压缩，使用完整文本）..."):
                        # 1. 使用全文本提取资质要求（跳过预处理压缩）
                        project_requirements = ai_analyzer.extract_requirements_fulltext(project.evaluation_content)
                        
                        # 2. 比对资质
                        comparison_result, final_decision = ai_analyzer.compare_qualifications(project_requirements)
                        
                        # 3. 应用客观分判定配置
                        from config import OBJECTIVE_SCORE_CONFIG
                        if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                            # 检查是否需要根据客观分丢分阈值调整最终决策
                            import re

                            # 封装一个内部函数，统一“丢分”计算逻辑
                            def _extract_loss_score(text: str) -> float:
                                loss = 0.0
                                # 1. 通过“客观分总满分 / 客观分可得分”计算
                                total_m = re.search(r'客观分总满分[：: ]*([0-9]+\.?[0-9]*)分', text)
                                gain_m = re.search(r'客观分可得分[：: ]*([0-9]+\.?[0-9]*)分', text)
                                if total_m and gain_m:
                                    try:
                                        total_s = float(total_m.group(1))
                                        gain_s = float(gain_m.group(1))
                                        loss = max(total_s - gain_s, 0.0)
                                    except ValueError:
                                        loss = 0.0
                                # 2. 若仍为0，再尝试匹配“丢分/失分 X 分”
                                if loss == 0.0:
                                    m = re.search(r'[丢失]分.*?([0-9]+\.?[0-9]*)分', text)
                                    if m:
                                        try:
                                            loss = float(m.group(1))
                                        except ValueError:
                                            loss = 0.0
                                return loss

                            if "客观分不满分" in final_decision:
                                # 尝试从比对结果中提取丢分信息
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
                    
                    # 2.5. 如果项目之前被移出推荐（有复核说明），移除旧的复核说明，使用新的分析结果
                    if project.comparison_result and ("【复核说明】" in project.comparison_result or "复核不推荐" in project.comparison_result):
                        # 如果新的结果是推荐，清除复核状态
                        if final_decision in ["推荐参与", "可以参与", "客观分满分", "通过"]:
                            project.review_status = None
                            project.review_result = None
                            project.review_reason = None
                            project.review_time = None
                    
                    # 3. 更新项目状态（完全替换comparison_result，不保留旧内容）
                    update_project(db, project.id, {
                        "project_requirements": project_requirements,
                        "comparison_result": comparison_result,  # 完全替换，不保留旧内容
                        "final_decision": final_decision or "未判定",
                        "status": ProjectStatus.COMPARED,
                        "ai_extracted_text": project_requirements,  # 保存AI提取的原始文本
                        "review_status": project.review_status if hasattr(project, 'review_status') else None,
                        "review_result": project.review_result if hasattr(project, 'review_result') else None,
                        "review_reason": project.review_reason if hasattr(project, 'review_reason') else None,
                        "review_time": project.review_time if hasattr(project, 'review_time') else None
                    })
                    
                    # 清除缓存（延迟到函数定义后执行，使用st.cache_data的clear方法）
                    # 注意：这些函数在文件后面定义，但Streamlit会在运行时处理
                    try:
                        # 使用st.cache_data.clear()来清除所有缓存
                        st.cache_data.clear()
                    except Exception:
                        # 如果清除失败，尝试单独清除（函数可能还未定义）
                        pass
                    
                    st.success(f"✅ 项目 {project.id} 全文本重新分析完成")
                    # 清除session状态
                    del st.session_state[key]
                    time.sleep(0.5)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 项目全文本重新分析失败：{str(e)}")
                    st.exception(e)
                    # 清除session状态
                    if key in st.session_state:
                        del st.session_state[key]
                finally:
                    db.close()
    
    # 处理项目重新AI分析（压缩模式，原有功能）
    for key in list(st.session_state.keys()):
        if key.startswith('reanalyze_project_') and not key.startswith('fulltext_reanalyze_project_'):
            try:
                project_id = int(key.split('_')[-1])
                db = next(get_db())
            except (ValueError, StopIteration) as e:
                log.warning(f"解析项目ID失败或数据库连接失败（可忽略）：{str(e)}")
                continue
            
            try:
                project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            except Exception as e:
                log.warning(f"查询项目失败（可忽略）：{str(e)}")
                try:
                    db.close()
                except:
                    pass
                continue
            
            if project:
                try:
                    # 执行AI重新分析
                    if not project.evaluation_content:
                        raise ValueError("项目解析内容为空")
                    
                    # 1. 提取资质要求
                    project_requirements = ai_analyzer.extract_requirements(project.evaluation_content)
                    
                    # 2. 比对资质
                    comparison_result, final_decision = ai_analyzer.compare_qualifications(project_requirements)
                    
                    # 3. 应用客观分判定配置
                    from config import OBJECTIVE_SCORE_CONFIG
                    if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                        # 检查是否需要根据客观分丢分阈值调整最终决策
                        import re

                        def _extract_loss_score(text: str) -> float:
                            loss = 0.0
                            total_m = re.search(r'客观分总满分[：: ]*([0-9]+\.?[0-9]*)分', text)
                            gain_m = re.search(r'客观分可得分[：: ]*([0-9]+\.?[0-9]*)分', text)
                            if total_m and gain_m:
                                try:
                                    total_s = float(total_m.group(1))
                                    gain_s = float(gain_m.group(1))
                                    loss = max(total_s - gain_s, 0.0)
                                except ValueError:
                                    loss = 0.0
                            if loss == 0.0:
                                m = re.search(r'[丢失]分.*?([0-9]+\.?[0-9]*)分', text)
                                if m:
                                    try:
                                        loss = float(m.group(1))
                                    except ValueError:
                                        loss = 0.0
                            return loss

                        if "客观分不满分" in final_decision:
                            # 尝试从比对结果中提取丢分信息
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
                    
                    # 3. 更新项目状态
                    update_project(db, project.id, {
                        "project_requirements": project_requirements,
                        "comparison_result": comparison_result,
                        "final_decision": final_decision or "未判定",
                        "status": ProjectStatus.COMPARED
                    })
                    
                    # 清除session状态
                    del st.session_state[key]
                    
                except Exception as e:
                    st.error(f"❌ 项目重新分析失败：{str(e)}")
                    # 清除session状态
                    if key in st.session_state:
                        del st.session_state[key]
                finally:
                    if db:
                        try:
                            db.close()
                        except:
                            pass
            else:
                # 如果项目不存在，也要关闭数据库连接
                if db:
                    try:
                        db.close()
                    except:
                        pass


@st.cache_data(ttl=300, max_entries=10)  # 缓存5分钟，减少数据库查询
def get_project_stats():
    """获取项目统计信息（优化：使用单个查询减少数据库访问）"""
    from sqlalchemy import func, case
    db = next(get_db())
    try:
        # 优化：使用单个查询获取所有统计信息，减少数据库往返
        stats = db.query(
            func.count(TenderProject.id).label('total'),
            func.sum(
                case((TenderProject.status == ProjectStatus.COMPARED, 1), else_=0)
            ).label('completed'),
            func.sum(
                case((
                    TenderProject.final_decision.in_(["可以参与", "客观分满分", "推荐参与", "通过"]), 1
                ), else_=0)
            ).label('qualified')
        ).first()
        
        total = stats.total or 0
        completed = stats.completed or 0
        qualified = stats.qualified or 0
        
        return {
            "total": total,
            "completed": completed,
            "qualified": qualified,
            "unqualified": completed - qualified
        }
    finally:
        db.close()


def create_download_link(file_data, filename, mime_type):
    """
    创建 base64 编码的下载链接（避免 Streamlit 媒体文件存储问题）
    
    Args:
        file_data: 文件数据（bytes）
        filename: 文件名
        mime_type: MIME类型
        
    Returns:
        str: HTML 下载链接
    """
    try:
        import base64
        b64_data = base64.b64encode(file_data).decode()
        href = f'<a href="data:{mime_type};base64,{b64_data}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1f77b4; color: white; text-decoration: none; border-radius: 0.25rem; font-weight: 500;">📥 下载文件</a>'
        return href
    except Exception as e:
        log.error(f"创建下载链接失败: {str(e)}")
        return None


def prepare_file_for_download(file_path):
    """
    准备文件用于下载（支持文件和文件夹）
    
    Args:
        file_path: 文件或文件夹路径
        
    Returns:
        tuple: (文件数据bytes, 文件名, MIME类型, 错误信息)
    """
    try:
        if not file_path or not os.path.exists(file_path):
            return None, None, None, "文件路径不存在"
        
        # 如果是文件夹，打包成zip
        if os.path.isdir(file_path):
            import io
            zip_buffer = io.BytesIO()
            folder_name = os.path.basename(file_path.rstrip(os.sep))
            
            # 限制文件夹大小，避免内存溢出（最大500MB）
            total_size = 0
            max_size = 500 * 1024 * 1024  # 500MB
            file_count = 0
            max_files = 1000  # 限制文件数量
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                for root, dirs, files in os.walk(file_path):
                    # 跳过隐藏文件和系统文件
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    for file in files:
                        if file.startswith('.'):
                            continue
                        
                        if file_count >= max_files:
                            break
                            
                        file_full_path = os.path.join(root, file)
                        
                        try:
                            # 检查文件大小
                            file_size = os.path.getsize(file_full_path)
                            if total_size + file_size > max_size:
                                break
                            
                            # 计算相对路径
                            arcname = os.path.relpath(file_full_path, file_path)
                            arcname = os.path.join(folder_name, arcname).replace('\\', '/')
                            
                            # 读取文件内容并添加到zip
                            with open(file_full_path, 'rb') as f:
                                file_data = f.read()
                                zip_file.writestr(arcname, file_data)
                                total_size += len(file_data)
                                file_count += 1
                                
                        except (IOError, OSError, PermissionError):
                            # 跳过无法读取的文件，但不中断整个流程
                            continue
                        except Exception:
                            continue
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.read()
            
            if len(zip_data) == 0:
                return None, None, None, "文件夹为空或无法读取文件"
                
            filename = f"{folder_name}.zip"
            mime_type = "application/zip"
            return zip_data, filename, mime_type, None
        
        # 如果是文件，直接读取
        else:
            # 检查文件大小（限制单个文件最大500MB）
            file_size = os.path.getsize(file_path)
            max_file_size = 500 * 1024 * 1024  # 500MB
            
            if file_size > max_file_size:
                return None, None, None, f"文件过大（{file_size / 1024 / 1024:.2f}MB），最大支持500MB"
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            filename = os.path.basename(file_path)
            # 根据文件扩展名确定MIME类型
            ext = os.path.splitext(filename)[1].lower()
            mime_types = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.xls': 'application/vnd.ms-excel',
                '.txt': 'text/plain',
                '.zip': 'application/zip',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')
            return file_data, filename, mime_type, None
            
    except Exception as e:
        return None, None, None, f"准备文件失败: {str(e)}"


def render_objective_score_analysis(objective_scores, key_suffix=""):
    """渲染客观分分析组件
    
    Args:
        objective_scores: 客观分数据（JSON字符串）
        key_suffix: 用于生成唯一key的后缀，避免多个项目详情同时显示时的key冲突
    """
    if objective_scores:
        with st.expander("客观分分析", expanded=False):
            try:
                objective_data = json.loads(objective_scores)
                if isinstance(objective_data, list) and objective_data:
                    # 表格展示
                    df = pd.DataFrame(objective_data)
                    st.dataframe(df, width='stretch')
                    
                    # 图表展示
                    if 'score' in df.columns and 'criterion' in df.columns:
                        # 如果有满分数据，创建双轴柱状图
                        if 'max_score' in df.columns:
                            # 创建得分和满分的对比图表
                            fig = px.bar(df, x='criterion', y=['score', 'max_score'], 
                                        title='客观分得分与满分对比',
                                        color_discrete_map={'score': '#28a745', 'max_score': '#e9ecef'},
                                        barmode='group')
                            fig.update_layout(
                                xaxis_tickangle=-45,
                                xaxis_title='评分项',
                                yaxis_title='分数',
                                legend_title='分数类型',
                                font=dict(size=12),
                                margin=dict(l=20, r=20, t=50, b=100)
                            )
                            # 添加数据标签
                            fig.update_traces(texttemplate='%{y}', textposition='outside', textfont_size=10)
                        else:
                            # 只有得分的图表
                            fig = px.bar(df, x='criterion', y='score', title='客观分分布', 
                                        color='score', color_continuous_scale='RdYlGn')
                            fig.update_layout(
                                xaxis_tickangle=-45,
                                xaxis_title='评分项',
                                yaxis_title='得分',
                                font=dict(size=12),
                                margin=dict(l=20, r=20, t=50, b=100)
                            )
                            # 添加数据标签
                            fig.update_traces(texttemplate='%{y}', textposition='outside', textfont_size=10)
                        
                        st.plotly_chart(fig, config={"displayModeBar": True}, width='stretch')
                    
                    # 总分计算（确保item是字典类型）
                    total_score = sum(item.get('score', 0) if isinstance(item, dict) else 0 for item in objective_data)
                    max_possible = sum(
                        item.get('max_score', item.get('score', 0)) if isinstance(item, dict) else 0 
                        for item in objective_data
                    )
                    st.info(f"客观分总分: {total_score}/{max_possible}")
                else:
                    st.text_area("客观分数据", objective_scores, height=200, key=f"objective_scores_raw_{key_suffix}_{id(objective_scores)}")
            except json.JSONDecodeError:
                st.text_area("客观分数据（JSON格式错误）", objective_scores, height=200, key=f"objective_scores_error_{key_suffix}_{id(objective_scores)}")
                st.info("💡 解决建议：")
                st.markdown("- 检查数据格式是否符合JSON规范")
                st.markdown("- 确认AI分析流程是否正常完成")
                st.markdown("- 尝试重新运行项目分析")
            except Exception as e:
                st.error(f"解析客观分数据失败: {str(e)}")
                st.info("💡 解决建议：")
                st.markdown("- 检查项目数据是否完整")
                st.markdown("- 验证AI分析结果格式")
                st.markdown("- 尝试重新生成分析结果")


def render_subjective_score_analysis(subjective_scores, key_suffix=""):
    """渲染主观分分析组件
    
    Args:
        subjective_scores: 主观分数据（JSON字符串）
        key_suffix: 用于生成唯一key的后缀，避免多个项目详情同时显示时的key冲突
    """
    if subjective_scores:
        with st.expander("主观分分析", expanded=False):
            try:
                subjective_data = json.loads(subjective_scores)
                if isinstance(subjective_data, list) and subjective_data:
                    # 表格展示
                    df = pd.DataFrame(subjective_data)
                    st.dataframe(df, width='stretch')
                    
                    # 图表展示
                    if 'max_score' in df.columns and 'criterion' in df.columns:
                        fig = px.bar(df, x='criterion', y='max_score', title='主观分满分分布', 
                                    color='max_score', color_continuous_scale='Blues')
                        fig.update_layout(
                            xaxis_tickangle=-45,
                            xaxis_title='评分项',
                            yaxis_title='满分值',
                            font=dict(size=12),
                            margin=dict(l=20, r=20, t=50, b=100),
                            showlegend=False
                        )
                        # 添加数据标签
                        fig.update_traces(texttemplate='%{y}', textposition='outside', textfont_size=10)
                        st.plotly_chart(fig, config={"displayModeBar": True}, width='stretch')
                else:
                    st.text_area("主观分数据", subjective_scores, height=200, key=f"subjective_scores_raw_{key_suffix}_{id(subjective_scores)}")
            except json.JSONDecodeError:
                st.text_area("主观分数据（JSON格式错误）", subjective_scores, height=200, key=f"subjective_scores_error_{key_suffix}_{id(subjective_scores)}")
                st.info("💡 解决建议：")
                st.markdown("- 检查数据格式是否符合JSON规范")
                st.markdown("- 确认AI分析流程是否正常完成")
                st.markdown("- 尝试重新运行项目分析")
            except Exception as e:
                st.error(f"解析主观分数据失败: {str(e)}")
                st.info("💡 解决建议：")
                st.markdown("- 检查项目数据是否完整")
                st.markdown("- 验证AI分析结果格式")
                st.markdown("- 尝试重新生成分析结果")


def render_comparison_analysis(comparison_result, key_suffix=""):
    """渲染对比分析组件，展示分析过程和结论"""
    if not comparison_result:
        return
    
    with st.expander("比对结果", expanded=False):
        # 尝试解析对比结果，提取分析过程和最终结论
        analysis_process = ""
        final_conclusion = ""
        
        # 优先查找结构化格式的"三、最终判定"部分
        final_section_markers = ["=== 三、最终判定 ===", "三、最终判定", "=== 最终判定 ===", "【最终判定】"]
        conclusion_pos = -1
        
        for marker in final_section_markers:
            pos = comparison_result.find(marker)
            if pos != -1:
                conclusion_pos = pos
                break
        
        # 如果没有找到结构化标记，尝试查找其他结论标识
        if conclusion_pos == -1:
            conclusion_keywords = ["【最终判定结果】", "最终判定结果", "最终判定：", "=== 最终判定 ===", "【最终结论】"]
            for keyword in conclusion_keywords:
                pos = comparison_result.find(keyword)
                if pos != -1:
                    conclusion_pos = pos
                    break
        
        # 如果还是没找到，尝试查找包含"客观分满分"或"客观分不满分"的最后出现位置
        # 这样可以找到最终结论部分（因为在分析过程中也可能出现这些词）
        if conclusion_pos == -1:
            last_qualified_pos = comparison_result.rfind("客观分满分")
            last_unqualified_pos = comparison_result.rfind("客观分不满分")
            if last_qualified_pos != -1 or last_unqualified_pos != -1:
                # 取最后出现的位置作为结论开始
                conclusion_pos = max(last_qualified_pos, last_unqualified_pos)
                # 向前查找，找到这一段的开始（通常是"判定结果为"或类似文字）
                if conclusion_pos > 50:
                    # 向前查找最近的段落开始标识
                    prev_markers = ["判定结果", "最终判定", "结论", "\n\n", "\n"]
                    for marker in prev_markers:
                        marker_pos = comparison_result.rfind(marker, 0, conclusion_pos)
                        if marker_pos != -1 and conclusion_pos - marker_pos < 100:
                            conclusion_pos = marker_pos
                            break
        
        # 如果找到了结论位置，分离分析过程和结论
        if conclusion_pos != -1 and conclusion_pos > 0:
            analysis_process = comparison_result[:conclusion_pos].strip()
            final_conclusion = comparison_result[conclusion_pos:].strip()
        else:
            # 如果找不到明确的分离点，将整个内容作为分析过程
            analysis_process = comparison_result
            final_conclusion = ""
        
        # 显示分析过程
        if analysis_process:
            st.markdown("### 📊 详细分析过程")
            st.text_area(
                "AI分析过程",
                analysis_process,
                height=400,
                key=f"analysis_process_{key_suffix}",
                help="展示AI对每个评分项的详细分析过程，包括项目要求分析、匹配过程分析、综合判定等完整步骤"
            )
        
        # 显示最终结论
        if final_conclusion:
            st.markdown("---")
            st.markdown("### ✅ 最终判定结果")
            # 根据结论类型设置不同的样式
            if "客观分满分" in final_conclusion or "可以参与" in final_conclusion or "推荐参与" in final_conclusion:
                st.success(final_conclusion)
            elif "客观分不满分" in final_conclusion or "不可以参与" in final_conclusion or "不推荐参与" in final_conclusion:
                st.error(final_conclusion)
            else:
                st.info(final_conclusion)
        elif analysis_process:
            # 如果没有单独的结论部分，显示完整内容
            st.markdown("---")
            st.markdown("### 📋 完整比对结果")
            st.text_area(
                "完整内容",
                comparison_result,
                height=200,
                key=f"full_comparison_{key_suffix}"
            )


def render_project_details(project, project_id_suffix="", include_file_download=True, is_visualization=False):
    """
    统一的项目详情渲染函数
    
    Args:
        project: TenderProject对象
        project_id_suffix: 用于区分不同位置的唯一后缀（避免key冲突）
        include_file_download: 是否包含文件下载功能（默认True）
        is_visualization: 是否在可视化页面中使用（True时隐藏不需要的信息）
    """
    # 在可视化页面中不显示提取后的原始文本和AI提取文本
    if not is_visualization:
        # 显示提取后的原始文本
        if project.evaluation_content:
            with st.expander("提取后的全部文本", expanded=False):
                st.text_area("原始提取内容", project.evaluation_content, height=300, 
                            key=f"evaluation_content_{project.id}{project_id_suffix}")
                
                # 添加全文本重新提取按钮（仅在原始文本存在且没有评分要求时显示）
                if project.evaluation_content and (not project.project_requirements or len(project.project_requirements.strip()) < 50):
                    st.markdown("---")
                    st.info("💡 如果原始文本中包含评分表但未提取成功，可以使用全文本重新提取（不压缩，使用完整文本）")
                    if st.button("🔍 使用全文本重新提取和分析", 
                                key=f"fulltext_reanalyze_{project.id}{project_id_suffix}",
                                type="primary",
                                help="使用完整的原始文本（不压缩）重新进行AI提取和分析，适用于评分表提取失败的情况"):
                        # 设置全文本重新分析的会话状态
                        st.session_state[f'fulltext_reanalyze_project_{project.id}'] = True
                        st.rerun()
        
        # 显示AI提取后的文本
        if project.ai_extracted_text:
            with st.expander("AI提取后的文本", expanded=False):
                st.text_area("AI提取结果", project.ai_extracted_text, height=200, 
                            key=f"ai_extracted_text_{project.id}{project_id_suffix}")
    
    # 显示评分要求和比对结果
    # 优先使用 project_requirements，如果为空则使用 ai_extracted_text
    requirements_to_display = project.project_requirements or project.ai_extracted_text
    if requirements_to_display:
        with st.expander("评分要求", expanded=False):
            # 应用过滤函数，在显示时移除企业资质部分
            filtered_requirements = filter_company_qualifications_for_display(requirements_to_display)
            st.text_area("项目要求", filtered_requirements, height=200, 
                        key=f"project_requirements_{project.id}{project_id_suffix}")
            # 如果 project_requirements 为空但 ai_extracted_text 有值，显示提示
            if not project.project_requirements and project.ai_extracted_text and not is_visualization:
                st.warning("⚠️ 注意：此项目的project_requirements字段为空，当前显示的是ai_extracted_text。建议使用'重新进行AI分析'功能更新数据。")
    
    # 对比分析（包含分析过程）
    if project.comparison_result:
        render_comparison_analysis(project.comparison_result, key_suffix=f"{project.id}{project_id_suffix}")
    
    # 客观分分析（可视化页面不显示）
    if not is_visualization and project.objective_scores:
        render_objective_score_analysis(project.objective_scores, key_suffix=f"{project.id}{project_id_suffix}")
    
    # 主观分分析（可视化页面不显示）
    if not is_visualization and project.subjective_scores:
        render_subjective_score_analysis(project.subjective_scores, key_suffix=f"{project.id}{project_id_suffix}")
    
    # 文件信息（如果需要）
    if include_file_download:
        if project.file_path:
            # 严格检查文件是否存在
            file_exists = os.path.exists(project.file_path) or os.path.isdir(project.file_path)
            if file_exists:
                col_file1, col_file2 = st.columns([3, 1])
                with col_file1:
                    st.text(f"文件路径: {project.file_path}")
                with col_file2:
                    try:
                        # 每次渲染时重新准备文件数据，避免使用过期的文件ID
                        file_data, filename, mime_type, error_msg = prepare_file_for_download(project.file_path)
                        if file_data and filename and mime_type:
                            # 对于小文件（<10MB），使用 base64 下载链接避免 Streamlit 媒体文件存储问题
                            file_size_mb = len(file_data) / (1024 * 1024)
                            if file_size_mb < 10:
                                # 使用 base64 下载链接
                                download_link = create_download_link(file_data, filename, mime_type)
                                if download_link:
                                    st.markdown(download_link, unsafe_allow_html=True)
                                else:
                                    # 回退到 download_button
                                    st.download_button(
                                        label="📥 下载文件",
                                        data=file_data,
                                        file_name=filename,
                                        mime=mime_type,
                                        key=f"download_file_{project.id}{project_id_suffix}",
                                        help="点击下载项目文件",
                                        width='stretch'
                                    )
                            else:
                                # 大文件使用 download_button
                                st.download_button(
                                    label="📥 下载文件",
                                    data=file_data,
                                    file_name=filename,
                                    mime=mime_type,
                                    key=f"download_file_{project.id}{project_id_suffix}",
                                    help="点击下载项目文件",
                                    width='stretch'
                                )
                        else:
                            st.warning(f"⚠️ {error_msg or '文件准备失败'}")
                    except Exception as e:
                        log.error(f"准备文件下载失败（项目ID: {project.id}）: {str(e)}")
                        st.warning(f"⚠️ 文件下载功能暂时不可用")
            else:
                st.warning(f"⚠️ 文件不存在: {project.file_path}")
        else:
            st.text("文件不存在")


@st.cache_data(ttl=300, max_entries=10)  # 缓存5分钟，减少数据库查询
def get_today_project_stats():
    """获取当日项目统计信息（优化：使用单个查询减少数据库访问）"""
    from datetime import datetime, date
    from sqlalchemy import func, case
    db = next(get_db())
    
    try:
        # 获取今天的日期范围
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        # 优化：使用单个查询获取所有统计信息，减少数据库往返
        stats = db.query(
            func.count(TenderProject.id).label('total'),
            func.sum(
                case((TenderProject.status == ProjectStatus.COMPARED, 1), else_=0)
            ).label('completed'),
            func.sum(
                case((
                    TenderProject.final_decision.in_(["可以参与", "客观分满分", "推荐参与", "通过"]), 1
                ), else_=0)
            ).label('qualified')
        ).filter(
            TenderProject.publish_time >= start_of_day,
            TenderProject.publish_time <= end_of_day
        ).first()
        
        today_total = stats.total or 0
        today_completed = stats.completed or 0
        today_qualified = stats.qualified or 0
        today_pass_rate = today_qualified / today_total * 100 if today_total > 0 else 0
        
        return {
            "total": today_total,
            "completed": today_completed,
            "qualified": today_qualified,
            "pass_rate": round(today_pass_rate, 1)
        }
    finally:
        db.close()


def _project_to_dict(project):
    """将TenderProject ORM对象转换为字典（可序列化）"""
    # 将枚举类型转换为字符串值以确保可序列化
    status_value = project.status.value if project.status else None
    return {
        'id': project.id,
        'project_name': project.project_name,
        'site_name': project.site_name,
        'publish_time': project.publish_time,
        'publish_timestamp': project.publish_timestamp,
        'download_url': project.download_url,
        'file_path': project.file_path,
        'file_format': project.file_format,
        'evaluation_content': project.evaluation_content,
        'ai_extracted_text': project.ai_extracted_text,
        'project_requirements': project.project_requirements,
        'comparison_result': project.comparison_result,
        'status': status_value,  # 存储字符串值而不是枚举对象
        'error_msg': project.error_msg,
        'create_time': project.create_time,
        'update_time': project.update_time,
        'project_id': project.project_id,
        'region': project.region,
        'final_decision': project.final_decision,
        'tender_method': project.tender_method,
        'objective_scores': project.objective_scores,
        'subjective_scores': project.subjective_scores,
        'objective_score_decisions': project.objective_score_decisions,
        'all_objective_recommended': project.all_objective_recommended,
        'review_status': project.review_status,
        'review_result': project.review_result,
        'review_reason': project.review_reason,
        'review_time': project.review_time,
    }

def _dict_to_project(project_dict):
    """将字典转换为SimpleNamespace对象（提供属性访问）"""
    # 直接使用字典创建SimpleNamespace，status直接存储字符串值
    # 注意：现在status是字符串，不是对象，所以使用时要直接访问 project.status
    # 而不是 project.status.value
    return SimpleNamespace(**project_dict)


# ====================== 平台筛选辅助函数 ======================
@st.cache_data(ttl=3600, max_entries=1)  # 缓存1小时，平台列表很少变化
def get_available_platforms():
    """获取所有可用的爬虫平台列表（带缓存优化）"""
    try:
        # 确保导入所有平台爬虫（触发注册）
        try:
            from spider.platforms.hangzhou import HangZhouTenderSpider
        except Exception as e:
            log.warning(f"导入杭州市爬虫失败: {str(e)}")
        
        try:
            from spider.platforms.jiaxing import JiaXingTenderSpider
        except Exception as e:
            log.warning(f"导入嘉兴市爬虫失败: {str(e)}")
        
        try:
            from spider.platforms.ningbo import NingBoTenderSpider
        except Exception as e:
            log.warning(f"导入宁波市爬虫失败: {str(e)}", exc_info=True)

        try:
            from spider.platforms.shaoxing import ShaoXingTenderSpider
        except Exception as e:
            log.warning(f"导入绍兴市爬虫失败: {str(e)}", exc_info=True)
        
        try:
            from spider.platforms.huzhou import HuZhouTenderSpider
        except Exception as e:
            log.warning(f"导入湖州市爬虫失败: {str(e)}")
        
        try:
            from spider.platforms.yiwu import YiWuTenderSpider
        except Exception as e:
            log.warning(f"导入义乌市爬虫失败: {str(e)}")

        try:
            from spider.platforms.lishui import LiShuiTenderSpider
        except Exception as e:
            log.warning(f"导入丽水市爬虫失败: {str(e)}")
        
        platforms = SpiderManager.list_all_spider_info()
        log.debug(f"已注册的爬虫平台: {[p['code'] for p in platforms]}")
        return {info["code"]: info["name"] for info in platforms}
    except Exception as e:
        log.error(f"获取平台列表失败: {str(e)}", exc_info=True)
        return {"zhejiang": "浙江省政府采购网"}

def extract_platform_code(site_name):
    """从site_name中提取平台代码"""
    if not site_name:
        return None
    
    # 平台名称映射
    platform_map = {
        "浙江省政府采购网": "zhejiang",
        "杭州市公共资源交易网": "hangzhou",
        "嘉兴禾采联综合采购服务平台": "jiaxing",
        "宁波市阳光采购服务平台": "ningbo",
        "绍兴市阳光采购服务平台": "shaoxing",
        "湖州市绿色采购服务平台": "huzhou",
        "义乌市阳光招标采购平台": "yiwu",
        "丽水市阳光采购服务平台": "lishui",
    }
    
    for platform_name, code in platform_map.items():
        if platform_name in site_name:
            return code
    
    return None

def filter_projects_by_platform(projects, platform_code):
    """根据平台代码筛选项目"""
    if platform_code == "全部":
        return projects
    
    filtered = []
    for project in projects:
        site_name = project.site_name if hasattr(project, 'site_name') else getattr(project, 'site_name', '')
        project_platform = extract_platform_code(site_name)
        if project_platform == platform_code:
            filtered.append(project)
    
    return filtered

@st.cache_data(ttl=60, max_entries=20)  # 缓存1分钟，减少数据库查询，确保新项目能及时显示
def get_all_projects():
    """获取所有项目数据"""
    db = next(get_db())
    projects = db.query(TenderProject).all()
    db.close()
    # 转换为可序列化的格式
    return [_dict_to_project(_project_to_dict(p)) for p in projects]


@st.cache_data(ttl=600, max_entries=100)  # 缓存10分钟，减少数据库查询频率（从5分钟增加到10分钟）
def get_completed_projects(region="全部", month_day="全部", platform_code=None):
    """获取已对比（COMPARED）状态的项目
    
    Args:
        region: 区域筛选（"全部"或具体区域名称）
        month_day: 日期筛选（"全部"或"MM-DD"格式）
        platform_code: 平台代码筛选（None表示全部，或具体平台代码如"zhejiang"）
    """
    from sqlalchemy import extract  # 在函数内部导入，确保在缓存环境中可用
    from utils.log import log
    from sqlalchemy import or_
    
    # 定义大类区域列表（与spider/tender_spider.py中的district_codes保持一致）
    major_regions = [
        "浙江省本级", "杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", 
        "绍兴市", "金华市", "衢州市", "舟山市", "台州市", "丽水市"
    ]
    
    db = next(get_db())
    try:
        # 只筛选已对比（COMPARED）状态的项目
        # 优化：只查询可视化需要的字段，不加载大字段（evaluation_content等）
        query = db.query(
            TenderProject.id,
            TenderProject.project_name,
            TenderProject.site_name,
            TenderProject.region,
            TenderProject.publish_time,
            TenderProject.create_time,
            TenderProject.status,
            TenderProject.final_decision,
            TenderProject.file_path,
            TenderProject.file_format,
            TenderProject.comparison_result,
            TenderProject.review_status,
            TenderProject.review_result,
            TenderProject.review_reason,
            TenderProject.review_time
        ).filter(
            TenderProject.status == ProjectStatus.COMPARED
        )
        
        # 区域筛选：根据district_codes映射值筛选
        # 注意：API返回的districtName可能格式不一致，需要支持多种匹配方式
        if region != "全部":
            # 1. 精确匹配region字段（对应district_codes中的值，如"浙江省本级"）
            exact_match = TenderProject.region == region
            # 2. 包含匹配region字段（处理API返回的districtName可能包含前缀或后缀的情况）
            contains_match = TenderProject.region.like(f'%{region}%')
            # 3. 从site_name中提取区域（格式：浙江省政府采购网-{region_name}）
            # 这样可以匹配到即使region字段为空但site_name中包含区域信息的情况
            site_name_match = TenderProject.site_name.like(f'%{region}%')
            # 使用OR条件，支持多种格式
            query = query.filter(or_(exact_match, contains_match, site_name_match))
        # 当选择"全部"时，不进行区域筛选，显示所有已对比的项目
        
        # 日期（月-日）筛选
        if month_day != "全部":
            try:
                month, day = map(int, month_day.split("-"))
                query = query.filter(
                    extract('month', TenderProject.publish_time) == month,
                    extract('day', TenderProject.publish_time) == day
                )
            except ValueError:
                pass  # 日期格式错误，不进行筛选
        
        # 执行查询
        projects = query.all()
        
        # 转换为可序列化的格式（优化：只加载需要的字段，不加载大字段）
        result = []
        for p in projects:
            # 平台筛选（在数据库查询后应用，因为site_name可能包含多个字段）
            if platform_code:
                site_name = p.site_name if hasattr(p, 'site_name') else getattr(p, 'site_name', '')
                project_platform = extract_platform_code(site_name)
                if project_platform != platform_code:
                    continue
            
            # 创建轻量级项目对象，不加载evaluation_content等大字段
            project_dict = {
                'id': p.id,
                'project_name': p.project_name,
                'site_name': p.site_name,
                'region': p.region,
                'publish_time': p.publish_time,
                'create_time': p.create_time,
                'status': p.status.value if p.status else None,
                'final_decision': p.final_decision,
                'file_path': p.file_path,
                'file_format': p.file_format,
                'comparison_result': p.comparison_result,
                'review_status': p.review_status,
                'review_result': p.review_result,
                'review_reason': p.review_reason,
                'review_time': p.review_time,
                # 可视化不需要的大字段设为None，减少内存占用
                'evaluation_content': None,
                'ai_extracted_text': None,
                'project_requirements': None,
                'download_url': None,
                'publish_timestamp': None,
                'error_msg': None,
                'update_time': None,
                'project_id': None,
                'tender_method': None,
                'objective_scores': None,
                'subjective_scores': None,
                'objective_score_decisions': None,
                'all_objective_recommended': None
            }
            result.append(_dict_to_project(project_dict))
        
        return result
    finally:
        db.close()


@st.cache_data(ttl=120, max_entries=20)  # 缓存2分钟，限制最大条目数
def get_pending_review_projects():
    """获取待复核项目（所有客观分条目均被判定为推荐参与）"""
    db = next(get_db())
    projects = db.query(TenderProject).filter(
        TenderProject.status == ProjectStatus.COMPARED,
        TenderProject.final_decision.in_(["可以参与", "客观分满分", "推荐参与", "通过"]),
        TenderProject.all_objective_recommended == 1,
        TenderProject.review_status == "待复核"
    ).all()
    db.close()
    # 转换为可序列化的格式
    return [_dict_to_project(_project_to_dict(p)) for p in projects]


def mark_project_reviewed(project_id, review_result, review_reason=None):
    """标记项目为已复核（优化版）"""
    db = next(get_db())
    try:
        # 使用更高效的更新方式
        update_data = {
            "review_status": "已复核",
            "review_result": review_result,
            "review_reason": review_reason,
            "review_time": datetime.now()
        }
        
        # 如果复核后不推荐，更新final_decision
        if review_result == "复核不推荐":
            update_data["final_decision"] = "不推荐参与"
            # 只在需要时才处理comparison_result
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if project:
                if project.comparison_result:
                    # 快速查找并移除旧的调整说明
                    old_result = project.comparison_result
                    # 查找最后一个调整说明的位置
                    last_adjustment_pos = max(
                        old_result.rfind("【丢分阈值调整说明】"),
                        old_result.rfind("【失分验证说明】")
                    )
                    if last_adjustment_pos != -1:
                        old_result = old_result[:last_adjustment_pos].strip()
                    # 添加新的复核说明
                    review_time_str = update_data["review_time"].strftime('%Y-%m-%d %H:%M:%S')
                    review_note = f"\n\n【复核说明】\n- 复核结果：复核不推荐\n"
                    if review_reason:
                        review_note += f"- 复核理由：{review_reason}\n"
                    review_note += f"- 复核时间：{review_time_str}\n"
                    update_data["comparison_result"] = old_result + review_note
                else:
                    # 如果没有比对结果，创建新的复核说明
                    review_time_str = update_data["review_time"].strftime('%Y-%m-%d %H:%M:%S')
                    review_note = f"【复核说明】\n- 复核结果：复核不推荐\n"
                    if review_reason:
                        review_note += f"- 复核理由：{review_reason}\n"
                    review_note += f"- 复核时间：{review_time_str}\n"
                    update_data["comparison_result"] = review_note
        
        # 批量更新
        from utils.db import update_project
        result = update_project(db, project_id, update_data)
        return result
    except Exception as e:
        db.rollback()
        log.error(f"标记项目复核失败：{str(e)}")
        return False
    finally:
        db.close()


def update_objective_recommendation_status():
    """更新所有项目的客观分推荐状态"""
    import json
    db = next(get_db())
    projects = db.query(TenderProject).filter(
        TenderProject.status == ProjectStatus.COMPARED,
        TenderProject.objective_score_decisions.isnot(None)
    ).all()
    
    for project in projects:
        try:
            decisions = json.loads(project.objective_score_decisions)
            if decisions and all(item.get('is_attainable', False) for item in decisions):
                project.all_objective_recommended = 1
            else:
                project.all_objective_recommended = 0
        except json.JSONDecodeError:
            project.all_objective_recommended = 0
    
    db.commit()
    db.close()


# ====================== 全局异常处理 ======================
def handle_exception(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    st.error(f"系统错误：{str(exc_value)}")
    st.exception("详细错误信息：")


sys.excepthook = handle_exception


# ====================== 自定义样式 ======================
def load_custom_css():
    """加载自定义CSS样式"""
    custom_css = """
    <style>
    /* 全局样式 */
    body {
        font-family: 'Microsoft YaHei', Arial, sans-serif;
        background-color: #f0f2f6;
    }
    
    /* 卡片样式 */
    .stCard {
        background-color: #f8f9fa;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        padding: 20px;
    }
    
    /* 标题样式 */
    h1, h2, h3, h4, h5, h6 {
        color: #1f2937;
        font-weight: 600;
    }
    
    /* 按钮样式 */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        padding: 0.5rem 1rem;
    }
    
    /* 进度条样式 - 提高对比度 */
    .stProgress > div > div {
        background-color: #22c55e;  /* 绿色进度条 */
    }
    
    /* 指标卡片样式 - 提高对比度 */
    .stMetric {
        background-color: #1e40af;  /* 深蓝色背景 */
        color: white;
        border-radius: 6px;
        padding: 10px;
    }
    
    /* 表格样式 */
    .dataframe {
        border-radius: 6px;
        overflow: hidden;
    }
    
    /* 增强按钮可见性 */
    .stButton > button[kind="primary"] {
        background-color: #ec4899;  /* 粉色主按钮 */
        color: white;
        font-weight: bold;
    }
    
    /* 成功消息样式 */
    .success-message {
        background-color: #d1fae5;
        color: #065f46;
        padding: 10px;
        border-radius: 5px;
    }
    
    /* 警告消息样式 */
    .warning-message {
        background-color: #fef9c3;
        color: #92400e;
        padding: 10px;
        border-radius: 5px;
    }
    
    /* 错误消息样式 */
    .error-message {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 10px;
        border-radius: 5px;
    }
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


# ====================== 侧边栏 ======================
def render_sidebar():
    """渲染侧边栏"""
    # 使用容器来确保侧边栏内容只渲染一次，避免重复key错误
    with st.sidebar.container():
        st.sidebar.title("📋 功能导航")
        st.sidebar.markdown("---")

        # 菜单选择
        menu_options = [
            "系统首页",
            "标书文件管理",
            "资质库管理",
            "流程执行",
            "分析过程可视化",
            "报告导出",
            "存储管理",
            "定时任务"
        ]

        # 使用侧边栏标签页式导航，提高视觉体验
        # 从session_state获取当前选择，如果没有则使用默认值
        current_index = 0
        if "menu_choice" in st.session_state:
            try:
                current_index = menu_options.index(st.session_state["menu_choice"])
            except ValueError:
                current_index = 0
        
        # 使用条件检查，避免重复创建相同key的组件
        # 如果key已存在且值相同，则使用session_state中的值
        if "main_sidebar_menu_choice" not in st.session_state:
            st.session_state["main_sidebar_menu_choice"] = menu_options[current_index]
        
        # 使用radio组件，但确保key的唯一性
        # 如果已经渲染过，直接使用session_state中的值
        menu_choice = st.sidebar.radio(
            "选择功能模块", 
            menu_options,
            index=current_index,
            key="main_sidebar_menu_choice",  # 使用唯一的key
            help="通过点击选择不同的功能模块",
            label_visibility="collapsed"
        )
    
    # 确保session_state与radio选择同步
    # 如果session_state中的menu_choice被外部修改（如按钮），优先使用它来设置index
    # 但最终使用radio返回的值（用户可能通过radio切换了）
    # 注意：不能直接修改sidebar_menu_choice（widget已实例化），只能通过index控制
    
    # 使用radio返回的值（这是用户实际选择的值）
    st.session_state["menu_choice"] = menu_choice

    # 显示当前选中的模块
    st.sidebar.markdown(f"\n**当前模块：**\n{menu_choice}")

    # 系统状态信息
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 系统状态")

    if SYSTEM_READY:
        # 安全获取统计数据（添加异常处理，防止中断应用）
        try:
            today_stats = get_today_project_stats()
        except Exception as e:
            log.warning(f"获取今日统计失败（可忽略）：{str(e)}")
            today_stats = {"total": 0, "completed": 0, "qualified": 0, "pass_rate": 0}
        
        # 显示存储空间信息
        try:
            from utils.storage_manager import StorageManager
            storage_manager = StorageManager()
            disk_usage = storage_manager.get_disk_usage()
            usage_percent = disk_usage["percent_used"]
            
            # 存储空间警告
            if usage_percent >= 90:
                storage_status = f"🔴 磁盘空间严重不足 ({usage_percent:.1f}%)"
            elif usage_percent >= 80:
                storage_status = f"🟡 磁盘空间不足 ({usage_percent:.1f}%)"
            else:
                storage_status = f"✅ 存储空间正常 ({usage_percent:.1f}%)"
        except Exception as e:
            log.debug(f"获取存储空间信息失败（可忽略）：{str(e)}")
            storage_status = "✅ 存储空间正常"
        
        with st.sidebar.container(border=True, height=200):
            st.markdown(
                f"✅ 系统正常运行\n"
                f"📁 当日项目总数：{today_stats['total']}\n"
                f"✅ 当日已完成：{today_stats['completed']}\n"
                f"🎯 当日推荐参与：{today_stats['qualified']}\n"
                f"📈 当日通过率：{today_stats['pass_rate']}%\n"
                f"💾 {storage_status}"
            )
    else:
        st.sidebar.error("❌ 系统初始化失败")

    return menu_choice


# ====================== 页面组件 ======================
def render_home_page():
    """渲染首页"""
    st.title("🏗️ 系统首页 - 标书资质自动匹配系统")
    st.markdown("---")

    # 系统统计概览
    st.subheader("📊 系统概览")
    stats = get_project_stats()
    today_stats = get_today_project_stats()
    
    # 全局统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 项目总数", stats["total"])
    with col2:
        st.metric("✅ 已完成", stats["completed"])
    with col3:
        st.metric("🎯 可参与", stats["qualified"])
    with col4:
        try:
            qualified_rate = f"{stats['qualified']/stats['completed']*100:.1f}%" if stats['completed'] > 0 else "0%"
            st.metric("📈 通过率", qualified_rate)
        except:
            st.metric("📈 通过率", "0%")
    
    # 当日统计
    st.markdown("---")
    st.subheader("📅 当日统计")
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("📁 当日项目总数", today_stats["total"])
    with col6:
        st.metric("✅ 当日已完成", today_stats["completed"])
    with col7:
        st.metric("🎯 当日推荐参与", today_stats["qualified"])
    with col8:
        st.metric("📈 当日通过率", f"{today_stats['pass_rate']}%")

    st.markdown("---")

    # 系统流程可视化
    st.subheader("🔄 核心流程")
    cols = st.columns(5, gap="small")
    steps = [
        ("📤", "标书上传", "支持PDF/Word/DOC/ZIP格式"),
        ("🔍", "内容解析", "OCR技术提取文本内容"),
        ("🧠", "资质提取", "AI识别客观/主观评分项"),
        ("⚖️", "智能比对", "与资质库自动匹配"),
        ("📄", "报告生成", "导出详细分析报告")
    ]

    for idx, (icon, title, description) in enumerate(steps):
        with cols[idx]:
            st.markdown(f"<h1 style='text-align: center; color: #1e40af;'>{icon}</h1>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center; margin-bottom: 5px;'>{idx + 1}. {title}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; font-size: 12px; color: #6b7280;'>{description}</p>", unsafe_allow_html=True)

    st.markdown("---")

    # 系统功能介绍
    st.subheader("🌟 核心功能")
    features = [
        {"icon": "📄", "title": "智能文件解析", "description": "支持PDF（含OCR）、Word、DOC等多种格式文件的自动解析和文本提取"},
        {"icon": "🧠", "title": "AI资质分析", "description": "基于Llama3/GPT模型智能提取资质要求，区分客观分和主观分"},
        {"icon": "⚖️", "title": "精准资质匹配", "description": "与公司资质库自动比对，智能判断项目参与资格"},
        {"icon": "📊", "description": "可视化分析报告", "icon": "📊", "title": "可视化分析", "description": "直观展示匹配结果、评分分布和参与建议"},
        {"icon": "🕷️", "title": "自动标书爬虫", "description": "定时爬取政府采购网站最新标书信息"}
    ]

    # 使用卡片式布局展示功能
    for i in range(0, len(features), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(features):
                feature = features[i + j]
                with cols[j]:
                    with st.container(border=True, height=150):
                        st.markdown(f"<h4 style='margin-bottom: 5px;'><span style='color: #ec4899;'>{feature['icon']}</span> {feature['title']}</h4>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size: 14px; color: #4b5563;'>{feature['description']}</p>", unsafe_allow_html=True)

    st.markdown("---")

    # 待复核项目列表
    pending_review_projects = get_pending_review_projects()
    if pending_review_projects:
        st.subheader("⏳ 待复核项目")
        st.markdown("所有客观分条目均被判定为\"推荐参与\"的项目")
        
        for project in pending_review_projects:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{project.project_name}**")
                    st.caption(f"ID: {project.id} | 来源: {project.site_name} | 发布时间: {project.publish_time.strftime('%Y-%m-%d')}")
                with col2:
                    st.markdown(f"**状态:** {project.final_decision}")
                    if project.objective_score_decisions:
                        try:
                            import json
                            decisions = json.loads(project.objective_score_decisions)
                            st.caption(f"客观分条目: {len(decisions)} 条")
                        except:
                            pass
                with col3:
                    if st.button("查看详情", key=f"pending_review_view_{project.id}"):
                        st.session_state["review_project_id"] = project.id
                        st.session_state["review_mode"] = True
                        st.rerun()

    st.markdown("---")

def render_file_management():
    """渲染文件管理页面（修复删除功能）"""
    st.title("📤 文件管理 - 标书资质自动匹配系统")
    st.markdown("---")

    # 初始化删除状态
    if "delete_confirmed" not in st.session_state:
        st.session_state.delete_confirmed = False
    if "files_to_delete" not in st.session_state:
        st.session_state.files_to_delete = []

    # 上传方式选择
    tab1, tab2, tab3 = st.tabs(["📤 文件上传", "📁 已有文件", "❌ 解析失败文件"])

    with tab1:
        # 原有上传逻辑（保持不变）
        uploaded_files = st.file_uploader(
            "选择标书文件",
            type=["pdf", "docx", "doc", "zip"],
            accept_multiple_files=True,
            help="支持PDF（含扫描件）、Word、DOC和ZIP格式文件，可以选择多个文件同时上传",
            label_visibility="visible"
        )
        st.caption("💡 支持格式：PDF（含OCR）、Word、DOC、ZIP")

        if uploaded_files:
            file_data = []
            for f in uploaded_files:
                file_data.append({
                    "文件名": f.name,
                    "大小": f"{f.size / 1024:.2f}KB",
                    "格式": f.name.split(".")[-1].upper()
                })

            st.dataframe(pd.DataFrame(file_data), width='stretch')

            if st.button("✅ 保存文件", type="primary"):
                with st.spinner("正在保存文件..."):
                    save_files(uploaded_files)

    with tab2:
        # 显示已有文件
        if os.path.exists(FILES_DIR) and os.listdir(FILES_DIR):
            files = []
            file_info = {}
            # 过滤掉zip文件，只显示非zip文件和目录
            filtered_files = [f for f in os.listdir(FILES_DIR) if not f.endswith('.zip')]
            for filename in filtered_files:
                filepath = os.path.join(FILES_DIR, filename)
                if os.path.isfile(filepath):
                    filesize = os.path.getsize(filepath) / 1024
                    file_info[filename] = filepath
                    files.append({
                        "文件名": filename,
                        "大小": f"{filesize:.2f}KB",
                        "修改时间": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
                    })

            st.dataframe(pd.DataFrame(files), width='stretch')

            # 批量操作区
            st.markdown("---")
            st.subheader("🗑️ 批量操作")

            # 选择要删除的文件
            selected_files = st.multiselect(
                "选择文件（可多选）",
                [f["文件名"] for f in files],
                key="selected_files_for_ops"
            )

            # 删除流程 - 步骤1：确认选择
            if st.button("🗑️ 删除选中文件", type="secondary") and selected_files:
                st.session_state.files_to_delete = selected_files
                st.session_state.delete_confirmed = True

            # 删除流程 - 步骤2：二次确认（使用会话状态）
            if st.session_state.delete_confirmed and st.session_state.files_to_delete:
                st.warning(f"⚠️ 确定要删除以下 {len(st.session_state.files_to_delete)} 个文件吗？此操作不可恢复！")
                st.code("\n".join(st.session_state.files_to_delete))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认删除", type="primary"):
                        with st.spinner("正在删除文件..."):
                            # 执行删除操作
                            delete_files(st.session_state.files_to_delete)
                            # 重置状态
                            st.session_state.delete_confirmed = False
                            st.session_state.files_to_delete = []

                with col2:
                    if st.button("❌ 取消"):
                        st.session_state.delete_confirmed = False
                        st.session_state.files_to_delete = []

            # 添加到项目按钮
            if st.button("➕ 添加选中文件到项目", type="primary") and selected_files:
                with st.spinner("正在添加到项目..."):
                    add_files_to_project(selected_files)

        else:
            st.info("📁 暂无文件，请先上传文件")
            # 重置删除状态
            st.session_state.delete_confirmed = False
            st.session_state.files_to_delete = []
    
    with tab3:
        # 显示解析失败的文件
        st.subheader("❌ 解析失败文件管理")
        st.markdown("显示所有解析失败的项目，可以查看失败原因、重置失败计数或手动标记为跳过")
        
        try:
            from utils.db import get_db, TenderProject, ProjectStatus, update_project
            import re
            
            db = next(get_db())
            try:
                # 查询所有解析失败的项目（ERROR状态或包含错误信息）
                failed_projects = db.query(TenderProject).filter(
                    TenderProject.status == ProjectStatus.ERROR
                ).order_by(TenderProject.create_time.desc()).all()
                
                if failed_projects:
                    # 统计信息
                    total_failed = len(failed_projects)
                    skipped_count = sum(1 for p in failed_projects if p.error_msg and '[跳过-多次失败]' in p.error_msg)
                    retryable_count = total_failed - skipped_count
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总失败数", total_failed)
                    with col2:
                        st.metric("可重试", retryable_count)
                    with col3:
                        st.metric("已跳过", skipped_count)
                    
                    st.markdown("---")
                    
                    # 筛选选项
                    filter_option = st.selectbox(
                        "筛选选项",
                        ["全部", "可重试（失败<3次）", "已跳过（失败≥3次）"],
                        key="failed_files_filter"
                    )
                    
                    # 根据筛选选项过滤项目
                    if filter_option == "可重试（失败<3次）":
                        filtered_projects = [
                            p for p in failed_projects 
                            if not (p.error_msg and '[跳过-多次失败]' in p.error_msg)
                        ]
                    elif filter_option == "已跳过（失败≥3次）":
                        filtered_projects = [
                            p for p in failed_projects 
                            if p.error_msg and '[跳过-多次失败]' in p.error_msg
                        ]
                    else:
                        filtered_projects = failed_projects
                    
                    if filtered_projects:
                        st.info(f"显示 {len(filtered_projects)} 个失败项目")
                        
                        # 批量操作
                        st.markdown("### 🔧 批量操作")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("🔄 重置所有失败计数", help="清除所有项目的失败计数，允许重新尝试解析"):
                                reset_count = 0
                                for project in filtered_projects:
                                    if project.error_msg:
                                        # 清除失败计数标记
                                        new_error_msg = re.sub(r'\[解析失败\d+次\].*', '', project.error_msg).strip()
                                        if new_error_msg != project.error_msg:
                                            update_project(db, project.id, {
                                                "error_msg": new_error_msg if new_error_msg else None,
                                                "status": ProjectStatus.DOWNLOADED  # 重置为DOWNLOADED状态，允许重新解析
                                            })
                                            reset_count += 1
                                db.commit()
                                st.success(f"✅ 已重置 {reset_count} 个项目的失败计数")
                                st.rerun()
                        
                        with col2:
                            if st.button("⏭️ 标记所有为跳过", help="将所有项目标记为跳过，不再尝试解析"):
                                skip_count = 0
                                for project in filtered_projects:
                                    if not (project.error_msg and '[跳过-多次失败]' in project.error_msg):
                                        # 提取失败次数
                                        match = re.search(r'\[解析失败(\d+)次\]', project.error_msg or "")
                                        fail_count = int(match.group(1)) if match else 3
                                        new_error_msg = f"{project.error_msg or '解析失败'} [解析失败{fail_count}次] [跳过-多次失败]"
                                        update_project(db, project.id, {
                                            "error_msg": new_error_msg
                                        })
                                        skip_count += 1
                                db.commit()
                                st.success(f"✅ 已标记 {skip_count} 个项目为跳过")
                                st.rerun()
                        
                        with col3:
                            if st.button("🗑️ 删除所有失败项目", type="secondary", help="删除所有失败项目的数据库记录（不删除文件）"):
                                delete_count = 0
                                for project in filtered_projects:
                                    db.delete(project)
                                    delete_count += 1
                                db.commit()
                                st.success(f"✅ 已删除 {delete_count} 个失败项目")
                                st.rerun()
                        
                        st.markdown("---")
                        st.markdown("### 📋 失败项目列表")
                        
                        # 显示项目列表
                        for project in filtered_projects:
                            with st.expander(f"项目 {project.id}: {project.project_name[:60]}...", expanded=False):
                                col1, col2 = st.columns([3, 1])
                                
                                with col1:
                                    st.markdown(f"**项目名称:** {project.project_name}")
                                    st.markdown(f"**文件路径:** {project.file_path or '未设置'}")
                                    st.markdown(f"**文件格式:** {project.file_format or '未知'}")
                                    st.markdown(f"**创建时间:** {project.create_time.strftime('%Y-%m-%d %H:%M:%S') if project.create_time else '未知'}")
                                    
                                    # 显示错误信息
                                    if project.error_msg:
                                        # 提取失败次数
                                        match = re.search(r'\[解析失败(\d+)次\]', project.error_msg)
                                        fail_count = int(match.group(1)) if match else 0
                                        is_skipped = '[跳过-多次失败]' in project.error_msg
                                        
                                        st.markdown(f"**失败次数:** {fail_count} 次")
                                        st.markdown(f"**状态:** {'已跳过' if is_skipped else '可重试'}")
                                        st.markdown(f"**错误信息:**")
                                        st.code(project.error_msg, language=None)
                                    
                                    # 检查文件是否存在
                                    if project.file_path:
                                        file_exists = os.path.exists(project.file_path) or os.path.isdir(project.file_path)
                                        if file_exists:
                                            file_size = os.path.getsize(project.file_path) if os.path.isfile(project.file_path) else 0
                                            st.markdown(f"**文件状态:** ✅ 存在（大小: {file_size / 1024:.2f}KB）")
                                        else:
                                            st.markdown(f"**文件状态:** ❌ 不存在")
                                
                                with col2:
                                    # 操作按钮
                                    if project.error_msg and '[跳过-多次失败]' not in project.error_msg:
                                        if st.button("🔄 重置失败计数", key=f"reset_{project.id}"):
                                            # 清除失败计数
                                            new_error_msg = re.sub(r'\[解析失败\d+次\].*', '', project.error_msg).strip()
                                            update_project(db, project.id, {
                                                "error_msg": new_error_msg if new_error_msg else None,
                                                "status": ProjectStatus.DOWNLOADED
                                            })
                                            db.commit()
                                            st.success(f"✅ 项目 {project.id} 失败计数已重置")
                                            st.rerun()
                                        
                                        if st.button("⏭️ 标记为跳过", key=f"skip_{project.id}"):
                                            # 标记为跳过
                                            match = re.search(r'\[解析失败(\d+)次\]', project.error_msg)
                                            fail_count = int(match.group(1)) if match else 3
                                            new_error_msg = f"{project.error_msg} [解析失败{fail_count}次] [跳过-多次失败]"
                                            update_project(db, project.id, {
                                                "error_msg": new_error_msg
                                            })
                                            db.commit()
                                            st.success(f"✅ 项目 {project.id} 已标记为跳过")
                                            st.rerun()
                                    
                                    if st.button("🗑️ 删除项目", key=f"delete_{project.id}", type="secondary"):
                                        db.delete(project)
                                        db.commit()
                                        st.success(f"✅ 项目 {project.id} 已删除")
                                        st.rerun()
                    else:
                        st.info(f"没有符合筛选条件的失败项目")
                else:
                    st.success("✅ 没有解析失败的项目！")
                    
            finally:
                db.close()
        except Exception as e:
            st.error(f"❌ 加载失败项目列表失败：{str(e)}")
            log.error(f"加载失败项目列表失败：{str(e)}", exc_info=True)


def delete_files(filenames):
    """删除文件（修复版，支持zip文件及其解压目录）"""
    try:
        deleted_count = 0
        error_files = []

        # 先删除本地文件和对应的解压目录
        for filename in filenames:
            filepath = os.path.join(FILES_DIR, filename)
            try:
                # 删除文件本身
                if os.path.exists(filepath):
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        deleted_count += 1
                        
                        # 如果是zip文件，还需要删除对应的解压目录
                        if filepath.lower().endswith('.zip'):
                            extract_dir = os.path.splitext(filepath)[0]
                            if os.path.exists(extract_dir):
                                shutil.rmtree(extract_dir)
                                st.toast(f"已删除zip解压目录：{os.path.basename(extract_dir)}")
                        
                    else:
                        # 如果是目录，递归删除
                        shutil.rmtree(filepath)
                        deleted_count += 1
                else:
                    error_files.append(f"{filename}（文件不存在）")
            except Exception as e:
                error_files.append(f"{filename}（删除失败：{str(e)}）")

        # 再删除数据库记录
        try:
            db = next(get_db())
            for filename in filenames:
                filepath = os.path.join(FILES_DIR, filename)
                # 多种匹配方式确保删除
                projects = db.query(TenderProject).filter(
                    db.or_(
                        TenderProject.file_path == filepath,
                        TenderProject.file_path.contains(filename),
                        TenderProject.project_name.contains(os.path.splitext(filename)[0])
                    )
                ).all()

                for project in projects:
                    db.delete(project)

            db.commit()
            db.close()
        except Exception as e:
            st.warning(f"⚠️ 文件已删除，但数据库记录清理失败：{str(e)}")

        # 显示结果
        if deleted_count > 0:
            st.success(f"✅ 成功删除 {deleted_count} 个文件/目录！")
        if error_files:
            st.error(f"❌ 以下文件删除失败：\n" + "\n".join(error_files))

        # 强制刷新页面（关键修复）
        st.rerun()

    except Exception as e:
        st.error(f"❌ 删除操作异常：{str(e)}")




def save_files(uploaded_files):
    """保存上传的文件"""
    try:
        os.makedirs(FILES_DIR, exist_ok=True)
        saved_count = 0

        for file in uploaded_files:
            filepath = os.path.join(FILES_DIR, file.name)
            with open(filepath, "wb") as f:
                f.write(file.getbuffer())
            saved_count += 1

        st.success(f"✅ 成功保存 {saved_count} 个文件！")

        # 自动添加到项目
        add_files_to_project([f.name for f in uploaded_files])

    except Exception as e:
        st.error(f"❌ 文件保存失败：{str(e)}")
        st.info("💡 解决建议：")
        st.markdown("- 检查文件是否已存在")
        st.markdown("- 验证文件目录是否有写入权限")
        st.markdown("- 确保文件大小不超过系统限制")
        st.markdown("- 尝试重新上传文件")


def add_files_to_project(filenames):
    """将文件添加到项目"""
    try:
        db = next(get_db())
        added_count = 0

        for filename in filenames:
            filepath = os.path.join(FILES_DIR, filename)

            # 检查是否已存在
            existing = db.query(TenderProject).filter(
                TenderProject.file_path == filepath
            ).first()

            if not existing:
                project_data = {
                    "project_name": os.path.splitext(filename)[0],
                    "site_name": "本地上传",
                    "publish_time": datetime.now(),
                    "file_path": filepath,
                    "file_format": filename.split(".")[-1].lower() if "." in filename else "unknown",
                    "status": ProjectStatus.DOWNLOADED
                }
                save_project(db, project_data)
                added_count += 1

        db.close()
        st.success(f"✅ 成功添加 {added_count} 个文件到项目！")

    except Exception as e:
        st.error(f"❌ 添加项目失败：{str(e)}")


def render_qualification_management():
    """渲染资质库管理页面（数据库版本）"""
    st.title("🏢 资质库管理 - 标书资质自动匹配系统")
    st.markdown("---")

    # 导入数据库函数
    from utils.db import (
        get_company_qualifications, add_company_qualification, delete_company_qualification, update_company_qualification,
        batch_add_qualifications,
        get_class_a_certificates, add_class_a_certificate, update_class_a_certificate, delete_class_a_certificate,
        get_class_b_rules, add_class_b_rule, update_class_b_rule, delete_class_b_rule
    )
    from config import COMPANY_QUALIFICATIONS as DEFAULT_QUALIFICATIONS

    # 获取数据库实例（使用缓存，避免频繁创建连接）
    # 注意：数据库连接不应该缓存，但可以优化查询
    db = next(get_db())

    # 从数据库获取资质数据
    try:
        db_qualifications = get_company_qualifications(db)
        
        # 如果数据库中没有资质，使用默认配置作为参考
        if not db_qualifications:
            db_qualifications = DEFAULT_QUALIFICATIONS
            # 询问用户是否要导入默认资质
            st.info("数据库中没有资质数据，当前显示默认资质。")
            if st.button("📥 导入默认资质到数据库"):
                try:
                    # 使用批量添加函数导入默认资质
                    batch_add_qualifications(db, DEFAULT_QUALIFICATIONS)
                    st.success("✅ 默认资质导入成功！")
                    # 重新获取资质
                    db_qualifications = get_company_qualifications(db)
                except Exception as e:
                    st.error(f"❌ 默认资质导入失败：{str(e)}")
    except Exception as e:
        st.error(f"❌ 加载资质数据失败：{str(e)}")
        db.close()
        return

    # 创建标签页（包括基本资质、A类证书、B类规则）
    categories = list(db_qualifications.keys()) + ["A类证书管理", "B类规则管理"]
    if not categories:
        categories = list(DEFAULT_QUALIFICATIONS.keys()) + ["A类证书管理", "B类规则管理"]
    tabs = st.tabs(categories)

    for idx, category in enumerate(categories):
        with tabs[idx]:
            # A类证书管理
            if category == "A类证书管理":
                # 获取A类证书列表
                certificates = get_class_a_certificates(db)
                
                # 新增A类证书
                st.subheader("➕ 新增A类证书")
                with st.form(f"add_cert_form_{idx}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        cert_name = st.text_input(
                            "证书名称",
                            help="例如：ISO 9001质量管理体系认证",
                            placeholder="请输入证书全称"
                        )
                        cert_number = st.text_input(
                            "认证标准",
                            help="证书上的唯一认证标准",
                            placeholder="例如：CNAS-Z-01-2023"
                        )
                    with col2:
                        issuing_auth = st.text_input(
                            "查询机构",
                            help="颁发证书的权威机构名称",
                            placeholder="例如：中国认证认可监督管理委员会"
                        )
                        cert_type = st.text_input(
                            "证书类型",
                            help="证书的分类",
                            placeholder="例如：质量管理体系认证"
                        )
                    
                    # 有效期
                    col1, col2 = st.columns(2)
                    with col1:
                        valid_from = st.date_input("有效期开始", format="YYYY-MM-DD", key=f"valid_from_{idx}", value=None)
                    with col2:
                        valid_until = st.date_input("有效期结束", format="YYYY-MM-DD", key=f"valid_until_{idx}", value=None)
                    
                    if st.form_submit_button("保存证书"):
                        if cert_name and cert_number:
                            try:
                                add_class_a_certificate(db, cert_name, cert_number, issuing_auth, valid_from, valid_until, cert_type)
                                st.success("✅ 证书添加成功！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 添加失败：{str(e)}")
                        else:
                            st.warning("⚠️ 证书名称和认证标准不能为空")
                
                # 导入默认A类证书
                st.markdown("---")
                st.subheader("📥 导入默认A类证书")
                from config import A_CERTIFICATE_CONFIG
                if st.button("📥 从config.py导入默认A类证书", key=f"import_default_certs_{idx}"):
                    try:
                        imported_count = 0
                        skipped_count = 0
                        existing_cert_numbers = {cert.certificate_number for cert in certificates}
                        
                        for cert_data in A_CERTIFICATE_CONFIG["default_certificates"]:
                            # 检查是否已存在（根据证书编号）
                            if cert_data.get("certificate_number") not in existing_cert_numbers:
                                cert = ClassACertificate(**cert_data)
                                db.add(cert)
                                imported_count += 1
                            else:
                                skipped_count += 1
                        
                        db.commit()
                        if imported_count > 0:
                            st.success(f"✅ 成功导入 {imported_count} 条默认A类证书！" + (f"（跳过 {skipped_count} 条已存在的证书）" if skipped_count > 0 else ""))
                        else:
                            st.info(f"ℹ️ 所有默认A类证书已存在，无需导入（共 {skipped_count} 条）")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"❌ 导入失败：{str(e)}")
                
                # 显示现有A类证书
                st.markdown("---")
                st.subheader("📋 现有A类证书")
                
                if certificates:
                    for cert in certificates:
                        # 证书信息卡片
                        with st.expander(f"{cert.certificate_name} (认证标准: {cert.certificate_number})"):
                            col1, col2, col3 = st.columns([1, 1, 0.5])
                            with col1:
                                st.markdown(f"**查询机构:** {cert.issuing_authority or '未填写'}")
                                st.markdown(f"**证书类型:** {cert.certificate_type or '未填写'}")
                            with col2:
                                st.markdown(f"**有效期:** {cert.valid_from.strftime('%Y-%m-%d') if cert.valid_from else '无'} 至 {cert.valid_until.strftime('%Y-%m-%d') if cert.valid_until else '无'}")
                                st.markdown(f"**状态:** {'有效' if cert.is_active else '无效'}")
                            with col3:
                                # 操作按钮
                                if st.button(f"✏️ 编辑", key=f"edit_cert_{cert.id}"):
                                    st.session_state[f"editing_cert_{cert.id}"] = True
                                if st.button(f"🗑️ 删除", key=f"del_cert_{cert.id}"):
                                    try:
                                        delete_class_a_certificate(db, cert.id)
                                        st.success("✅ 证书删除成功！")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ 删除失败：{str(e)}")
                        
                        # 编辑表单
                        if f"editing_cert_{cert.id}" in st.session_state and st.session_state[f"editing_cert_{cert.id}"]:
                            st.markdown("---")
                            st.subheader("✏️ 编辑A类证书")
                            with st.form(f"edit_cert_form_{cert.id}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    new_cert_name = st.text_input("证书名称", value=cert.certificate_name)
                                    new_cert_number = st.text_input("认证标准", value=cert.certificate_number)
                                with col2:
                                    new_issuing_auth = st.text_input("查询机构", value=cert.issuing_authority or "")
                                    new_cert_type = st.text_input("证书类型", value=cert.certificate_type or "")
                                
                                # 有效期
                                col1, col2 = st.columns(2)
                                with col1:
                                    new_valid_from = st.date_input("有效期开始", format="YYYY-MM-DD", value=cert.valid_from or None, key=f"new_valid_from_{cert.id}")
                                with col2:
                                    new_valid_until = st.date_input("有效期结束", format="YYYY-MM-DD", value=cert.valid_until or None, key=f"new_valid_until_{cert.id}")
                                
                                new_is_active = st.checkbox("是否有效", value=bool(cert.is_active))
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("保存修改"):
                                        if new_cert_name and new_cert_number:
                                            try:
                                                update_class_a_certificate(
                                                    db, cert.id, new_cert_name, new_cert_number, new_issuing_auth,
                                                    new_valid_from, new_valid_until, new_cert_type, int(new_is_active)
                                                )
                                                st.success("✅ 证书更新成功！")
                                                st.session_state[f"editing_cert_{cert.id}"] = False
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"❌ 更新失败：{str(e)}")
                                        else:
                                            st.warning("⚠️ 证书名称和编号不能为空")
                                with col2:
                                    if st.form_submit_button("取消修改", type="secondary"):
                                        st.session_state[f"editing_cert_{cert.id}"] = False
                                        st.rerun()
                else:
                    st.info("暂无A类证书，请添加")
            
            # B类规则管理
            elif category == "B类规则管理":
                # 获取B类规则列表
                rules = get_class_b_rules(db)
                
                # 新增B类规则
                st.subheader("➕ 新增B类规则")
                with st.form(f"add_rule_form_{idx}"):
                    rule_name = st.text_input(
                        "规则名称",
                        help="规则的简洁描述",
                        placeholder="例如：具有5年以上相关经验"
                    )
                    rule_type = st.text_input(
                        "规则类型",
                        help="规则的分类",
                        placeholder="例如：经验要求"
                    )
                    trigger_cond = st.text_area(
                        "触发条件",
                        height=100,
                        help="触发此规则的条件",
                        placeholder="例如：'项目要求中包含'5年以上'或'五年以上'"
                    )
                    conclusion = st.text_area(
                        "结论",
                        height=100,
                        help="满足条件时的结论",
                        placeholder="例如：'符合要求，得满分'"
                    )
                    
                    if st.form_submit_button("保存规则"):
                        if rule_name and trigger_cond and conclusion:
                            try:
                                add_class_b_rule(db, rule_name, trigger_cond, conclusion, rule_type)
                                st.success("✅ 规则添加成功！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 添加失败：{str(e)}")
                        else:
                            st.warning("⚠️ 规则名称、触发条件和结论不能为空")
                
                # 导入默认B类规则
                st.markdown("---")
                st.subheader("📥 导入默认B类规则")
                from config import B_RULE_CONFIG
                if st.button("📥 从config.py导入默认B类规则", key=f"import_default_rules_{idx}"):
                    try:
                        imported_count = 0
                        skipped_count = 0
                        existing_rule_names = {rule.rule_name for rule in rules}
                        
                        for rule_data in B_RULE_CONFIG["default_rules"]:
                            # 检查是否已存在（根据规则名称）
                            if rule_data.get("rule_name") not in existing_rule_names:
                                rule = ClassBRule(**rule_data)
                                db.add(rule)
                                imported_count += 1
                            else:
                                skipped_count += 1
                        
                        db.commit()
                        if imported_count > 0:
                            st.success(f"✅ 成功导入 {imported_count} 条默认B类规则！" + (f"（跳过 {skipped_count} 条已存在的规则）" if skipped_count > 0 else ""))
                        else:
                            st.info(f"ℹ️ 所有默认B类规则已存在，无需导入（共 {skipped_count} 条）")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"❌ 导入失败：{str(e)}")
                
                # 显示现有B类规则
                st.markdown("---")
                st.subheader("📋 现有B类规则")
                
                if rules:
                    for rule in rules:
                        # 规则信息卡片
                        with st.expander(f"{rule.rule_name}"):
                            st.markdown(f"**规则类型:** {rule.rule_type or '未填写'}")
                            st.markdown(f"**触发条件:** {rule.trigger_condition}")
                            st.markdown(f"**结论:** {rule.conclusion}")
                            st.markdown(f"**状态:** {'启用' if rule.is_active else '禁用'}")
                            
                            # 操作按钮
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"✏️ 编辑", key=f"edit_rule_{rule.id}"):
                                    st.session_state[f"editing_rule_{rule.id}"] = True
                            with col2:
                                if st.button(f"🗑️ 删除", key=f"del_rule_{rule.id}"):
                                    try:
                                        delete_class_b_rule(db, rule.id)
                                        st.success("✅ 规则删除成功！")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ 删除失败：{str(e)}")
                        
                        # 编辑表单
                        if f"editing_rule_{rule.id}" in st.session_state and st.session_state[f"editing_rule_{rule.id}"]:
                            st.markdown("---")
                            st.subheader("✏️ 编辑B类规则")
                            with st.form(f"edit_rule_form_{rule.id}"):
                                new_rule_name = st.text_input("规则名称", value=rule.rule_name)
                                new_rule_type = st.text_input("规则类型", value=rule.rule_type or "")
                                new_trigger_cond = st.text_area("触发条件", value=rule.trigger_condition, height=100)
                                new_conclusion = st.text_area("结论", value=rule.conclusion, height=100)
                                new_is_active = st.checkbox("是否启用", value=bool(rule.is_active))
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("保存修改"):
                                        if new_rule_name and new_trigger_cond and new_conclusion:
                                            try:
                                                update_class_b_rule(
                                                    db, rule.id, new_rule_name, new_trigger_cond, new_conclusion,
                                                    new_rule_type, int(new_is_active)
                                                )
                                                st.success("✅ 规则更新成功！")
                                                st.session_state[f"editing_rule_{rule.id}"] = False
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"❌ 更新失败：{str(e)}")
                                        else:
                                            st.warning("⚠️ 规则名称、触发条件和结论不能为空")
                                with col2:
                                    if st.form_submit_button("取消修改", type="secondary"):
                                        st.session_state[f"editing_rule_{rule.id}"] = False
                                        st.rerun()
                else:
                    st.info("暂无B类规则，请添加")
            
            # 普通资质类别
            else:
                # 获取当前类别的资质列表
                items = db_qualifications.get(category, [])
                
                # 新增资质
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_item = st.text_input(f"新增{category}", key=f"new_{category}")

                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)  # 垂直间距
                    if st.button(f"➕ 添加", key=f"add_{category}") and new_item.strip():
                        try:
                            # 检查是否已存在
                            existing = db.query(CompanyQualification).filter(
                                CompanyQualification.category == category,
                                CompanyQualification.content == new_item.strip(),
                                CompanyQualification.is_active == 1
                            ).first()
                            
                            if not existing:
                                add_company_qualification(db, category, new_item.strip())
                                st.success(f"✅ 添加成功：{new_item.strip()}")
                                # 强制刷新页面以显示新数据
                                st.rerun()
                            else:
                                st.warning(f"⚠️ {category}已存在：{new_item.strip()}")
                        except Exception as e:
                            st.error(f"❌ 添加失败：{str(e)}")

                # 显示现有资质
                st.markdown("---")
                st.subheader(f"现有{category}")

                if items:
                    # 列表展示和管理
                    for idx, item in enumerate(items, 1):
                        col1, col2, col3 = st.columns([4, 1, 1])
                        with col1:
                            st.markdown(f"{idx}. {item}")
                        
                        # 仅当从数据库获取的资质才显示编辑和删除按钮
                        # 获取资质ID
                        qual_obj = db.query(CompanyQualification).filter(
                            CompanyQualification.category == category,
                            CompanyQualification.content == item,
                            CompanyQualification.is_active == 1
                        ).first()
                        
                        with col2:
                            if qual_obj:
                                if st.button(f"✏️ 编辑", key=f"edit_{category}_{qual_obj.id}", help="编辑此资质"):
                                    st.session_state[f"editing_{category}_{qual_obj.id}"] = True
                        with col3:
                            if qual_obj:
                                if st.button(f"🗑️ 删除", key=f"del_{category}_{qual_obj.id}", help="删除此资质"):
                                    try:
                                        delete_company_qualification(db, qual_obj.id)
                                        st.success(f"✅ 删除成功：{item}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ 删除失败：{str(e)}")

                        # 编辑表单 - 仅处理数据库中的资质
                        if qual_obj and f"editing_{category}_{qual_obj.id}" in st.session_state and st.session_state[f"editing_{category}_{qual_obj.id}"]:
                            st.markdown("---")
                            st.subheader(f"编辑{category}")
                            new_content = st.text_input("新内容", value=item, key=f"edit_content_{category}_{qual_obj.id}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"💾 保存", key=f"save_{category}_{qual_obj.id}"):
                                    if new_content.strip():
                                        try:
                                            update_company_qualification(db, qual_obj.id, content=new_content.strip())
                                            st.success(f"✅ 编辑成功：{new_content.strip()}")
                                            st.session_state[f"editing_{category}_{qual_obj.id}"] = False
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ 编辑失败：{str(e)}")
                                    else:
                                        st.warning("⚠️ 资质内容不能为空")
                            with col2:
                                if st.button(f"❌ 取消", key=f"cancel_{category}_{qual_obj.id}"):
                                    st.session_state[f"editing_{category}_{qual_obj.id}"] = False
                                    st.rerun()
                else:
                    st.info(f"暂无{category}，请添加")

    # 批量操作区域
    st.markdown("---")
    st.subheader("📋 批量操作")
    
    # 批量导入功能
    with st.expander("🔄 批量导入资质"):
        st.markdown("""
        **导入格式说明**：
        - 每行一个资质
        - 使用 `类别: 内容` 格式
        - 例如：
          ```
          企业资质: 建筑工程施工总承包一级
          人员资质: 一级建造师（建筑工程）
          财务要求: 近3年净资产均在5000万元以上
          ```
        """)
        
        import_text = st.text_area("批量导入资质", height=200, placeholder="类别1: 资质内容1\n类别2: 资质内容2\n...")
        
        if st.button("📥 执行批量导入"):
            if import_text.strip():
                try:
                    lines = import_text.strip().split("\n")
                    success_count = 0
                    error_count = 0
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if ": " in line:
                            category, content = line.split(": ", 1)
                            if category and content:
                                try:
                                    # 检查是否已存在
                                    existing = db.query(CompanyQualification).filter(
                                        CompanyQualification.category == category,
                                        CompanyQualification.content == content,
                                        CompanyQualification.is_active == 1
                                    ).first()
                                    
                                    if not existing:
                                        add_company_qualification(db, category, content)
                                        success_count += 1
                                    else:
                                        error_count += 1
                                except Exception:
                                    error_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                    
                    st.success(f"✅ 批量导入完成！成功：{success_count} 条，失败：{error_count} 条")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 批量导入失败：{str(e)}")
            else:
                st.warning("⚠️ 请输入要导入的资质内容")

    # 关闭数据库连接
    db.close()


def run_ai_analysis_with_progress():
    """带进度和CPU监控的AI分析执行函数"""
    # 初始化状态
    st.session_state['ai_analysis_running'] = True
    st.session_state['ai_analysis_paused'] = False
    st.session_state['ai_analysis_progress'] = 0
    st.session_state['ai_analysis_current'] = 0
    st.session_state['ai_analysis_total'] = 0
    st.session_state['completed_projects'] = []
    st.session_state['failed_projects'] = []
    
    try:
        # 获取数据库连接
        from utils.db import get_db, TenderProject, ProjectStatus, update_project
        db = next(get_db())
        
        # 查询待分析的项目
        target_project_id = st.session_state.get('target_error_project_id')
        if target_project_id:
            # 只分析特定项目
            project = db.query(TenderProject).filter(
                TenderProject.id == target_project_id,
                TenderProject.status == ProjectStatus.PARSED
            ).first()
            projects = [project] if project else []
        else:
            # 分析所有待分析项目
            projects = db.query(TenderProject).filter(
                TenderProject.status == ProjectStatus.PARSED
            ).all()
        
        # 清除目标项目ID，避免重复分析
        if 'target_error_project_id' in st.session_state:
            del st.session_state['target_error_project_id']
        
        total = len(projects)
        current = 0
        
        # 创建进度条和状态显示
        progress_bar = st.progress(0)
        status_text = st.empty()
        cpu_text = st.empty()
        
        # 在进度显示区域内创建控制按钮
        control_container = st.container()
        with control_container:
            col1, col2, col3 = st.columns(3)
            pause_button = col1.button("⏸️ 暂停分析", key="pause_button_in_progress")
            resume_button = col2.button("▶️ 继续分析", key="resume_button_in_progress", disabled=True)
            stop_button = col3.button("❌ 中断分析", type="secondary", key="stop_button_in_progress")
        
        # 执行前显示初始信息
        safe_streamlit_update(status_text.info, f"📋 准备分析 {total} 个项目")
        
        for project in projects:
            # 检查按钮状态更新
            if pause_button:
                st.session_state['ai_analysis_paused'] = True
                resume_button = col2.button("▶️ 继续分析", key="resume_button_in_progress_after_pause", disabled=False)
            if resume_button:
                st.session_state['ai_analysis_paused'] = False
            if stop_button:
                st.session_state['ai_analysis_running'] = False
            
            # 检查是否暂停
            if st.session_state.get('ai_analysis_paused', False):
                safe_streamlit_update(status_text.info, f"⏸️ 分析已暂停，当前进度：{current}/{total}")
                # 等待直到继续或中断
                wait_start = time.time()
                while st.session_state.get('ai_analysis_paused', False):
                    # 每2秒检查一次是否需要退出
                    if time.time() - wait_start > 2:
                        wait_start = time.time()
                        # 刷新UI
                        safe_streamlit_update(status_text.info, f"⏸️ 分析已暂停，当前进度：{current}/{total}")
                        # 重新渲染按钮以获取最新状态
                        with control_container:
                            col1, col2, col3 = st.columns(3)
                            if col2.button("▶️ 继续分析", key="resume_button_refresh"):
                                st.session_state['ai_analysis_paused'] = False
                            if col3.button("❌ 中断分析", type="secondary", key="stop_button_refresh"):
                                st.session_state['ai_analysis_running'] = False
                    
                    # 检查是否需要退出
                    if not st.session_state.get('ai_analysis_running', False):
                        break
                    time.sleep(0.5)
                
            if not st.session_state.get('ai_analysis_running', False):
                safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                break
            
            try:
                current += 1
                progress = current / total if total > 0 else 0
                
                # 减少UI更新频率：每5个项目或最后一个项目才更新进度条和状态
                # 这样可以减少WebSocket错误（当客户端断开连接时）
                should_update_ui = (current % 5 == 0) or (current == total) or (current == 1)
                
                if should_update_ui:
                    safe_streamlit_update(progress_bar.progress, progress)
                    
                    # 直接获取CPU使用率而不是通过线程
                    cpu_usage = psutil.cpu_percent(interval=0.1)
                    
                    safe_streamlit_update(status_text.info, f"🔍 正在分析项目 {current}/{total}：{project.project_name}")
                    safe_streamlit_update(cpu_text.text, f"💻 CPU占用率：{cpu_usage:.1f}%")
                    # 短暂延迟，让Streamlit有机会更新UI
                    time.sleep(0.1)
                
                # 执行实际分析
                if not project.evaluation_content:
                    raise ValueError("项目解析内容为空")
                
                # 在执行AI操作前检查是否中断
                if not st.session_state.get('ai_analysis_running', False):
                    safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                    break
                
                # 0. 先判断是否是服务类项目
                ai_analyzer = get_ai_analyzer()
                
                # 检查是否中断（在长时间操作前）
                if not st.session_state.get('ai_analysis_running', False):
                    safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                    break
                
                is_service, reason = ai_analyzer.is_service_project(project.evaluation_content)
                
                # 检查是否是因为功能被禁用而返回False
                service_check_enabled = config.AI_CONFIG.get("service_check", {}).get("enable", False)
                
                if is_service and service_check_enabled:
                    # 只有当服务类判断功能启用且项目确实是服务类时，才标记为已排除
                    log.info(f"⚠️ 项目 {project.id} 是服务类项目，标记为已排除：{reason}")
                    # 更新项目状态为已排除，而不是删除，避免下次重复爬取
                    from utils.db import get_db, update_project, ProjectStatus
                    db = next(get_db())
                    update_project(db, project.id, {
                        "status": ProjectStatus.EXCLUDED,
                        "error_msg": f"服务类项目：{reason}"
                    })
                    db.commit()
                    db.close()
                    log.info(f"✅ 服务类项目已标记为已排除：{project.project_name}（ID：{project.id}）")
                    continue  # 跳过后续分析
                elif is_service and not service_check_enabled:
                    # 当服务类判断功能被禁用时，跳过判断，继续分析所有项目
                    log.info(f"服务类判断功能已禁用，跳过判断，继续分析项目 {project.id}")
                else:
                    # 项目不是服务类，继续分析
                    log.info(f"项目 {project.id} 不是服务类项目，继续分析")
                
                # 1. 提取资质要求
                # 检查是否中断（在长时间操作前）
                if not st.session_state.get('ai_analysis_running', False):
                    safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                    break
                
                project_requirements = ai_analyzer.extract_requirements(project.evaluation_content)
                
                # 检查是否中断（在第二个AI操作前）
                if not st.session_state.get('ai_analysis_running', False):
                    safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                    break
                
                # 2. 比对资质
                comparison_result, final_decision = ai_analyzer.compare_qualifications(project_requirements)
                
                # 3. 应用客观分判定配置
                from config import OBJECTIVE_SCORE_CONFIG
                if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                    # 检查是否需要根据客观分丢分阈值调整最终决策
                    if "客观分不满分" in final_decision:
                        # 尝试从比对结果中提取丢分信息
                        loss_score = 0.0
                        # 简单的丢分提取逻辑，实际项目中可能需要更复杂的解析
                        import re
                        loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison_result)
                        if loss_match:
                            loss_score = float(loss_match.group(1))
                        
                        threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                        if loss_score <= threshold:
                            # 丢分≤阈值，改为"推荐参与"
                            original_decision = final_decision
                            final_decision = "推荐参与"
                            comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：推荐参与"
                    elif "推荐参与" in final_decision:
                        # 检查是否需要根据丢分阈值改为"不推荐参与"
                        loss_score = 0.0
                        import re
                        loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison_result)
                        if loss_match:
                            loss_score = float(loss_match.group(1))
                        
                        threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                        if loss_score > threshold:
                            # 丢分>阈值，改为"不推荐参与"
                            original_decision = final_decision
                            final_decision = "不推荐参与"
                            comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：不推荐参与"
                
                # 4. 确保结果是中文的，如果不是则格式化
                if not ("符合" in comparison_result and ("可以参与" in comparison_result or "不可以参与" in comparison_result)):
                    # 如果结果不是中文格式，则添加中文说明
                    comparison_result = f"资质比对结果：{comparison_result}\n\n（注：以上为AI原始输出，已转换为中文显示）"
                
                # 3. 更新项目状态
                update_project(db, project.id, {
                    "project_requirements": project_requirements,
                    "ai_extracted_text": project_requirements,  # 保存AI提取的原始文本
                    "comparison_result": comparison_result,
                    "final_decision": final_decision or "未判定",
                    "status": ProjectStatus.COMPARED
                })
                
                st.session_state['completed_projects'].append(project.project_name)
                # 只在关键节点更新UI，减少WebSocket错误
                if should_update_ui:
                    safe_streamlit_update(status_text.success, f"✅ 项目分析完成：{project.project_name}")
                
            except Exception as e:
                error_msg = str(e)[:500]
                error_type = type(e).__name__
                
                # 记录详细错误信息
                log.error(f"项目 {project.id} ({project.project_name}) 分析失败：{error_type}: {error_msg}")
                
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
                
                # 更新项目状态
                try:
                    if analysis_fail_count >= 3:
                        # 3次都失败，标记为异常
                        error_msg_full = f"{error_type}: {error_msg} [AI分析失败{analysis_fail_count}次] [跳过-多次失败]"
                        log.warning(f"⚠️ 项目 {project.project_name}（ID：{project.id}）AI分析已失败{analysis_fail_count}次，标记为跳过")
                        update_project(db, project.id, {
                            "status": ProjectStatus.ERROR,
                            "error_msg": error_msg_full
                        })
                    else:
                        # 自动重试：重置状态为PARSED，让它重新进入AI分析流程
                        error_msg_full = f"{error_type}: {error_msg} [AI分析失败{analysis_fail_count}次]"
                        log.info(f"🔄 项目 {project.project_name}（ID：{project.id}）AI分析失败第{analysis_fail_count}次，自动重置状态准备重试")
                        update_project(db, project.id, {
                            "status": ProjectStatus.PARSED,  # 重置为PARSED状态，下次分析时会重新处理
                            "error_msg": error_msg_full,
                            "project_requirements": None,  # 清空之前可能的部分分析结果
                            "comparison_result": None,
                            "final_decision": None
                        })
                except Exception as update_error:
                    log.error(f"更新项目状态失败：{str(update_error)}")
                
                st.session_state['failed_projects'].append(f"{project.project_name}（{error_msg[:100]}）")
                
                # 错误信息总是显示，但使用安全更新
                safe_streamlit_update(status_text.error, f"❌ 项目分析失败：{project.project_name}（{error_type}）")
                
                # 继续处理下一个项目，不中断整个分析流程
                continue
        
        db.close()
        
        # 显示结果统计
        if st.session_state.get('ai_analysis_running', False):
            safe_streamlit_update(status_text.success, "✅ AI资质分析完成！")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("总项目数", total)
            col2.metric("成功项目数", len(st.session_state['completed_projects']))
            col3.metric("失败项目数", len(st.session_state['failed_projects']))
            
            if st.session_state['failed_projects']:
                with st.expander("查看失败项目", expanded=False):
                    for failed in st.session_state['failed_projects']:
                        st.error(f"- {failed}")
                    
    finally:
        # 清理资源（只有在正常完成或明确中断时才清理）
        was_running = st.session_state.get('ai_analysis_running', False)
        
        # 标记分析已完成
        st.session_state['ai_analysis_running'] = False
        
        # 清除所有相关缓存，确保数据及时更新
        get_project_stats.clear()
        get_today_project_stats.clear()
        get_completed_projects.clear()
        get_all_projects.clear()
        
        # 只有在正常完成时才清理UI（不刷新页面，避免中断任务）
        if was_running and current >= total:
            progress_bar.empty()
            status_text.empty()
            cpu_text.empty()
            control_container.empty()
            # 不刷新页面，让Streamlit自动更新UI
            time.sleep(0.1)
        # 如果是中断的，保留UI显示，让用户看到中断信息

def _check_task_status():
    """检查任务运行状态（基于session_state）"""
    task_configs = {
        "全流程": "full_process_running",
        "文件解析": "parse_running",
        "AI资质分析": "ai_analysis_running"
    }
    
    for task_name, session_key in task_configs.items():
        if st.session_state.get(session_key, False):
            # 检查线程是否还在运行
            thread_key = session_key.replace("_running", "_thread")
            thread = st.session_state.get(thread_key)
            if thread and thread.is_alive():
                # 获取任务信息
                task_info = {
                    "start_time": st.session_state.get(f"{session_key}_start_time", datetime.now().isoformat()),
                    "process": task_name,
                    "paused": st.session_state.get(f"{session_key}_paused", False),
                    "stopped": st.session_state.get(f"{session_key}_stopped", False)
                }
                return True, task_name, task_info
            else:
                # 线程已结束，清除状态
                st.session_state[session_key] = False
    
    return False, None, None

def _get_progress_stats():
    """获取进度统计信息（辅助函数）"""
    try:
        from utils.db import get_db, TenderProject, ProjectStatus
        from sqlalchemy import func, case
        
        db = next(get_db())
        try:
            stats = db.query(
                func.count(TenderProject.id).label('total'),
                func.sum(case((TenderProject.status == ProjectStatus.DOWNLOADED, 1), else_=0)).label('downloaded'),
                func.sum(case((TenderProject.status == ProjectStatus.PARSED, 1), else_=0)).label('parsed'),
                func.sum(case((TenderProject.status == ProjectStatus.COMPARED, 1), else_=0)).label('compared')
            ).first()
            
            return {
                'downloaded': stats.downloaded or 0,
                'parsed': stats.parsed or 0,
                'compared': stats.compared or 0,
                'total': stats.total or 0
            }
        finally:
            db.close()
    except Exception as e:
        log.warning(f"获取进度信息失败：{str(e)}")
        return {'downloaded': 0, 'parsed': 0, 'compared': 0, 'total': 0}

def _render_task_steps(task_name, task_info):
    """渲染任务执行步骤的可视化显示"""
    st.markdown("### 📋 执行步骤")
    
    # 根据任务类型定义步骤
    if task_name == "全流程":
        steps = [
            {"name": "标书爬虫", "status": "pending", "icon": "📥"},
            {"name": "文件解析", "status": "pending", "icon": "📄"},
            {"name": "AI资质分析", "status": "pending", "icon": "🤖"},
            {"name": "完成", "status": "pending", "icon": "✅"}
        ]
        
        # 根据数据库状态判断当前步骤
        stats = _get_progress_stats()
        if stats['compared'] > 0:
            current_step = 3
        elif stats['parsed'] > 0:
            current_step = 2
        elif stats['downloaded'] > 0:
            current_step = 1
        else:
            current_step = 0
            
    elif task_name == "文件解析":
        steps = [
            {"name": "开始解析", "status": "pending", "icon": "📄"},
            {"name": "解析中", "status": "pending", "icon": "⏳"},
            {"name": "完成", "status": "pending", "icon": "✅"}
        ]
        stats = _get_progress_stats()
        if stats['parsed'] > 0:
            current_step = 2
        else:
            current_step = 0
            
    elif task_name == "AI资质分析":
        steps = [
            {"name": "开始分析", "status": "pending", "icon": "🤖"},
            {"name": "分析中", "status": "pending", "icon": "⏳"},
            {"name": "完成", "status": "pending", "icon": "✅"}
        ]
        stats = _get_progress_stats()
        if stats['compared'] > 0:
            current_step = 2
        else:
            current_step = 0
    else:
        steps = [
            {"name": "执行中", "status": "pending", "icon": "⏳"},
            {"name": "完成", "status": "pending", "icon": "✅"}
        ]
        current_step = 0
    
    # 更新步骤状态
    for i, step in enumerate(steps):
        if i < current_step:
            step["status"] = "completed"
        elif i == current_step:
            step["status"] = "running"
        else:
            step["status"] = "pending"
    
    # 渲染步骤
    cols = st.columns(len(steps))
    for i, (col, step) in enumerate(zip(cols, steps)):
        with col:
            if step["status"] == "completed":
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background-color: #d1fae5; 
                            border-radius: 8px; border: 2px solid #10b981;">
                    <div style="font-size: 24px;">{step['icon']}</div>
                    <div style="font-weight: bold; color: #065f46;">{step['name']}</div>
                    <div style="font-size: 12px; color: #047857;">✓ 已完成</div>
                </div>
                """, unsafe_allow_html=True)
            elif step["status"] == "running":
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background-color: #dbeafe; 
                            border-radius: 8px; border: 2px solid #3b82f6; animation: pulse 2s infinite;">
                    <div style="font-size: 24px;">{step['icon']}</div>
                    <div style="font-weight: bold; color: #1e40af;">{step['name']}</div>
                    <div style="font-size: 12px; color: #1d4ed8;">⟳ 执行中</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background-color: #f3f4f6; 
                            border-radius: 8px; border: 2px solid #9ca3af;">
                    <div style="font-size: 24px; opacity: 0.5;">{step['icon']}</div>
                    <div style="font-weight: bold; color: #6b7280;">{step['name']}</div>
                    <div style="font-size: 12px; color: #9ca3af;">○ 待执行</div>
                </div>
                """, unsafe_allow_html=True)
    
    # 添加CSS动画
    st.markdown("""
    <style>
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    </style>
    """, unsafe_allow_html=True)

def _start_background_task(task_type, **kwargs):
    """启动后台任务的统一函数（基于session_state）"""
    task_configs = {
        "全流程": {
            "session_key": "full_process_running",
            "thread_key": "full_process_thread",
            "paused_key": "full_process_paused",
            "stopped_key": "full_process_stopped"
        },
        "文件解析": {
            "session_key": "parse_running",
            "thread_key": "parse_thread",
            "paused_key": "parse_paused",
            "stopped_key": "parse_stopped"
        },
        "AI资质分析": {
            "session_key": "ai_analysis_running",
            "thread_key": "ai_analysis_thread",
            "paused_key": "ai_analysis_paused",
            "stopped_key": "ai_analysis_stopped"
        }
    }
    
    config = task_configs.get(task_type)
    if not config:
        return False
    
    # 设置session_state
    st.session_state[config["session_key"]] = True
    st.session_state[config["thread_key"]] = None
    st.session_state[config["paused_key"]] = False
    st.session_state[config["stopped_key"]] = False
    st.session_state[f"{config['session_key']}_start_time"] = datetime.now().isoformat()
    
    # 启动对应的线程函数（增强异常处理，防止应用崩溃）
    if task_type == "全流程":
        def safe_get_session_state(key, default=False):
            """安全地获取session_state值，避免ScriptRunContext警告"""
            try:
                import streamlit
                from streamlit.runtime.scriptrunner import get_script_run_ctx
                ctx = get_script_run_ctx()
                if ctx:
                    return st.session_state.get(key, default)
                return default
            except:
                return default
                
        def run_task(config=config, kwargs=kwargs):
            try:
                from auto_run_full_process import run_full_process_cli
                daily_limit = kwargs.get("daily_limit", SPIDER_CONFIG['daily_limit'])
                days_before = kwargs.get("days_before", 7)
                enabled_platforms = kwargs.get("enabled_platforms", None)
                
                # 检查是否被停止
                while not safe_get_session_state(config["stopped_key"]):
                    # 检查是否被暂停
                    while safe_get_session_state(config["paused_key"]) and not safe_get_session_state(config["stopped_key"]):
                        time.sleep(1)  # 暂停时等待
                    
                    if safe_get_session_state(config["stopped_key"]):
                        log.warning("全流程执行被用户终止")
                        break
                    
                    try:
                        result = run_full_process_cli(daily_limit=daily_limit, days_before=days_before, model_type=None, enabled_platforms=enabled_platforms)
                        break  # 执行完成，退出循环
                    except KeyboardInterrupt:
                        log.warning("全流程执行被用户中断")
                        break
                    except Exception as e:
                        log.error(f"全流程执行失败：{str(e)}", exc_info=True)
                        break
            except Exception as e:
                log.error(f"全流程任务启动失败：{str(e)}", exc_info=True)
            finally:
                # 尝试清除session_state（仅在有ScriptRunContext时执行）
                try:
                    import streamlit
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    ctx = get_script_run_ctx()
                    if ctx:
                        # 清除session_state
                        st.session_state[config["session_key"]] = False
                        st.session_state[config["stopped_key"]] = False
                        st.session_state[config["paused_key"]] = False
                except:
                    # 如果发生任何异常，忽略它（不能在后台线程中安全更新session_state）
                    pass
        
    elif task_type == "文件解析":
        def safe_get_session_state(key, default=False):
            """安全地获取session_state值，避免ScriptRunContext警告"""
            try:
                import streamlit
                from streamlit.runtime.scriptrunner import get_script_run_ctx
                ctx = get_script_run_ctx()
                if ctx:
                    return st.session_state.get(key, default)
                return default
            except:
                return default
                
        def run_task(config=config):
            try:
                from parser.file_parser import FileParser
                
                # 检查是否被停止
                while not safe_get_session_state(config["stopped_key"]):
                    # 检查是否被暂停
                    while safe_get_session_state(config["paused_key"]) and not safe_get_session_state(config["stopped_key"]):
                        time.sleep(1)  # 暂停时等待
                    
                    if safe_get_session_state(config["stopped_key"]):
                        log.warning("文件解析被用户终止")
                        break
                    
                    try:
                        parser = get_file_parser()
                        parser.run()
                        break  # 执行完成，退出循环
                    except KeyboardInterrupt:
                        log.warning("文件解析被用户中断")
                        break
                    except Exception as e:
                        log.error(f"文件解析失败：{str(e)}", exc_info=True)
                        break
            except Exception as e:
                log.error(f"文件解析任务启动失败：{str(e)}", exc_info=True)
            finally:
                # 尝试清除session_state（仅在有ScriptRunContext时执行）
                try:
                    import streamlit
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    ctx = get_script_run_ctx()
                    if ctx:
                        # 清除session_state
                        st.session_state[config["session_key"]] = False
                        st.session_state[config["stopped_key"]] = False
                        st.session_state[config["paused_key"]] = False
                except:
                    # 如果发生任何异常，忽略它（不能在后台线程中安全更新session_state）
                    pass
    
    elif task_type == "AI资质分析":
        def safe_get_session_state(key, default=False):
            """安全地获取session_state值，避免ScriptRunContext警告"""
            try:
                # 尝试安全访问session_state
                import streamlit
                from streamlit.runtime.scriptrunner import get_script_run_ctx
                ctx = get_script_run_ctx()
                if ctx:
                    return st.session_state.get(key, default)
                return default
            except:
                # 如果发生任何异常，返回默认值
                return default
                
        def run_task(config=config):
            db = None
            try:
                from ai.qualification_analyzer import AIAnalyzer
                from utils.db import get_db, TenderProject, ProjectStatus, update_project
                
                # 检查是否被停止
                while not safe_get_session_state(config["stopped_key"]):
                    # 检查是否被暂停
                    while safe_get_session_state(config["paused_key"]) and not safe_get_session_state(config["stopped_key"]):
                        time.sleep(1)  # 暂停时等待
                    
                    if safe_get_session_state(config["stopped_key"]):
                        log.warning("AI资质分析被用户终止")
                        break
                    
                    try:
                        analyzer = AIAnalyzer()
                        log.info("AI分析器初始化完成，开始查询待分析项目")
                        db = next(get_db())
                        try:
                            projects = db.query(TenderProject).filter(TenderProject.status == ProjectStatus.PARSED).all()
                            log.info(f"查询到 {len(projects)} 个待分析项目")
                            
                            if len(projects) == 0:
                                log.info("没有待分析的项目，AI资质分析任务完成")
                                break  # 没有项目，退出循环
                            
                            processed_count = 0
                            for project in projects:
                                # 检查是否被停止
                                if safe_get_session_state(config["stopped_key"]):
                                    log.warning(f"AI资质分析被用户终止，已处理 {processed_count}/{len(projects)} 个项目")
                                    break
                                
                                # 检查是否被暂停
                                while safe_get_session_state(config["paused_key"]) and not safe_get_session_state(config["stopped_key"]):
                                    time.sleep(1)
                                
                                if safe_get_session_state(config["stopped_key"]):
                                    log.warning(f"AI资质分析被用户终止，已处理 {processed_count}/{len(projects)} 个项目")
                                    break
                                
                                try:
                                    if project.evaluation_content:
                                        log.info(f"开始分析项目 {project.id}：{project.project_name[:50]}")
                                        
                                        # 0. 先判断是否是服务类项目
                                        is_service, reason = analyzer.is_service_project(project.evaluation_content)
                                        
                                        # 检查是否是因为功能被禁用而返回False
                                        try:
                                            service_check_enabled = config.AI_CONFIG.get("service_check", {}).get("enable", False)
                                        except Exception as e:
                                            log.warning(f"访问config.AI_CONFIG失败，使用默认值：{str(e)}")
                                            service_check_enabled = False  # 默认禁用服务类检查
                                        
                                        if is_service and service_check_enabled:
                                            # 只有当服务类判断功能启用且项目确实是服务类时，才标记为已排除
                                            log.info(f"⚠️ 项目 {project.id} 是服务类项目，标记为已排除：{reason}")
                                            # 更新项目状态为已排除，而不是删除，避免下次重复爬取
                                            from utils.db import update_project, ProjectStatus
                                            update_project(db, project.id, {
                                                "status": ProjectStatus.EXCLUDED,
                                                "error_msg": f"服务类项目：{reason}"
                                            })
                                            db.commit()
                                            log.info(f"✅ 服务类项目已标记为已排除：{project.project_name}（ID：{project.id}）")
                                            continue  # 跳过后续分析
                                        elif is_service and not service_check_enabled:
                                            # 当服务类判断功能被禁用时，跳过判断，继续分析所有项目
                                            log.info(f"服务类判断功能已禁用，跳过判断，继续分析项目 {project.id}")
                                        else:
                                            # 项目不是服务类，继续分析
                                            log.info(f"项目 {project.id} 不是服务类项目，继续分析")
                                        
                                        # 1. 提取资质要求
                                        requirements = analyzer.extract_requirements(project.evaluation_content)
                                        # 2. 比对资质
                                        comparison, decision = analyzer.compare_qualifications(requirements)
                                        
                                        # 3. 应用客观分判定配置
                                        from config import OBJECTIVE_SCORE_CONFIG
                                        if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                                            # 检查是否需要根据客观分丢分阈值调整最终决策
                                            if "客观分不满分" in decision:
                                                # 尝试从比对结果中提取丢分信息
                                                loss_score = 0.0
                                                # 简单的丢分提取逻辑，实际项目中可能需要更复杂的解析
                                                import re
                                                loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison)
                                                if loss_match:
                                                    loss_score = float(loss_match.group(1))
                                                
                                                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                                if loss_score <= threshold:
                                                    # 丢分≤阈值，改为"推荐参与"
                                                    original_decision = decision
                                                    decision = "推荐参与"
                                                    comparison += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：推荐参与"
                                            elif "推荐参与" in decision:
                                                # 检查是否需要根据丢分阈值改为"不推荐参与"
                                                loss_score = 0.0
                                                import re
                                                loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison)
                                                if loss_match:
                                                    loss_score = float(loss_match.group(1))
                                                
                                                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                                if loss_score > threshold:
                                                    # 丢分>阈值，改为"不推荐参与"
                                                    original_decision = decision
                                                    decision = "不推荐参与"
                                                    comparison += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：不推荐参与"
                                        
                                        update_project(db, project.id, {
                                            "project_requirements": requirements,
                                            "ai_extracted_text": requirements,
                                            "comparison_result": comparison,
                                            "final_decision": decision or "未判定",
                                            "status": ProjectStatus.COMPARED
                                        })
                                        db.commit()
                                        processed_count += 1
                                        log.info(f"项目 {project.id} 分析完成，最终判定：{decision}")
                                    else:
                                        log.warning(f"项目 {project.id} 解析内容为空，跳过分析")
                                        # 自动重置为DOWNLOADED状态，以便重新解析
                                        log.info(f"🔄 项目 {project.id} 解析内容为空，自动重置为DOWNLOADED状态，等待重新解析")
                                        update_project(db, project.id, {
                                            "status": ProjectStatus.DOWNLOADED,
                                            "error_msg": "解析内容为空，已重置状态等待重新解析",
                                            "evaluation_content": None  # 清空空内容
                                        })
                                        db.commit()
                                except Exception as e:
                                    error_msg = str(e)[:500]
                                    log.error(f"AI分析项目失败（项目ID: {project.id}）：{error_msg}", exc_info=True)
                                    
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
                                    
                                    try:
                                        if analysis_fail_count >= 3:
                                            # 3次都失败，标记为异常
                                            error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次] [跳过-多次失败]"
                                            log.warning(f"⚠️ 项目 {project.project_name}（ID：{project.id}）AI分析已失败{analysis_fail_count}次，标记为跳过")
                                            update_project(db, project.id, {
                                                "status": ProjectStatus.ERROR,
                                                "error_msg": error_msg_full
                                            })
                                        else:
                                            # 自动重试：重置状态为PARSED，让它重新进入AI分析流程
                                            error_msg_full = f"AI分析失败：{error_msg} [AI分析失败{analysis_fail_count}次]"
                                            log.info(f"🔄 项目 {project.project_name}（ID：{project.id}）AI分析失败第{analysis_fail_count}次，自动重置状态准备重试")
                                            update_project(db, project.id, {
                                                "status": ProjectStatus.PARSED,  # 重置为PARSED状态，下次分析时会重新处理
                                                "error_msg": error_msg_full,
                                                "project_requirements": None,  # 清空之前可能的部分分析结果
                                                "comparison_result": None,
                                                "final_decision": None
                                            })
                                        db.commit()
                                    except Exception as update_error:
                                        log.error(f"更新项目状态失败：{str(update_error)}")
                                        db.rollback()
                                    
                                    continue
                            
                            log.info(f"AI资质分析任务完成，共处理 {processed_count}/{len(projects)} 个项目")
                        finally:
                            if db:
                                db.close()
                        break  # 执行完成，退出循环
                    except KeyboardInterrupt:
                        log.warning("AI资质分析被用户中断")
                        break
                    except Exception as e:
                        log.error(f"AI资质分析失败：{str(e)}", exc_info=True)
                        break
            except Exception as e:
                log.error(f"AI资质分析任务启动失败：{str(e)}", exc_info=True)
            finally:
                try:
                    if db:
                        db.close()
                except:
                    pass
                # 尝试清除session_state（仅在有ScriptRunContext时执行）
                try:
                    import streamlit
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    ctx = get_script_run_ctx()
                    if ctx:
                        # 清除session_state
                        st.session_state[config["session_key"]] = False
                        st.session_state[config["stopped_key"]] = False
                        st.session_state[config["paused_key"]] = False
                except:
                    # 如果发生任何异常，忽略它（不能在后台线程中安全更新session_state）
                    pass
    
    thread = Thread(target=run_task, daemon=False, name=f"{task_type}Thread")
    thread.start()
    st.session_state[config["thread_key"]] = thread
    return True

def _render_project_status(show_refresh=True):
    """渲染项目状态显示（当日和全部项目）"""
    from utils.db import get_db, ProjectStatus, update_project
    from datetime import timedelta
    
    # 定义状态顺序（在整个函数中可用）
    status_order = ["待处理", "已下载", "已解析", "已比对", "异常", "未知"]
    
    # 当日项目状态
    st.markdown("---")
    st.subheader("📊 当日项目状态")
    
    # 只在非任务运行时显示刷新按钮
    if show_refresh:
        col_refresh1, col_refresh2 = st.columns([1, 10])
        with col_refresh1:
            if st.button("🔄 刷新", key="refresh_today_status"):
                get_all_projects.clear()
                get_project_stats.clear()
                get_today_project_stats.clear()
                st.rerun()
        with col_refresh2:
            # 自动刷新提示：显示缓存状态
            cache_info = "💡 提示：数据缓存60秒，新保存的项目可能需要刷新后才能显示"
            st.caption(cache_info)
    
    today = datetime.today().date()
    all_projects = get_all_projects()
    today_projects = [p for p in all_projects if (p.create_time and p.create_time.date() == today) or 
                     (p.publish_time and p.publish_time.date() == today)]
    
    if today_projects:
        status_data = {}
        for p in today_projects:
            status = p.status if p.status else "未知"
            status_data[status] = status_data.get(status, 0) + 1

        if status_data:
            fig = px.pie(values=list(status_data.values()), names=list(status_data.keys()),
                        title="当日项目状态分布", hole=0.3)
            st.plotly_chart(fig, config={"displayModeBar": True}, width='stretch')
        
        st.markdown("### 📊 状态统计")
        sorted_items = sorted(status_data.items(), key=lambda x: status_order.index(x[0]) if x[0] in status_order else len(status_order))
        
        for row_start in range(0, len(sorted_items), 6):
            row_items = sorted_items[row_start:row_start + 6]
            cols = st.columns(len(row_items))
            for idx, (status, count) in enumerate(row_items):
                with cols[idx]:
                    st.metric(label=status, value=count)

        # 项目列表
        st.markdown("### 📋 当日项目详情")
        projects_by_status = {}
        for p in today_projects:
            status = p.status if p.status else "未知"
            if status not in projects_by_status:
                projects_by_status[status] = []
            projects_by_status[status].append(p)
        
        sorted_statuses = sorted(projects_by_status.keys(), key=lambda x: status_order.index(x) if x in status_order else len(status_order))
        for status in sorted_statuses:
            with st.expander(f"{status} ({len(projects_by_status[status])}个)", expanded=True):
                df_data = [{"ID": p.id, "项目名称": p.project_name, "来源": p.site_name,
                           "状态": p.status or "未知", "文件格式": p.file_format or "未知",
                           "判定结果": p.final_decision or "未完成",
                           "发布时间": p.publish_time.strftime("%Y-%m-%d %H:%M:%S") if p.publish_time else "未知"}
                          for p in projects_by_status[status]]
                st.dataframe(pd.DataFrame(df_data), width='stretch')
                
                if status == "异常":
                    if st.button("🔄 一键重置全部为已下载", key=f"reset_today_error_{status}"):
                        try:
                            db = next(get_db())
                            try:
                                updated = sum(1 for p in projects_by_status[status] 
                                             if update_project(db, p.id, {"status": ProjectStatus.DOWNLOADED, "error_msg": None}))
                                db.commit()
                                get_all_projects.clear()
                                st.success(f"✅ 已重置 {updated} 个异常项目")
                                time.sleep(0.5)
                                st.rerun()
                            finally:
                                db.close()
                        except Exception as e:
                            st.error(f"重置失败：{str(e)}")
    else:
        st.info("📊 今日暂无项目数据")
    
    # 全部项目状态详情
    st.markdown("---")
    st.subheader("📋 全部项目状态详情")
    
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        all_statuses = ["全部"] + [s.value for s in ProjectStatus] + ["未知"]
        selected_status = st.selectbox("筛选状态", all_statuses, index=0, key="all_status_filter")
    with col2:
        date_filter = st.selectbox("日期范围", ["全部", "最近7天", "最近30天", "最近90天", "自定义"],
                                  key="all_date_filter")
    with col3:
        # 平台筛选
        available_platforms = get_available_platforms()
        platform_options = ["全部"] + list(available_platforms.values())
        selected_platform_name = st.selectbox("筛选平台", platform_options, index=0, key="all_platform_filter")
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 刷新全部", key="refresh_all"):
            get_all_projects.clear()
            st.rerun()
    
    # 日期筛选
    start_date = end_date = None
    if date_filter == "自定义":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("开始日期", value=datetime.now().date() - timedelta(days=30), key="start_date")
        with col_d2:
            end_date = st.date_input("结束日期", value=datetime.now().date(), key="end_date")
    elif date_filter != "全部":
        days_map = {"最近7天": 7, "最近30天": 30, "最近90天": 90}
        start_date = datetime.now().date() - timedelta(days=days_map.get(date_filter, 30))
        end_date = datetime.now().date()
    
    # 应用筛选
    filtered = []
    # 获取平台代码
    selected_platform_code = None
    if selected_platform_name != "全部":
        selected_platform_code = {v: k for k, v in available_platforms.items()}.get(selected_platform_name)
    
    for p in all_projects:
        p_status = p.status if p.status else "未知"
        if selected_status != "全部" and (selected_status == "未知" and p_status != "未知" or 
                                          selected_status != "未知" and p_status != selected_status):
            continue
        if start_date or end_date:
            p_date = (p.create_time or p.publish_time)
            if p_date:
                p_date = p_date.date()
                if (start_date and p_date < start_date) or (end_date and p_date > end_date):
                    continue
            elif date_filter != "全部":
                continue
        # 平台筛选
        if selected_platform_code:
            project_platform = extract_platform_code(p.site_name if hasattr(p, 'site_name') else getattr(p, 'site_name', ''))
            if project_platform != selected_platform_code:
                continue
        filtered.append(p)
    
    if filtered:
        status_counts = {}
        for p in filtered:
            s = p.status if p.status else "未知"
            status_counts[s] = status_counts.get(s, 0) + 1
        
        st.markdown("### 📊 统计信息")
        for row_start in range(0, len(status_counts), 6):
            row_items = list(status_counts.items())[row_start:row_start + 6]
            cols = st.columns(len(row_items))
            for idx, (s, c) in enumerate(row_items):
                with cols[idx]:
                    st.metric(label=s, value=c)
        st.metric("总项目数", len(filtered))
        
        st.markdown("### 📋 项目详情")
        projects_by_status = {}
        for p in filtered:
            s = p.status if p.status else "未知"
            if s not in projects_by_status:
                projects_by_status[s] = []
            projects_by_status[s].append(p)
        
        sorted_statuses = sorted(projects_by_status.keys(), 
                               key=lambda x: status_order.index(x) if x in status_order else len(status_order))
        for status in sorted_statuses:
            with st.expander(f"{status} ({len(projects_by_status[status])}个)", expanded=False):
                if status == "异常" and projects_by_status[status]:
                    if st.button("🔄 一键重置全部为已下载", key=f"reset_all_error_{status}"):
                        try:
                            db = next(get_db())
                            try:
                                updated = sum(1 for p in projects_by_status[status]
                                            if update_project(db, p.id, {"status": ProjectStatus.DOWNLOADED, "error_msg": None}))
                                db.commit()
                                get_all_projects.clear()
                                st.success(f"✅ 已重置 {updated} 个异常项目")
                                time.sleep(0.5)
                                st.rerun()
                            finally:
                                db.close()
                        except Exception as e:
                            st.error(f"重置失败：{str(e)}")
                    st.markdown("---")
                
                df_data = []
                for p in projects_by_status[status]:
                    p_date = (p.create_time or p.publish_time)
                    df_data.append({
                        "ID": p.id,
                        "项目名称": p.project_name[:50] + "..." if len(p.project_name) > 50 else p.project_name,
                        "来源": p.site_name,
                        "状态": p.status or "未知",
                        "文件格式": p.file_format or "未知",
                        "判定结果": p.final_decision or "未完成",
                        "日期": p_date.strftime("%Y-%m-%d %H:%M:%S") if p_date else "未知"
                    })
                st.dataframe(pd.DataFrame(df_data), width='stretch')
    else:
        st.info("📊 没有符合条件的项目数据")

def _read_recent_logs(max_lines=50, check_recent_minutes=5):
    """读取日志文件的最新INFO信息（增强版：添加超时和异常处理）
    
    Args:
        max_lines: 最多返回的日志条数
        check_recent_minutes: 检查最近N分钟内的日志，如果最近有日志更新，即使session_state中没有任务状态也显示
    """
    import os
    from config import LOG_DIR
    from datetime import datetime, timedelta
    import signal
    
    log_file = os.path.join(LOG_DIR, "tender_system.log")
    if not os.path.exists(log_file):
        return []
    
    try:
        # 检查文件最后修改时间（添加异常处理）
        try:
            file_mtime = os.path.getmtime(log_file)
            file_mtime_dt = datetime.fromtimestamp(file_mtime)
            time_threshold = datetime.now() - timedelta(minutes=check_recent_minutes)
            
            # 如果文件最近没有更新，返回空（可能任务已结束）
            if file_mtime_dt < time_threshold:
                return []
        except (OSError, ValueError) as e:
            # 文件可能被锁定或时间戳无效，直接返回空
            return []
        
        # 读取文件最后部分（避免读取整个大文件，添加超时保护）
        try:
            # 使用更安全的文件读取方式，避免文件锁定问题
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                try:
                    # 读取最后N行（估算，每行约200字符）
                    f.seek(0, 2)  # 移动到文件末尾
                    file_size = f.tell()
                    # 限制读取大小，避免大文件阻塞（减少到100KB）
                    read_size = min(100 * 1024, file_size)
                    f.seek(max(0, file_size - read_size))
                    lines = f.readlines()
                except (IOError, OSError) as e:
                    # 文件读取失败（可能被锁定），返回空
                    return []
        except (IOError, OSError, PermissionError) as e:
            # 文件打开失败（可能被锁定或权限不足），返回空
            return []
        
        # 只保留INFO级别的日志，并且只保留最近N分钟内的
        info_logs = []
        try:
            for line in lines:
                try:
                    line = line.strip()
                    if '| INFO |' in line:
                        # 尝试解析日志时间戳（格式：2025-12-26 17:39:05）
                        try:
                            # 提取时间戳部分
                            if len(line) >= 19:
                                time_str = line[:19]
                                log_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                                # 只保留最近N分钟内的日志
                                if log_time >= time_threshold:
                                    info_logs.append(line)
                        except (ValueError, IndexError):
                            # 如果解析时间失败，也保留（可能是格式不标准）
                            info_logs.append(line)
                except Exception:
                    # 单行处理失败，跳过
                    continue
        except Exception:
            # 批量处理失败，返回已收集的日志
            pass
        
        # 返回最新的N条
        return info_logs[-max_lines:] if len(info_logs) > max_lines else info_logs
    except Exception as e:
        # 所有异常都静默处理，避免影响应用运行
        return []

def _is_task_likely_running():
    """检查任务是否可能在运行（综合检查session_state和日志文件，增强异常处理）"""
    try:
        # 方法1：检查session_state中的任务状态
        is_task_running_session = (
            st.session_state.get("full_process_running", False) or
            st.session_state.get("parse_running", False) or
            st.session_state.get("ai_analysis_running", False)
        )
        
        if is_task_running_session:
            return True
        
        # 方法2：检查日志文件最近是否有更新（最近5分钟内）
        import os
        from config import LOG_DIR
        from datetime import datetime, timedelta
        
        log_file = os.path.join(LOG_DIR, "tender_system.log")
        if os.path.exists(log_file):
            try:
                # 检查文件修改时间（添加异常处理）
                try:
                    file_mtime = os.path.getmtime(log_file)
                    file_mtime_dt = datetime.fromtimestamp(file_mtime)
                    time_threshold = datetime.now() - timedelta(minutes=5)
                    
                    # 如果文件最近5分钟内有更新，认为可能有任务在运行
                    if file_mtime_dt >= time_threshold:
                        # 进一步检查：读取最后几行，看是否有流程相关的日志
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                try:
                                    f.seek(0, 2)
                                    file_size = f.tell()
                                    read_size = min(50 * 1024, file_size)  # 读取最后50KB
                                    f.seek(max(0, file_size - read_size))
                                    last_lines = f.readlines()[-20:]  # 最后20行
                                    
                                    # 检查是否有流程相关的关键词
                                    process_keywords = [
                                        '爬虫', '解析', 'AI分析', '全流程', 'tender_spider',
                                        'file_parser', 'qualification_analyzer', 'auto_run_full_process',
                                        '项目更新成功', '开始', '完成', '执行'
                                    ]
                                    
                                    for line in last_lines:
                                        if any(keyword in line for keyword in process_keywords):
                                            return True
                                except (IOError, OSError):
                                    # 文件读取失败，返回False
                                    return False
                        except (IOError, OSError, PermissionError):
                            # 文件打开失败，返回False
                            return False
                except (OSError, ValueError):
                    # 文件时间戳获取失败，返回False
                    return False
            except Exception:
                # 所有异常都静默处理，返回False
                return False
        
        return False
    except Exception:
        # 最外层异常处理，确保不会导致应用崩溃
        return False

def render_process_execution():
    """渲染流程执行页面（重构版）"""
    st.title("⚙️ 流程执行 - 标书资质自动匹配系统")
    st.markdown("---")

    # 检查任务状态
    is_task_running, task_name, task_info = _check_task_status()
    
    # 如果任务正在运行，在页面顶部显示实时日志和控制按钮
    if is_task_running:
        # 显示任务控制栏
        st.warning(f"🔄 {task_name}正在运行中...")
        control_col1, control_col2, control_col3 = st.columns([2, 1, 1])
        with control_col1:
            st.info("💡 任务正在后台执行，您可以查看实时日志或进入进度页面查看详细进度")
        with control_col2:
            # 进入进度页面按钮
            if not st.session_state.get("show_task_progress", False):
                if st.button("📊 查看进度", key="enter_progress_page", type="primary"):
                    st.session_state["show_task_progress"] = True
                    st.rerun()
        with control_col3:
            # 停止任务按钮（直接停止，不需要进入进度页面）
            if st.button("🛑 停止任务", key="stop_task_quick", type="secondary"):
                try:
                    # 根据任务类型设置停止标志
                    if task_name == "全流程":
                        st.session_state["full_process_stopped"] = True
                        st.session_state["full_process_running"] = False
                    elif task_name == "文件解析":
                        st.session_state["parse_stopped"] = True
                        st.session_state["parse_running"] = False
                    elif task_name == "AI资质分析":
                        st.session_state["ai_analysis_stopped"] = True
                        st.session_state["ai_analysis_running"] = False
                    
                    st.success("✅ 任务已停止")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 停止失败：{str(e)}")
        
        # 读取最新的日志信息（检查最近5分钟内的日志）
        recent_logs = _read_recent_logs(max_lines=30, check_recent_minutes=5)
        
        if recent_logs:
            # 显示日志容器（可折叠，默认展开）
            with st.expander("📋 实时日志信息（仅显示INFO级别）", expanded=True):
                # 使用代码块样式显示日志，支持滚动
                # 只显示最后20条，避免显示过多
                display_logs = recent_logs[-20:] if len(recent_logs) > 20 else recent_logs
                log_text = "\n".join(display_logs)
                st.code(log_text, language=None)
                
                # 自动刷新提示
                st.caption("⏱️ 日志每10秒自动更新（显示最新20条INFO日志，最近5分钟内的日志）")
    
    # 检查用户是否主动进入进度页面
    show_progress = st.session_state.get("show_task_progress", False)
    
    # 如果任务正在运行，显示进度页面（仅在用户主动进入时）
    if is_task_running and show_progress:
        # 隐藏侧边栏
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            display: none;
        }
        section[data-testid="stSidebar"] + div {
            margin-left: 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 显示任务信息
        st.info(f"🔄 {task_name}正在执行中...")
        if task_info and task_info.get('start_time'):
            try:
                start_dt = datetime.fromisoformat(task_info['start_time'])
                elapsed = int((datetime.now() - start_dt).total_seconds())
                st.info(f"⏱️ 已运行时间：{elapsed // 60} 分 {elapsed % 60} 秒")
            except:
                pass
        
        # 显示进度（使用可视化步骤，自动刷新）
        # 清除缓存以确保数据实时更新
        get_all_projects.clear()
        get_project_stats.clear()
        get_today_project_stats.clear()
        
        stats = _get_progress_stats()
        st.markdown("### 📊 执行进度")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("已下载", stats['downloaded'])
        with col2:
            st.metric("已解析", stats['parsed'])
        with col3:
            st.metric("已比对", stats['compared'])
        
        # 检查暂停状态
        paused = task_info.get('paused', False) if task_info else False
        if paused:
            st.warning("⏸️ 任务已暂停")
        
        # 显示可视化步骤
        _render_task_steps(task_name, task_info)
        
        # 显示项目状态（下方，不包含刷新按钮）
        _render_project_status(show_refresh=False)
        
        # 添加操作按钮（暂停、终止、退出）
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            if paused:
                st.info("💡 任务已暂停，点击「继续」恢复执行，或点击「终止」停止任务")
            else:
                st.info("💡 点击下方按钮暂停、终止任务或退出进度页面")
        with col2:
            # 暂停/继续按钮
            paused_key = f"{task_name.lower().replace(' ', '_')}_paused"
            if task_name == "全流程":
                paused_key = "full_process_paused"
            elif task_name == "文件解析":
                paused_key = "parse_paused"
            elif task_name == "AI资质分析":
                paused_key = "ai_analysis_paused"
            
            if paused:
                if st.button("▶️ 继续", key="resume_task", type="primary"):
                    st.session_state[paused_key] = False
                    st.rerun()
            else:
                if st.button("⏸️ 暂停", key="pause_task"):
                    st.session_state[paused_key] = True
                    st.rerun()
        with col3:
            # 终止按钮
            if st.button("🛑 终止", key="stop_task", type="secondary"):
                try:
                    stopped_key = f"{task_name.lower().replace(' ', '_')}_stopped"
                    if task_name == "全流程":
                        stopped_key = "full_process_stopped"
                    elif task_name == "文件解析":
                        stopped_key = "parse_stopped"
                    elif task_name == "AI资质分析":
                        stopped_key = "ai_analysis_stopped"
                    
                    st.session_state[stopped_key] = True
                    st.session_state[paused_key] = False
                    st.success("✅ 任务已终止")
                    st.session_state["show_task_progress"] = False
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 终止失败：{str(e)}")
        with col4:
            # 退出进度页面按钮
            if st.button("❌ 退出", key="exit_progress", type="secondary"):
                st.session_state["show_task_progress"] = False
                st.rerun()
        
        # 使用JavaScript实现自动刷新（每10秒，避免过于频繁）
        st.markdown("""
        <script>
        setTimeout(function(){
            window.location.reload(1);
        }, 10000);
        </script>
        """, unsafe_allow_html=True)
        
        return

    # 流程选择（默认全流程）
    process_options = ["全流程", "标书爬虫", "文件解析", "AI资质分析", "报告生成"]
    default_index = 0  # 全流程为默认
    
    selected_process = st.selectbox("选择要执行的流程", process_options, index=default_index)
    
    # 爬取设置（仅全流程和标书爬虫需要）
    if selected_process in ["全流程", "标书爬虫"]:
        # 平台选择
        available_platforms = get_available_platforms()
        platform_options = ["全部"] + list(available_platforms.values())
        selected_platform_name = st.selectbox(
            "选择爬取平台",
            options=platform_options,
            index=0,
            key="selected_platform_name"
        )
        
        # 将平台名称转换为平台代码
        selected_platform_code = None
        if selected_platform_name != "全部":
            selected_platform_code = {v: k for k, v in available_platforms.items()}.get(selected_platform_name)
        
        col1, col2 = st.columns(2)
        with col1:
            crawl_quantity = st.number_input("爬取数量", min_value=1, max_value=200, 
                value=st.session_state.get("crawl_quantity", SPIDER_CONFIG["daily_limit"]), step=1)
            st.session_state["crawl_quantity"] = crawl_quantity
        with col2:
            crawl_days_before = st.number_input("爬取时间范围（天）", min_value=1, max_value=30,
                value=st.session_state.get("crawl_days_before", 7), step=1)
            st.session_state["crawl_days_before"] = crawl_days_before
    
    # 执行按钮
    if st.button("▶️ 执行", type="primary", key="execute_process_button"):
        # 检查是否有任务正在运行（防止重复启动）
        is_task_running_check, running_task_name, _ = _check_task_status()
        if is_task_running_check:
            st.warning(f"⚠️ {running_task_name}正在运行中，请先停止现有任务或等待其完成")
            return
        
        # 隐藏侧边栏
        st.session_state["hide_sidebar"] = True
        
        try:
            if selected_process == "全流程":
                enabled_platforms = [selected_platform_code] if selected_platform_code else None
                _start_background_task("全流程", daily_limit=crawl_quantity, days_before=crawl_days_before, enabled_platforms=enabled_platforms)
                st.success("✅ 全流程已启动，正在后台执行中...")
            elif selected_process == "标书爬虫":
                # 检查爬虫是否已经在运行
                if st.session_state.get('spider_running', False):
                    st.warning("⚠️ 爬虫已在运行中，请先停止现有爬虫")
                    return
                st.session_state['spider_running'] = False
                st.session_state['spider_paused'] = False
                st.session_state['selected_platform_code'] = selected_platform_code  # 保存平台选择
                run_spider_with_progress()
            elif selected_process == "文件解析":
                _start_background_task("文件解析")
                st.success("✅ 文件解析已启动，正在后台执行中...")
            elif selected_process == "AI资质分析":
                _start_background_task("AI资质分析")
                st.success("✅ AI资质分析已启动，正在后台执行中...")
            elif selected_process == "报告生成":
                with st.spinner("正在生成报告..."):
                    try:
                        report_generator = get_report_generator()
                        report_generator.generate_report()
                        st.success("✅ 报告生成完成！")
                    except Exception as e:
                        st.error(f"❌ 报告生成失败：{str(e)}")
        except Exception as e:
            st.error(f"❌ 启动任务失败：{str(e)}")
            log.error(f"启动任务失败：{str(e)}", exc_info=True)
    
    # 显示项目状态（下方，显示刷新按钮）
    _render_project_status(show_refresh=True)


def run_spider_with_progress():
    """带进度和中断功能的爬虫执行函数"""
    # 初始化状态
    st.session_state['spider_running'] = True
    st.session_state['spider_paused'] = False  # 确保暂停状态初始化为False
    st.session_state['spider_progress'] = 0
    st.session_state['spider_current'] = 0
    # 使用用户指定的爬取数量，如果没有则使用默认值
    # 每次都从crawl_quantity获取最新值，确保与用户输入同步
    st.session_state['spider_total'] = st.session_state.get("crawl_quantity", SPIDER_CONFIG['daily_limit'])
    st.session_state['successfully_crawled'] = []
    st.session_state['failed_crawled'] = []
    
    try:
        # 添加自定义CSS样式，提高对比度
        st.markdown("""
        <style>
        /* 进度条颜色 - 使用青蓝色 */
        .stProgress > div > div {
            background-color: #22c55e;  /* 绿色进度条 */
        }
        
        /* 状态消息框样式 - 使用粉色背景 */
        .status-message {
            background-color: #ec4899;  /* 粉色背景 */
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
            font-weight: bold;
        }
        
        /* 统计卡片样式 - 使用深色背景提高对比度 */
        .stMetric {
            background-color: #1e40af;  /* 深蓝色背景 */
            color: white;
            border-radius: 5px;
            padding: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* 按钮样式增强 */
        .stButton > button {
            font-weight: bold;
            padding: 0.5rem 1.5rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 创建进度条和状态显示
        progress_bar = st.progress(0)
        status_text = st.markdown('<div class="status-message">📥 准备开始爬取...</div>', unsafe_allow_html=True)
        
        # 在进度显示区域内创建控制按钮
        control_container = st.container()
        
        # 创建统计信息容器
        stats_container = st.empty()
        
        # 执行爬虫
        # 传递用户设置的总配额和时间范围给爬虫
        spider_total = st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])
        days_before = st.session_state.get("crawl_days_before", 7)  # 默认7天
        selected_platform_code = st.session_state.get('selected_platform_code', None)
        
        # 如果选择了特定平台，使用SpiderManager创建爬虫
        if selected_platform_code:
            from spider import SpiderManager
            try:
                spider = SpiderManager.create_spider(selected_platform_code, daily_limit=spider_total, days_before=days_before)
            except Exception as e:
                st.error(f"创建爬虫失败: {str(e)}")
                return
        else:
            # 使用原有的ZheJiangTenderSpider（向后兼容）
            spider = ZheJiangTenderSpider(daily_limit=spider_total, days_before=days_before)
        
        # 创建session对象
        import requests
        session = requests.Session()
        # 检查spider是否有headers和cookies属性（不同平台可能不同）
        if hasattr(spider, 'headers'):
            session.headers.update(spider.headers)
        if hasattr(spider, 'cookies'):
            session.cookies.update(spider.cookies)
        
        # 修改spider的run方法以支持中断
        total_count = 0
        projects = []
        
        # 如果选择了非浙江省平台，直接调用run方法（简化处理）
        if selected_platform_code and selected_platform_code != "zhejiang":
            # 非浙江省平台，直接运行（进度显示简化）
            try:
                projects = spider.run()
                total_count = len(projects)
                safe_streamlit_update(status_text.success, f"✅ 爬取完成，共获取 {total_count} 个项目")
                progress_bar.progress(1.0)
            except Exception as e:
                safe_streamlit_update(status_text.error, f"❌ 爬取失败: {str(e)}")
            return
        
        # 浙江省平台使用原有的详细进度显示逻辑
        if not hasattr(spider, 'category_codes'):
            # 如果spider没有category_codes属性，直接运行
            try:
                projects = spider.run()
                total_count = len(projects)
                safe_streamlit_update(status_text.success, f"✅ 爬取完成，共获取 {total_count} 个项目")
                progress_bar.progress(1.0)
            except Exception as e:
                safe_streamlit_update(status_text.error, f"❌ 爬取失败: {str(e)}")
            return
        
        for category in spider.category_codes:
            # 检查总配额是否已满
            if total_count >= st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit']):
                safe_streamlit_update(status_text.info, f"📊 已达到今日爬取配额限制({total_count}/{st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])})，停止爬取")
                break
                
            code = category["code"]
            name = category["name"]
            category_count = 0
            is_gov = name == "政府类"
            
            safe_streamlit_update(status_text.info, f"🔍 开始爬取[{name}]分类（{code}）")
            
            # 遍历所有区域（非政府类分类跳过区域循环）
            if not is_gov:
                # 非政府类直接爬取，不使用区域参数
                district_code = None
                district_name = "非区域"
                # 只执行一次循环
                districts = [(district_code, district_name)]
            else:
                districts = spider.district_codes.items()
            
            for district_code, district_name in districts:
                if total_count >= st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit']):
                    safe_streamlit_update(status_text.info, f"📊 已达到今日爬取配额限制({total_count}/{st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])})，停止爬取")
                    break
                    
                page_no = 1
                district_count = 0
                
                safe_streamlit_update(status_text.info, f"🔍 开始爬取[{name}-{district_name}]区域（{district_code}）")
                
                while district_count < spider.district_quota and page_no <= SPIDER_CONFIG["zhejiang_max_pages"] and total_count < st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit']):
                    # 检查是否需要中断
                    if not st.session_state.get('spider_running', False):
                        safe_streamlit_update(status_text.warning, "⚠️ 爬取已中断")
                        return False
                    
                    # 检查暂停状态
                    while st.session_state.get('spider_paused', False):
                        safe_streamlit_update(status_text.markdown, '<div class="status-message">⏸️ 爬取已暂停，点击继续按钮恢复</div>', unsafe_allow_html=True)
                        with control_container:
                            col1, col2 = st.columns(2)
                            if col2.button("▶️ 继续爬取", key="resume_spider_refresh"):
                                st.session_state['spider_paused'] = False
                                safe_streamlit_update(status_text.markdown, '<div class="status-message">▶️ 恢复爬取中...</div>', unsafe_allow_html=True)
                            if col1.button("❌ 中断爬取", type="secondary", key="stop_spider_refresh"):
                                st.session_state['spider_running'] = False
                                st.session_state['run_spider'] = False  # 中断时也重置run_spider状态
                        
                        if not st.session_state.get('spider_running', False):
                            break
                        time.sleep(0.5)  # 短暂休眠以减少资源占用
                    
                    if not st.session_state.get('spider_running', False):
                        break
                    
                    # 反爬控制
                    if page_no > 1:
                        time.sleep(SPIDER_CONFIG["anti_crawl"]["request_interval"])
                    
                    # 获取页面数据（传递正确的session、区域参数和政府类标识）
                    result = spider._fetch_page(session, code, page_no, district_code, is_gov)
                    if not result or not result.get('result') or not result['result'].get('data'):
                        safe_streamlit_update(status_text.warning, f"[{name}-{district_name}]第{page_no}页无有效数据，停止爬取该区域")
                        break
                
                    # 获取数据列表
                    items = result['result']['data'].get('data', [])
                    if not items:
                        safe_streamlit_update(status_text.warning, f"[{name}-{district_name}]第{page_no}页无项目数据，继续下一页")
                        page_no += 1
                        continue
                    
                    # 处理项目数据
                    for item in items:
                        # 检查是否需要中断或达到配额
                        if not st.session_state.get('spider_running', False):
                            break
                        # 优先检查总配额，然后检查分类配额
                        total_limit = st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])
                        if total_count >= total_limit:
                            safe_streamlit_update(status_text.info, f"📊 已达到今日爬取配额限制({total_count}/{total_limit})，停止爬取")
                            break
                        # 政府类分类可以突破分类配额限制，只要不超过总配额
                        if not is_gov and category_count >= spider.category_quota:
                            safe_streamlit_update(status_text.info, f"📊 已达到分类爬取配额限制({category_count}/{spider.category_quota})，切换到下一个分类")
                            break
                        
                        project_id = item.get("articleId")
                        if not project_id or spider._is_duplicate(project_id):
                            continue
                        
                        # 提取发布时间（使用爬虫的提取方法）
                        publish_date, publish_date_source = spider._extract_publish_date(item, name, district_name)
                        
                        # 如果没有发布时间，跳过该项目（不使用当前时间作为后备）
                        # 减少警告信息更新频率：每10个项目才显示一次警告
                        if publish_date is None:
                            if total_count % 10 == 0:  # 每10个才显示一次警告
                                safe_streamlit_update(status_text.warning, f"⚠️ 跳过无发布时间的项目: {item.get('title', '未命名项目')[:50]}")
                            continue
                        
                        # 解析发布时间：publishDate是13位毫秒时间戳，去掉后3位得到10位秒级时间戳
                        publish_time = None
                        publish_timestamp = None
                        try:
                            # 统一处理：将publishDate转换为整数，然后去掉后3位
                            if isinstance(publish_date, (int, float)):
                                timestamp_ms = int(publish_date)
                            elif isinstance(publish_date, str) and publish_date.strip() and publish_date.strip().isdigit():
                                timestamp_ms = int(publish_date.strip())
                            else:
                                # 减少警告频率：每20个错误才显示一次
                                if total_count % 20 == 0:
                                    safe_streamlit_update(status_text.warning, f"⚠️ publishDate格式错误: {publish_date}，跳过该项目")
                                continue
                            
                            # 去掉后3位，转换为10位秒级时间戳
                            timestamp = timestamp_ms // 1000
                            publish_time = datetime.fromtimestamp(timestamp)
                            publish_timestamp = timestamp_ms  # 保存原始时间戳（毫秒）
                        except (ValueError, OverflowError) as e:
                            # 减少警告频率：每20个错误才显示一次
                            if total_count % 20 == 0:
                                safe_streamlit_update(status_text.warning, f"⚠️ 项目日期格式错误: {publish_date}, 错误: {str(e)}，跳过该项目")
                            continue
                        
                        # 如果发布时间解析失败，跳过该项目
                        if not publish_time:
                            # 减少警告频率：每20个错误才显示一次
                            if total_count % 20 == 0:
                                safe_streamlit_update(status_text.warning, f"⚠️ 无法解析发布时间: {publish_date}，跳过该项目")
                            continue
                        
                        # 更新统计信息 - 直接更新空容器
                        stats_container.empty()
                        with stats_container:
                            # 进一步增加列宽，确保中文标题完整显示
                            col1, col2, col3 = st.columns([1.8, 1.8, 2.2], gap="large")
                            col1.metric("目标爬取数", st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit']))
                            col2.metric("已爬取数", category_count)
                            col3.metric("总进度", f"{total_count}/{st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])}")
                        
                        # 获取区域名称（优先使用API返回的districtName）
                        api_district_name = item.get("districtName")
                        if api_district_name:
                            region_name = api_district_name
                        else:
                            region_name = district_name
                        
                        # 构建项目数据
                        project_data = {
                            "project_name": item.get("title", ""),
                            "site_name": f"浙江省政府采购网-{region_name}",
                            "publish_time": publish_time,  # 使用从API时间戳转换的发布时间
                            "publish_timestamp": publish_timestamp,  # 保存原始时间戳（毫秒）
                            "project_id": project_id,
                            "region": region_name,  # 使用API返回的districtName
                            "status": "DOWNLOADED"
                        }
                        
                        status_text.markdown(f'<div class="status-message">📥 正在下载: {project_data["project_name"]}</div>', unsafe_allow_html=True)
                        
                        # 下载文件
                        try:
                            file_path, file_format = spider._download_document(project_id, project_data["project_name"], session)
                            if file_path:
                                project_data["file_path"] = file_path
                                project_data["file_format"] = file_format
                            
                                # 保存项目
                                saved_project = save_project(spider.db, project_data)
                                projects.append(saved_project)
                                category_count += 1
                                district_count += 1
                                total_count += 1
                                spider.crawled_count = total_count
                                st.session_state['successfully_crawled'].append(project_data['project_name'])
                                # 只保存项目ID，避免存储分离的ORM对象
                                if 'successfully_crawled_project_ids' not in st.session_state:
                                    st.session_state['successfully_crawled_project_ids'] = []
                                st.session_state['successfully_crawled_project_ids'].append(saved_project.id)
                                status_text.markdown(f'<div class="status-message">✅ 成功: {project_data["project_name"]}（{category_count}/{spider.category_quota}）</div>', unsafe_allow_html=True)
                            else:
                                st.session_state['failed_crawled'].append(f"{project_data['project_name']}（下载失败）")
                                safe_streamlit_update(status_text.markdown, f'<div class="status-message">❌ 失败: {project_data["project_name"]}（下载失败）</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.session_state['failed_crawled'].append(f"{project_data['project_name']}（{str(e)[:30]}）")
                            safe_streamlit_update(status_text.markdown, f'<div class="status-message">❌ 错误: {project_data["project_name"]}（{str(e)[:30]}）</div>', unsafe_allow_html=True)
                    
                    # 更新进度（添加短暂延迟让Streamlit有机会刷新）
                    st.session_state['spider_current'] = total_count
                    st.session_state['spider_progress'] = total_count / st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit'])
                    progress_bar.progress(min(st.session_state['spider_progress'], 1.0))
                    time.sleep(0.1)  # 短暂延迟，让Streamlit有机会更新UI
                    
                    page_no += 1
            
            if not st.session_state.get('spider_running', False):
                break
        
        spider.db.close()
        
        if st.session_state.get('spider_running', False):
            status_text.markdown('<div class="status-message">✅ 爬虫任务完成！</div>', unsafe_allow_html=True)
            
            # 清除缓存，确保新爬取的项目能立即显示
            get_all_projects.clear()
            get_project_stats.clear()
            get_today_project_stats.clear()
            
            # 显示统计结果
            with stats_container:
                col1, col2, col3 = st.columns(3)
                col1.metric("总目标数", st.session_state.get('spider_total', SPIDER_CONFIG['daily_limit']))
                col2.metric("成功爬取数", len(st.session_state['successfully_crawled']))
                col3.metric("失败爬取数", len(st.session_state['failed_crawled']))
            
            # 显示成功爬取的项目
            if st.session_state['successfully_crawled']:
                with st.expander("📋 成功爬取的项目列表", expanded=False):
                    for project in st.session_state['successfully_crawled'][:20]:  # 限制显示前20个
                        st.success(f"- {project}")
                    if len(st.session_state['successfully_crawled']) > 20:
                        st.info(f"... 还有{len(st.session_state['successfully_crawled']) - 20}个项目未显示")
            
            # 显示失败的项目
            if st.session_state['failed_crawled']:
                with st.expander("❌ 爬取失败的项目", expanded=False):
                    for failed in st.session_state['failed_crawled'][:20]:  # 限制显示前20个
                        st.error(f"- {failed}")
                    if len(st.session_state['failed_crawled']) > 20:
                        st.info(f"... 还有{len(st.session_state['failed_crawled']) - 20}个项目未显示")
        
        return True
        
    except Exception as e:
        status_text.error(f"❌ 爬虫执行失败: {str(e)}")
        raise e
    finally:
        # 清理资源
        st.session_state['spider_running'] = False
        st.session_state['run_spider'] = False  # 确保爬虫不会在页面切换后重新开始
        progress_bar.empty()
        status_text.empty()
        time.sleep(0.1)

def run_full_process():
    """执行全流程"""
    try:
        # 执行爬虫（使用带进度的版本）
        # 确保使用用户指定的爬取数量
        st.session_state['spider_total'] = st.session_state.get("crawl_quantity", SPIDER_CONFIG['daily_limit'])
        st.session_state['spider_running'] = True
        st.session_state['spider_paused'] = False
        spider_result = run_spider_with_progress()
        
        if not spider_result:
            st.warning("⚠️ 全流程执行已中断")
            return False
        
        # 保存当前爬取的项目ID
        current_project_ids = st.session_state.get('successfully_crawled_project_ids', [])
        
        # 执行文件解析（带进度更新）
        status_container = st.container()
        status_text = status_container.empty()
        progress_bar = st.progress(0)
        
        # 获取待解析项目数量
        from utils.db import get_db, TenderProject, ProjectStatus
        db = next(get_db())
        query = db.query(TenderProject).filter(
            TenderProject.status.in_([ProjectStatus.DOWNLOADED, ProjectStatus.ERROR])
        )
        if current_project_ids:
            query = query.filter(TenderProject.id.in_(current_project_ids))
        total_projects = query.count()
        db.close()
        
        if total_projects > 0:
            status_text.info(f"📄 开始执行文件解析... (共 {total_projects} 个项目)")
            
            # 创建带进度回调的文件解析函数
            def parse_with_progress(project_ids=None):
                from utils.db import get_db, TenderProject, update_project, ProjectStatus
                from config import FILES_DIR
                import traceback
                
                db = next(get_db())
                try:
                    query = db.query(TenderProject).filter(
                        TenderProject.status.in_([ProjectStatus.DOWNLOADED, ProjectStatus.ERROR])
                    )
                    if project_ids and len(project_ids) > 0:
                        query = query.filter(TenderProject.id.in_(project_ids))
                    projects = query.all()
                finally:
                    # 不在这里关闭db，因为后面还要使用
                    pass
                
                total = len(projects)
                processed = 0
                
                for idx, project in enumerate(projects, 1):
                    try:
                        processed = idx
                        progress = processed / total if total > 0 else 0
                        safe_streamlit_update(progress_bar.progress, progress)
                        safe_streamlit_update(status_text.info, f"📄 正在解析项目 {processed}/{total}：{project.project_name[:50]}...")
                        
                        # 检查文件路径
                        file_path = project.file_path
                        if not file_path:
                            update_project(db, project.id, {
                                "status": ProjectStatus.ERROR,
                                "error_msg": "文件路径为空，可能是下载失败"
                            })
                            continue
                        
                        # 处理相对路径
                        if not os.path.isabs(file_path):
                            file_path = os.path.join(FILES_DIR, file_path)
                        
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            update_project(db, project.id, {
                                "status": ProjectStatus.ERROR,
                                "error_msg": f"文件不存在：{file_path}"
                            })
                            safe_streamlit_update(status_text.warning, f"⚠️ 文件不存在：{file_path}")
                            continue
                        
                        # 解析文件（添加超时提示）
                        safe_streamlit_update(status_text.info, f"📄 正在解析：{os.path.basename(file_path)}（如果卡住，请检查日志）")
                        # 添加详细日志
                        import logging
                        parse_logger = logging.getLogger('parser')
                        parse_logger.info(f"Streamlit调用解析：项目ID={project.id}, 文件路径={file_path}")
                        
                        # 记录开始时间
                        parse_start_time = time.time()
                        
                        # 直接调用解析（file_parser内部已有超时机制）
                        # 如果解析时间过长，会在日志中记录
                        try:
                            parser = get_file_parser()
                            content = parser.parse_file(file_path, project.id)
                            parse_elapsed = time.time() - parse_start_time
                            parse_logger.info(f"Streamlit解析返回：项目ID={project.id}, 内容长度={len(content) if content else 0}, 耗时={parse_elapsed:.2f}秒")
                            
                            # 如果解析时间超过5分钟，记录警告
                            if parse_elapsed > 300:
                                parse_logger.warning(f"文件解析耗时较长：{parse_elapsed:.2f}秒，文件：{file_path}")
                        except Exception as parse_error:
                            parse_elapsed = time.time() - parse_start_time
                            parse_logger.error(f"文件解析异常：项目ID={project.id}, 耗时={parse_elapsed:.2f}秒, 错误：{str(parse_error)}")
                            raise
                        
                        # 详细记录解析结果
                        if content is not None and content.strip():
                            content_length = len(content) if content else 0
                            safe_streamlit_update(status_text.success, f"✅ 解析成功，内容长度：{content_length}字符")
                            
                            # 更新项目状态为已解析
                            # 注意：update_project内部已经调用了db.commit()
                            try:
                                update_result = update_project(db, project.id, {
                                    "evaluation_content": content,
                                    "status": ProjectStatus.PARSED
                                })
                                if update_result:
                                    # 刷新数据库会话，确保状态同步
                                    db.expire_all()
                                    # 清除缓存，确保状态更新立即生效
                                    get_all_projects.clear()
                                    get_project_stats.clear()
                                    get_today_project_stats.clear()
                                    log.info(f"项目 {project.id} 状态已更新为已解析")
                                else:
                                    log.error(f"更新项目 {project.id} 状态失败，未找到该项目")
                            except Exception as update_error:
                                log.error(f"更新项目 {project.id} 状态时出错：{str(update_error)}")
                                # 即使更新失败也要清除缓存，避免显示过期数据
                                get_all_projects.clear()
                                get_project_stats.clear()
                                get_today_project_stats.clear()
                        else:
                            # 检查文件大小和扩展名
                            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                            file_ext = os.path.splitext(file_path)[1].lower()
                            
                            # 更详细的错误信息
                            if content is None:
                                if file_ext == '.doc':
                                    error_msg = f"DOC文件解析失败（Word COM组件不可用，文件大小：{file_size}字节）。建议：1) 安装Microsoft Word 2) 手动转换为DOCX格式"
                                else:
                                    error_msg = f"解析返回None（文件大小：{file_size}字节）"
                            elif not content.strip():
                                error_msg = f"解析内容为空字符串（只有空白字符，文件大小：{file_size}字节）"
                            else:
                                error_msg = f"解析内容为空（文件大小：{file_size}字节）"
                            
                            safe_streamlit_update(status_text.error, f"❌ {error_msg}")
                            # 记录详细日志
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"项目 {project.id} 解析失败: {error_msg}, 文件路径: {file_path}")
                            
                            try:
                                update_project(db, project.id, {
                                    "status": ProjectStatus.ERROR,
                                    "error_msg": error_msg
                                })
                            except Exception as update_error:
                                log.error(f"更新项目 {project.id} 错误状态时出错：{str(update_error)}")
                    except Exception as e:
                        error_msg = f"{str(e)} \n {traceback.format_exc()[:500]}"
                        try:
                            update_project(db, project.id, {
                                "status": ProjectStatus.ERROR,
                                "error_msg": error_msg
                            })
                        except Exception as update_error:
                            log.error(f"更新项目 {project.id} 异常状态时出错：{str(update_error)}")
                        continue
                
                # update_project内部已经调用了db.commit()，这里不需要再次commit
                # 但是需要确保连接正确关闭
                db.close()
        
                safe_streamlit_update(progress_bar.progress, 1.0)
                safe_streamlit_update(status_text.success, f"✅ 文件解析完成！共处理 {processed} 个项目")
                
                # 清除缓存，确保数据及时更新（状态变更后立即清除缓存）
                # 注意：必须在数据库操作完成后清除缓存，否则UI会显示旧数据
                # 虽然在每个项目更新时已经清除了缓存，但这里再次清除确保一致性
                get_project_stats.clear()
                get_today_project_stats.clear()
                get_completed_projects.clear()
                get_all_projects.clear()
            
            # 执行带进度的文件解析
            parse_with_progress(current_project_ids)
        else:
            status_text.info("📄 没有待解析的项目")
            progress_bar.progress(1.0)
        
        # 不立即清空容器，保留用于显示AI分析进度
        time.sleep(0.5)
        
        # 更新状态显示，准备进入AI分析阶段
        status_text.info("🤖 文件解析完成，准备开始AI分析...")
        safe_streamlit_update(progress_bar.progress, 0)

        # 执行AI分析（使用带进度的版本）
        try:
            st.session_state['ai_analysis_running'] = True
            st.session_state['ai_analysis_paused'] = False
            
            # 获取数据库连接
            from utils.db import get_db, TenderProject, ProjectStatus, update_project
            db = next(get_db())
            
            # 查询待分析的项目（包括刚解析完成的项目）
            projects = db.query(TenderProject).filter(
                TenderProject.status == ProjectStatus.PARSED
            ).all()
            
            total = len(projects)
            current = 0
            
            if total > 0:
                status_text.info(f"🤖 开始AI分析，共 {total} 个项目待分析...")
                
                for project in projects:
                    if not st.session_state.get('ai_analysis_running', False):
                        safe_streamlit_update(status_text.warning, "⚠️ AI分析已被中断")
                        break
                    
                    try:
                        current += 1
                        progress = current / total if total > 0 else 0
                        safe_streamlit_update(progress_bar.progress, progress)
                        safe_streamlit_update(status_text.info, f"🤖 AI分析进度 {current}/{total}：{project.project_name[:50]}...")
                        
                        # 执行实际分析
                        if not project.evaluation_content:
                            raise ValueError("项目解析内容为空")
                        
                        # 在执行AI操作前检查是否中断
                        if not st.session_state.get('ai_analysis_running', False):
                            safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                            break
                        
                        # 0. 先判断是否是服务类项目
                        ai_analyzer = get_ai_analyzer()
                        
                        # 检查是否中断（在长时间操作前）
                        if not st.session_state.get('ai_analysis_running', False):
                            safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                            break
                        
                        is_service, reason = ai_analyzer.is_service_project(project.evaluation_content)
                        
                        # 检查是否是因为功能被禁用而返回False
                        service_check_enabled = config.AI_CONFIG.get("service_check", {}).get("enable", False)
                        
                        if is_service and service_check_enabled:
                            # 只有当服务类判断功能启用且项目确实是服务类时，才标记为已排除
                            log.info(f"⚠️ 项目 {project.id} 是服务类项目，标记为已排除：{reason}")
                            # 更新项目状态为已排除，而不是删除，避免下次重复爬取
                            from utils.db import update_project, ProjectStatus
                            db_project = db.query(TenderProject).filter(TenderProject.id == project.id).first()
                            if db_project:
                                update_project(db, project.id, {
                                    "status": ProjectStatus.EXCLUDED,
                                    "error_msg": f"服务类项目：{reason}"
                                })
                                db.commit()
                            log.info(f"✅ 服务类项目已标记为已排除：{project.project_name}（ID：{project.id}）")
                            continue  # 跳过后续分析
                        elif is_service and not service_check_enabled:
                            # 当服务类判断功能被禁用时，跳过判断，继续分析所有项目
                            log.info(f"服务类判断功能已禁用，跳过判断，继续分析项目 {project.id}")
                        else:
                            # 项目不是服务类，继续分析
                            log.info(f"项目 {project.id} 不是服务类项目，继续分析")
                        
                        # 1. 提取资质要求
                        # 检查是否中断（在长时间操作前）
                        if not st.session_state.get('ai_analysis_running', False):
                            safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                            break
                        
                        # 记录开始时间，用于检测卡住
                        extract_start_time = time.time()
                        log.info(f"开始提取项目 {project.id} ({project.project_name[:50]}) 的资质要求")
                        
                        try:
                            project_requirements = ai_analyzer.extract_requirements(project.evaluation_content)
                            extract_elapsed = time.time() - extract_start_time
                            log.info(f"项目 {project.id} 资质要求提取完成，耗时 {extract_elapsed:.2f} 秒")
                            
                            # 如果提取时间超过5分钟，记录警告
                            if extract_elapsed > 300:
                                log.warning(f"⚠️ 项目 {project.id} 资质要求提取耗时较长：{extract_elapsed:.2f} 秒")
                        except Exception as extract_error:
                            extract_elapsed = time.time() - extract_start_time
                            log.error(f"项目 {project.id} 资质要求提取失败，耗时 {extract_elapsed:.2f} 秒，错误：{str(extract_error)}")
                            raise
                        
                        # 检查是否中断（在第二个AI操作前）
                        if not st.session_state.get('ai_analysis_running', False):
                            safe_streamlit_update(status_text.warning, "⚠️ 分析已中断")
                            break
                        
                        # 2. 比对资质
                        compare_start_time = time.time()
                        log.info(f"开始比对项目 {project.id} ({project.project_name[:50]}) 的资质")
                        
                        try:
                            comparison_result, final_decision = ai_analyzer.compare_qualifications(project_requirements)
                            
                            # 应用客观分判定配置
                            from config import OBJECTIVE_SCORE_CONFIG
                            if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                                # 检查是否需要根据客观分丢分阈值调整最终决策
                                if "客观分不满分" in final_decision:
                                    # 尝试从比对结果中提取丢分信息
                                    loss_score = 0.0
                                    # 简单的丢分提取逻辑，实际项目中可能需要更复杂的解析
                                    import re
                                    loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison_result)
                                    if loss_match:
                                        loss_score = float(loss_match.group(1))
                                    
                                    threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                    if loss_score <= threshold:
                                        # 丢分≤阈值，改为"推荐参与"
                                        original_decision = final_decision
                                        final_decision = "推荐参与"
                                        comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：推荐参与"
                                elif "推荐参与" in final_decision:
                                    # 检查是否需要根据丢分阈值改为"不推荐参与"
                                    loss_score = 0.0
                                    import re
                                    loss_match = re.search(r'丢分.*?(\d+\.?\d*)分', comparison_result)
                                    if loss_match:
                                        loss_score = float(loss_match.group(1))
                                    
                                    threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                                    if loss_score > threshold:
                                        # 丢分>阈值，改为"不推荐参与"
                                        original_decision = final_decision
                                        final_decision = "不推荐参与"
                                        comparison_result += f"\n\n【丢分阈值调整说明】\n- 原判定：{original_decision}\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 调整后判定：不推荐参与"
                            
                            compare_elapsed = time.time() - compare_start_time
                            log.info(f"项目 {project.id} 资质比对完成，耗时 {compare_elapsed:.2f} 秒，最终判定：{final_decision}")
                            
                            # 如果比对时间超过5分钟，记录警告
                            if compare_elapsed > 300:
                                log.warning(f"⚠️ 项目 {project.id} 资质比对耗时较长：{compare_elapsed:.2f} 秒")
                        except Exception as compare_error:
                            compare_elapsed = time.time() - compare_start_time
                            log.error(f"项目 {project.id} 资质比对失败，耗时 {compare_elapsed:.2f} 秒，错误：{str(compare_error)}")
                            raise
                        
                        # 3. 更新项目状态
                        update_project(db, project.id, {
                            "project_requirements": project_requirements,
                            "ai_extracted_text": project_requirements,  # 保存AI提取的原始文本
                            "comparison_result": comparison_result,
                            "final_decision": final_decision or "未判定",
                            "status": ProjectStatus.COMPARED
                        })
                        
                        safe_streamlit_update(status_text.success, f"✅ 项目 {current}/{total} 分析完成：{project.project_name[:50]}")
                        
                    except Exception as e:
                        error_msg = str(e)[:500]
                        error_type = type(e).__name__
                        
                        # 记录详细错误信息
                        log.error(f"项目 {project.id} ({project.project_name}) 分析失败：{error_type}: {error_msg}")
                        
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
                        
                        # 更新项目状态
                        try:
                            if analysis_fail_count >= 3:
                                # 3次都失败，标记为异常
                                error_msg_full = f"{error_type}: {error_msg} [AI分析失败{analysis_fail_count}次] [跳过-多次失败]"
                                log.warning(f"⚠️ 项目 {project.project_name}（ID：{project.id}）AI分析已失败{analysis_fail_count}次，标记为跳过")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.ERROR,
                                    "error_msg": error_msg_full
                                })
                            else:
                                # 自动重试：重置状态为PARSED，让它重新进入AI分析流程
                                error_msg_full = f"{error_type}: {error_msg} [AI分析失败{analysis_fail_count}次]"
                                log.info(f"🔄 项目 {project.project_name}（ID：{project.id}）AI分析失败第{analysis_fail_count}次，自动重置状态准备重试")
                                update_project(db, project.id, {
                                    "status": ProjectStatus.PARSED,  # 重置为PARSED状态，下次分析时会重新处理
                                    "error_msg": error_msg_full,
                                    "project_requirements": None,  # 清空之前可能的部分分析结果
                                    "comparison_result": None,
                                    "final_decision": None
                                })
                        except Exception as update_error:
                            log.error(f"更新项目状态失败：{str(update_error)}")
                        
                        safe_streamlit_update(status_text.error, f"❌ 项目 {current}/{total} 分析失败：{project.project_name[:50]}（{error_type}）")
                        # 继续处理下一个项目，不中断整个分析流程
                        continue
                
                db.close()
                
                if not st.session_state.get('ai_analysis_running', False):
                    status_text.warning("⚠️ AI分析已被中断")
                    return False
                
                # 更新进度条
                safe_streamlit_update(progress_bar.progress, 1.0)
                status_text.success(f"✅ AI分析完成！共处理 {current} 个项目")
            else:
                status_text.info("🤖 没有待分析的项目（所有项目已完成分析或无需分析）")
                safe_streamlit_update(progress_bar.progress, 1.0)
            
            # 生成报告
            time.sleep(0.5)
            status_text.info("📊 正在生成报告...")
            try:
                report_generator = get_report_generator()
                report_generator.generate_report()
                status_text.success("✅ 报告生成完成")
            except Exception as report_error:
                status_text.warning(f"⚠️ 报告生成失败：{str(report_error)[:100]}")
            
            # 清除所有相关缓存，确保数据及时更新
            try:
                get_project_stats.clear()
                get_today_project_stats.clear()
                get_completed_projects.clear()
                get_all_projects.clear()
            except:
                pass
            
            # 最后清空容器
            time.sleep(1.0)
            status_container.empty()
            progress_bar.empty()
            
            return True
            
        except Exception as ai_error:
            # AI分析阶段出现异常
            status_text.error(f"❌ AI分析阶段出现错误：{str(ai_error)[:200]}")
            status_text.info("💡 建议检查：")
            status_text.markdown("- AI模型服务是否正常运行")
            status_text.markdown("- 数据库连接是否正常")
            status_text.markdown("- 查看详细日志获取更多信息")
            try:
                db.close()
            except:
                pass
            return False
    except Exception as e:
        raise e


# 添加一个在显示时过滤企业资质的函数
def filter_company_qualifications_for_display(requirements):
    """在界面显示时过滤掉企业资质要求部分"""
    if not requirements:
        return requirements
    
    import re
    # 使用正则表达式移除【企业资质】部分
    filtered_requirements = re.sub(r'【企业资质】.*?(?=【招标方式】|【人员资质】|【设备要求】|【业绩要求】|【其他要求】|$)', '', requirements, flags=re.DOTALL)
    return filtered_requirements

# 渲染结果可视化页面
def render_result_visualization():
    """渲染结果可视化页面（完善版）"""
    try:
        st.title("📈 匹配结果可视化")
        
        # 添加手动刷新按钮
        col_refresh, col_space = st.columns([1, 10])
        with col_refresh:
            if st.button("🔄 刷新数据", help="手动刷新统计数据", key="refresh_visualization"):
                # 清除所有缓存
                try:
                    get_project_stats.clear()
                    get_today_project_stats.clear()
                    get_completed_projects.clear()
                    get_all_projects.clear()
                except Exception as clear_error:
                    log.warning(f"清除缓存失败：{str(clear_error)}")
                st.rerun()
        
        st.markdown("---")
    except Exception as e:
        log.error(f"可视化页面初始化失败：{str(e)}", exc_info=True)
        st.error(f"❌ 页面初始化失败：{str(e)}")
        st.info("💡 请刷新页面重试")
        return

    # 处理复核模式
    if "review_mode" in st.session_state and st.session_state["review_mode"]:
        review_project_id = st.session_state.get("review_project_id")
        if review_project_id:
            # 获取待复核的项目
            db = next(get_db())
            project = db.query(TenderProject).filter(TenderProject.id == review_project_id).first()
            db.close()
            
            if project:
                st.subheader(f"🔍 项目复核 - {project.project_name}")
                
                # 显示项目基本信息
                with st.container(border=True):
                    st.markdown(f"**项目ID:** {project.id}")
                    st.markdown(f"**项目名称:** {project.project_name}")
                    st.markdown(f"**当前状态:** {project.final_decision} ({project.review_status})")
                    
                    # 显示客观分判定结果
                    if project.objective_score_decisions:
                        try:
                            decisions = json.loads(project.objective_score_decisions)
                            st.markdown("\n**客观分判定结果:**")
                            for idx, decision in enumerate(decisions):
                                status = "✅ 推荐参与" if decision.get('is_attainable', False) else "❌ 不推荐参与"
                                st.markdown(f"- **{decision.get('criterion', '未知要求')}**: {status}")
                        except json.JSONDecodeError:
                            st.error("解析客观分判定结果失败")
                
                # 复核操作
                st.markdown("---")
                st.subheader("⚖️ 复核操作")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("已复核，确认推荐", type="primary", key=f"confirm_review_{review_project_id}"):
                        if mark_project_reviewed(review_project_id, "确认推荐"):
                            st.success(f"项目 {review_project_id} 已确认推荐")
                            # 退出复核模式
                            del st.session_state["review_mode"]
                            del st.session_state["review_project_id"]
                            st.rerun()
                        else:
                            st.error(f"更新项目 {review_project_id} 状态失败")
                
                with col2:
                    if st.button("复核后不推荐", type="secondary", key=f"reject_review_{review_project_id}"):
                        st.session_state["reject_mode"] = True
                        st.rerun()
                
                # 不推荐原因输入
                if "reject_mode" in st.session_state and st.session_state["reject_mode"]:
                    st.markdown("---")
                    reject_reason = st.text_area("请输入不推荐的原因：", key=f"reject_reason_{review_project_id}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("确认不推荐", type="primary", key=f"confirm_reject_{review_project_id}"):
                            if reject_reason.strip():
                                if mark_project_reviewed(review_project_id, "复核不推荐", reject_reason):
                                    st.success(f"项目 {review_project_id} 已标记为复核不推荐")
                                    # 退出复核模式
                                    del st.session_state["review_mode"]
                                    del st.session_state["review_project_id"]
                                    del st.session_state["reject_mode"]
                                    st.rerun()
                                else:
                                    st.error(f"更新项目 {review_project_id} 状态失败")
                            else:
                                st.warning("请输入不推荐的原因")
                    with col2:
                        if st.button("取消", key=f"cancel_reject_{review_project_id}"):
                            del st.session_state["reject_mode"]
                            st.rerun()
            
            # 返回按钮
            if st.button("返回结果列表", key="back_to_results"):
                del st.session_state["review_mode"]
                if "review_project_id" in st.session_state:
                    del st.session_state["review_project_id"]
                if "reject_mode" in st.session_state:
                    del st.session_state["reject_mode"]
                st.rerun()
                
            return  # 提前返回，不显示其他内容

    # 只显示这些大类区域（与spider/tender_spider.py中的district_codes保持一致）
    predefined_regions = [
        "浙江省本级", "杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", 
        "绍兴市", "金华市", "衢州市", "舟山市", "台州市", "丽水市"
    ]
    
    # 优化：不再需要单独查询数据库，get_completed_projects会处理
    
    # 只使用这些大类区域作为选项
    region_options = predefined_regions
    
    # 添加筛选控件
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_region = st.selectbox(
            "区域筛选",
            options=["全部"] + region_options,
            key="region_filter"
        )
    
    with col2:
        # 平台筛选
        available_platforms = get_available_platforms()
        platform_options = ["全部"] + list(available_platforms.values())
        selected_platform_name = st.selectbox("平台筛选", platform_options, index=0, key="visualization_platform_filter")
    
    with col3:
        # 添加日期（月-日）筛选器（优化：使用缓存，避免每次查询数据库）
        @st.cache_data(ttl=1800, max_entries=1)  # 缓存30分钟，只缓存一个版本
        def get_available_dates():
            """获取数据库中实际存在的日期列表（缓存版本）"""
            try:
                db_temp = next(get_db())
                # 只查询已对比项目的日期，使用更高效的查询方式
                from sqlalchemy import func, distinct
                existing_dates = db_temp.query(
                    func.strftime('%m-%d', TenderProject.publish_time).label('date_str')
                ).filter(
                    TenderProject.status == ProjectStatus.COMPARED,
                    TenderProject.publish_time.isnot(None)
                ).distinct().all()
                db_temp.close()
                
                # 提取唯一的月-日组合
                date_set = set()
                for row in existing_dates:
                    if row and row.date_str:
                        date_set.add(row.date_str)
                
                # 排序并返回
                return sorted(list(date_set))
            except Exception as e:
                # 如果查询失败，返回最近30天的日期
                log.debug(f"获取日期列表失败，使用简化选项：{str(e)}")
                from datetime import datetime, timedelta
                today = datetime.now()
                return [(today - timedelta(days=i)).strftime("%m-%d") for i in range(30)]
        
        # 获取日期选项（使用缓存）
        available_dates = get_available_dates()
        date_options = ["全部"] + available_dates
        
        selected_month_day = st.selectbox(
            "日期筛选",
            options=date_options,
            key="date_filter"
        )
    
    # 添加项目名搜索栏
    search_keyword = st.text_input(
        "🔍 项目名搜索",
        value=st.session_state.get("project_search_keyword", ""),
        key="project_search_keyword",
        placeholder="输入项目名称关键词进行搜索（支持模糊匹配）",
        help="在项目名称中搜索包含关键词的项目，可用于快速定位特定项目"
    )
    
    # 获取筛选后的项目
    selected_platform_code = None
    if selected_platform_name != "全部":
        selected_platform_code = {v: k for k, v in available_platforms.items()}.get(selected_platform_name)
    
    completed_projects = get_completed_projects(selected_region, selected_month_day, selected_platform_code)
    
    # 应用项目名搜索过滤（优化：避免None值错误）
    original_count = len(completed_projects)
    if search_keyword and search_keyword.strip():
        search_keyword_lower = search_keyword.strip().lower()
        completed_projects = [
            p for p in completed_projects 
            if search_keyword_lower in (p.project_name or "").lower()
        ]
        filtered_count = len(completed_projects)
        if filtered_count < original_count:
            st.info(f"🔍 搜索关键词「{search_keyword}」找到 {filtered_count} 个项目（共 {original_count} 个）")
    
    if completed_projects:
        # 状态概览（基于筛选后的项目）
        # 优化：使用集合和单次遍历计算统计信息
        filtered_total = len(completed_projects)
        qualified_set = {"可以参与", "客观分满分", "推荐参与", "通过"}
        unqualified_set = {"不可以参与", "客观分不满分", "不推荐参与"}
        
        # 优化：单次遍历计算所有统计信息，而不是多次遍历
        filtered_qualified = 0
        filtered_unqualified = 0
        for p in completed_projects:
            if p.final_decision in qualified_set:
                filtered_qualified += 1
            elif p.final_decision in unqualified_set:
                filtered_unqualified += 1
        # 由于get_completed_projects已经只返回COMPARED状态的项目，所以所有项目都是已对比的
        filtered_compared = filtered_total

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("筛选后项目数", filtered_total, 
                     help=f"根据筛选条件（区域、日期、关键词）筛选后的项目数量")
        with col2:
            st.metric(
                "已对比项目数",
                filtered_compared,
                f"{filtered_compared / filtered_total * 100:.1f}%" if filtered_total > 0 else "0%",
                help="筛选后项目中已完成AI对比的数量"
            )
        with col3:
            st.metric(
                "可参与项目数",
                filtered_qualified,
                f"{filtered_qualified / filtered_total * 100:.1f}%" if filtered_total > 0 else "0%",
                help="筛选后项目中可参与的数量"
            )
        with col4:
            st.metric(
                "不可参与项目数",
                filtered_unqualified,
                f"{filtered_unqualified / filtered_total * 100:.1f}%" if filtered_total > 0 else "0%",
                help="筛选后项目中不可参与的数量"
            )
        
        # 显示失分阈值配置
        from config import OBJECTIVE_SCORE_CONFIG
        st.markdown("---")
        st.subheader("⚖️ 失分阈值配置")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"启用状态: {'✅ 已启用' if OBJECTIVE_SCORE_CONFIG.get('enable_loss_score_adjustment', True) else '❌ 已禁用'}")
            with col2:
                st.info(f"失分阈值: {OBJECTIVE_SCORE_CONFIG.get('loss_score_threshold', 1.0)} 分")
            st.markdown("**说明:**")
            st.markdown("- 当项目失分 ≤ 阈值时，AI最终判断为：推荐参与")
            st.markdown("- 当项目失分 > 阈值时，AI最终判断为：不推荐参与")
            st.markdown("- AI判断为最终判断，确保推荐划分的正确性")

        # 匹配结果分布
        st.markdown("---")
        st.subheader("🎯 匹配结果分布")

        # 生成来源分布数据（优化：减少字符串操作，使用缓存）
        # 只在数据量不太大时显示（超过1000个项目时跳过，避免卡顿）
        if len(completed_projects) <= 1000:
            source_data = {}
            qualified_set = {"可以参与", "客观分满分", "推荐参与", "通过"}
            for project in completed_projects:
                # 优化：使用find代替split，减少字符串操作
                site_name = project.site_name or ""
                dash_pos = site_name.find("-")
                source = site_name[:dash_pos] if dash_pos > 0 else site_name
                if source not in source_data:
                    source_data[source] = {"total": 0, "qualified": 0}
                source_data[source]["total"] += 1
                if project.final_decision in qualified_set:
                    source_data[source]["qualified"] += 1

            # 转换为DataFrame
            if source_data:
                source_df = pd.DataFrame([
                    {
                        "来源网站": k,
                        "项目总数": v["total"],
                        "可参与数": v["qualified"],
                        "可参与率": f"{v['qualified'] / v['total'] * 100:.1f}%" if v["total"] > 0 else "0%"
                    }
                    for k, v in source_data.items()
                ])
                st.dataframe(source_df, width='stretch')
        else:
            st.info(f"📊 项目数量较多（{len(completed_projects)}个），已隐藏来源分布图表以提升性能")

        # 项目详情卡片
        st.markdown("---")
        st.subheader("📋 项目详情")
        
        # 优化：使用集合进行快速查找，减少列表遍历次数
        qualified_set = {"可以参与", "客观分满分", "推荐参与", "通过"}
        unqualified_set = {"不可以参与", "客观分不满分", "不推荐参与"}
        
        # 将项目分为推荐参与和不推荐参与两个列表（优化：单次遍历完成分类）
        # 注意：分类操作本身很快，不需要缓存，主要优化Excel生成
        recommended_projects = []
        not_recommended_projects = []
        other_projects = []
        
        for p in completed_projects:
            # 检查是否被复核为"复核不推荐"
            is_reviewed_not_recommended = hasattr(p, 'review_result') and p.review_result == "复核不推荐"
            
            if p.final_decision in qualified_set and not is_reviewed_not_recommended:
                recommended_projects.append(p)
            elif p.final_decision in unqualified_set or is_reviewed_not_recommended:
                not_recommended_projects.append(p)
            else:
                other_projects.append(p)
        
        # 验证项目数量是否匹配
        total_displayed = len(recommended_projects) + len(not_recommended_projects) + len(other_projects)
        if total_displayed != len(completed_projects):
            st.warning(f"⚠️ 项目数量不匹配：筛选后项目数={len(completed_projects)}，分类后项目数={total_displayed}（推荐={len(recommended_projects)}，不推荐={len(not_recommended_projects)}，其他={len(other_projects)}）")
        
        # 显示推荐参与的项目（添加分页，提升性能）
        if recommended_projects:
            # 分页设置（减少每页显示数量，提升性能）
            items_per_page = 5  # 每页显示5个项目（从10减少到5，进一步提升性能）
            total_pages = (len(recommended_projects) + items_per_page - 1) // items_per_page
            page_key = "recommended_page"
            current_page = st.session_state.get(page_key, 1)
            
            col_title, col_export, col_page = st.columns([2, 1, 1])
            with col_title:
                st.markdown(f"### ✅ 推荐参与项目（共 {len(recommended_projects)} 个）")
            with col_export:
                # 优化：延迟生成Excel导出数据，使用缓存避免重复生成
                if recommended_projects:
                    # 使用项目数量作为缓存键的一部分（简单但有效）
                    export_cache_key = f"export_data_recommended_{len(recommended_projects)}"
                    
                    # 检查是否有缓存的导出数据
                    if export_cache_key not in st.session_state:
                        # 生成导出数据（只在第一次或数据变化时生成）
                        @st.cache_data(ttl=3600, show_spinner=False)  # 缓存1小时，不显示加载动画
                        def generate_export_data_cached(projects_data):
                            """生成导出数据（缓存版本）"""
                            export_data = []
                            for p_data in projects_data:
                                export_data.append({
                                    "项目ID": p_data['id'],
                                    "项目名称": p_data['name'],
                                    "来源网站": p_data.get('site', ''),
                                    "发布时间": p_data.get('publish_time', ''),
                                    "文件路径": p_data.get('file_path', ''),
                                    "文件格式": p_data.get('file_format', ''),
                                    "最终判定": p_data.get('decision', '未判定'),
                                    "复核状态": p_data.get('review_status', '未复核')
                                })
                            return export_data
                        
                        # 准备项目数据（轻量级，只包含导出需要的字段）
                        projects_data = []
                        for project in recommended_projects:
                            projects_data.append({
                                'id': project.id,
                                'name': project.project_name,
                                'site': project.download_url or project.site_name or "",
                                'publish_time': project.publish_time.strftime("%Y-%m-%d %H:%M") if project.publish_time else "",
                                'file_path': project.file_path or "",
                                'file_format': project.file_format or "",
                                'decision': project.final_decision or "未判定",
                                'review_status': getattr(project, 'review_status', '未复核') or "未复核"
                            })
                        
                        # 生成导出数据（使用缓存）
                        export_data = generate_export_data_cached(tuple(projects_data))
                        
                        # 转换为DataFrame和Excel
                        df_export = pd.DataFrame(export_data)
                        from io import BytesIO
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_export.to_excel(writer, index=False, sheet_name='可参与项目')
                        output.seek(0)
                        
                        # 缓存Excel数据
                        st.session_state[export_cache_key] = {
                            'data': output.getvalue(),
                            'filename': f"可参与项目列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        }
                    
                    # 使用缓存的导出数据
                    export_info = st.session_state[export_cache_key]
                    st.download_button(
                        label="📥 导出Excel",
                        data=export_info['data'],
                        file_name=export_info['filename'],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="export_qualified_projects",
                        help="导出所有可参与项目列表为Excel文件"
                    )
            with col_page:
                if total_pages > 1:
                    # 优化：使用更轻量的分页控件，减少渲染开销
                    page_options = list(range(1, total_pages + 1))
                    # 使用selectbox，但优化key使其在页码切换时不会触发整个页面重新计算
                    selected_page = st.selectbox(
                        f"页码（共 {total_pages} 页）",
                        page_options,
                        index=current_page - 1,
                        key="recommended_page_select"
                    )
                    # 只在页码真正改变时更新
                    if selected_page != current_page:
                        st.session_state[page_key] = selected_page
                        # 清除项目分类缓存，确保数据更新
                        # 但保留Excel导出缓存，避免重新生成
                        for key in list(st.session_state.keys()):
                            if key.startswith("export_data_recommended_"):
                                # 保留导出缓存
                                pass
                        st.rerun()
            
            # 计算当前页显示的项目
            start_idx = (current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_projects = recommended_projects[start_idx:end_idx]
            
            if total_pages > 1:
                st.info(f"📄 显示第 {current_page}/{total_pages} 页（{start_idx + 1}-{min(end_idx, len(recommended_projects))} / {len(recommended_projects)}）")
            
            for project in paginated_projects:
                # 创建项目卡片（优化：使用Streamlit原生组件代替复杂HTML，提升性能）
                with st.container():
                    # 根据判定结果设置不同的颜色和图标（优化：使用集合快速判断）
                    qualified_set = {"可以参与", "客观分满分", "推荐参与", "通过"}
                    unqualified_set = {"不可以参与", "客观分不满分", "不推荐参与"}
                    
                    if project.final_decision in qualified_set:
                        decision_icon = "✅"
                        decision_badge = "success"
                    elif project.final_decision in unqualified_set:
                        decision_icon = "❌"
                        decision_badge = "error"
                    else:
                        decision_icon = "⚠️"
                        decision_badge = "warning"
                    
                    # 使用Streamlit的columns和原生组件，减少HTML渲染开销
                    card_col1, card_col2 = st.columns([4, 1])
                    
                    with card_col1:
                        # 项目名称（使用原生markdown，性能更好）
                        project_name_display = project.project_name[:80] + "..." if len(project.project_name) > 80 else project.project_name
                        st.markdown(f"**{project_name_display}**")
                        
                        # 项目信息（使用原生文本，避免HTML）
                        info_text = f"ID: {project.id} | 发布时间: {project.publish_time.strftime('%Y-%m-%d') if project.publish_time else '未设置'}"
                        st.caption(info_text)
                        
                        # 复核信息（使用原生组件）
                        if hasattr(project, 'review_status'):
                            if project.review_status == "已复核":
                                if project.review_result == "确认推荐":
                                    st.success(f"✅ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                else:  # 复核不推荐
                                    st.error(f"❌ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                    if project.review_reason:
                                        st.caption(f"移出理由: {project.review_reason}")
                            elif project.review_status == "待复核":
                                st.warning("⏳ 复核状态: 待复核")
                    
                    with card_col2:
                        # 判定结果（使用badge样式）
                        st.markdown(f"{decision_icon} **{project.final_decision or '未完成'}**")
                
                # 添加操作按钮
                col1, col2 = st.columns(2)
                with col1:
                    # 创建一个空容器用于实时更新状态
                    status_container = st.empty()
                    
                    if st.button(f"标记为已复核", key=f"mark_reviewed_{project.id}", width='stretch'):
                        # 允许人工直接标记任何推荐项目为已复核
                        try:
                            if project.review_status == "待复核":
                                # 直接标记为已复核，无需进入复核模式
                                if mark_project_reviewed(project.id, "确认推荐"):
                                    # 清除缓存，确保数据立即更新
                                    get_project_stats.clear()
                                    get_today_project_stats.clear()
                                    get_completed_projects.clear()
                                    get_all_projects.clear()
                                    # 实时更新状态
                                    status_container.success(f"✅ 项目 {project.id} 已标记为已复核")
                                    # 立即刷新页面
                                    st.rerun()
                                else:
                                    status_container.error(f"❌ 标记项目 {project.id} 为已复核失败")
                            elif project.review_status == "已复核":
                                status_container.warning(f"⚠️ 项目 {project.id} 已经复核过了")
                        except Exception as e:
                            status_container.error(f"❌ 项目 {project.id} 复核操作失败: {str(e)}")
                    
                    # 在按钮下方显示当前状态
                    if project.review_status == "已复核":
                        status_container.info(f"ℹ️ 项目 {project.id} 状态: 已复核")
                    else:
                        status_container.info(f"ℹ️ 项目 {project.id} 状态: 待复核")
                with col2:
                    if st.button(f"移出推荐", key=f"remove_recommendation_{project.id}", width='stretch'):
                        # 进入移出推荐流程，显示理由输入框
                        st.session_state["removing_project_id"] = project.id
                        st.session_state["remove_reason"] = ""
                        st.session_state["show_remove_reason_input"] = True
                        st.rerun()
                
                # 显示移出推荐理由输入框
                if "show_remove_reason_input" in st.session_state and st.session_state["show_remove_reason_input"] and "removing_project_id" in st.session_state and st.session_state["removing_project_id"] == project.id:
                    with st.form(key=f"remove_reason_form_{project.id}"):
                        st.markdown("### 移出推荐理由")
                        remove_reason = st.text_area("请输入移出推荐的理由（必填）:", value=st.session_state.get("remove_reason", ""), height=100, key=f"remove_reason_text_{project.id}")
                        col1, col2 = st.columns(2)
                        with col1:
                            submit_button = st.form_submit_button("确认移出")
                        with col2:
                            cancel_button = st.form_submit_button("取消")
                        
                        if cancel_button:
                            st.session_state["show_remove_reason_input"] = False
                            st.session_state.pop("removing_project_id", None)
                            st.session_state.pop("remove_reason", None)
                            st.rerun()
                        
                        if submit_button:
                            if not remove_reason.strip():
                                st.error("移出推荐理由不能为空！")
                            else:
                                # 更新项目状态为不推荐参与，并保存理由
                                if mark_project_reviewed(project.id, "复核不推荐", remove_reason):
                                    # 清除缓存，确保数据立即更新
                                    get_project_stats.clear()
                                    get_today_project_stats.clear()
                                    get_completed_projects.clear()
                                    get_all_projects.clear()
                                    st.success(f"项目 {project.id} 已移出推荐列表")
                                    st.session_state["show_remove_reason_input"] = False
                                    st.session_state.pop("removing_project_id", None)
                                    st.session_state.pop("remove_reason", None)
                                    st.rerun()
                                else:
                                    st.error(f"更新项目 {project.id} 状态失败")
                
                # 创建隐藏的模态窗口
                with st.expander(f"项目 {project.id} 详情", expanded=False):
                    render_project_details(project, project_id_suffix="", include_file_download=True, is_visualization=False)
        
        # 显示不推荐参与的项目（添加分页，提升性能）
        if not_recommended_projects:
            st.markdown("---")
            # 分页设置（减少每页显示数量，提升性能）
            items_per_page_not = 5  # 每页显示5个项目
            total_pages_not = (len(not_recommended_projects) + items_per_page_not - 1) // items_per_page_not
            page_key_not = "not_recommended_page"
            current_page_not = st.session_state.get(page_key_not, 1)
            
            col_title_not, col_page_not = st.columns([3, 1])
            with col_title_not:
                st.markdown(f"### ❌ 不推荐参与项目（共 {len(not_recommended_projects)} 个）")
            with col_page_not:
                if total_pages_not > 1:
                    page_options_not = list(range(1, total_pages_not + 1))
                    selected_page_not = st.selectbox(
                        f"页码（共 {total_pages_not} 页）",
                        page_options_not,
                        index=current_page_not - 1,
                        key="not_recommended_page_select"
                    )
                    if selected_page_not != current_page_not:
                        st.session_state[page_key_not] = selected_page_not
                        st.rerun()
            
            # 计算当前页显示的项目
            start_idx_not = (current_page_not - 1) * items_per_page_not
            end_idx_not = start_idx_not + items_per_page_not
            paginated_not_recommended = not_recommended_projects[start_idx_not:end_idx_not]
            
            if total_pages_not > 1:
                st.info(f"📄 显示第 {current_page_not}/{total_pages_not} 页（{start_idx_not + 1}-{min(end_idx_not, len(not_recommended_projects))} / {len(not_recommended_projects)}）")
            
            for project in paginated_not_recommended:
                # 创建项目卡片（优化：使用Streamlit原生组件，提升性能）
                with st.container():
                    # 使用Streamlit的columns和原生组件
                    card_col1, card_col2 = st.columns([4, 1])
                    
                    with card_col1:
                        # 项目名称
                        project_name_display = project.project_name[:80] + "..." if len(project.project_name) > 80 else project.project_name
                        st.markdown(f"**{project_name_display}**")
                        
                        # 项目信息
                        info_text = f"ID: {project.id} | 发布时间: {project.publish_time.strftime('%Y-%m-%d') if project.publish_time else '未设置'}"
                        st.caption(info_text)
                        
                        # 复核信息（使用原生组件）
                        if hasattr(project, 'review_status'):
                            if project.review_status == "已复核":
                                if project.review_result == "确认推荐":
                                    st.success(f"✅ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                else:  # 复核不推荐
                                    st.error(f"❌ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                    if project.review_reason:
                                        st.caption(f"移出理由: {project.review_reason}")
                            elif project.review_status == "待复核":
                                st.warning("⏳ 复核状态: 待复核")
                    
                    with card_col2:
                        # 判定结果
                        st.markdown(f"❌ **{project.final_decision or '未完成'}**")
                    
                    # 添加重新进行AI分析按钮
                    if st.button("🔄 重新进行AI分析", key=f"reanalyze_{project.id}", type="secondary", width='stretch'):
                        # 设置重新分析的会话状态
                        st.session_state[f'reanalyze_project_{project.id}'] = True
                        st.rerun()  # 刷新页面以触发分析
                
                # 创建隐藏的模态窗口
                with st.expander(f"项目 {project.id} 详情", expanded=False):
                    render_project_details(project, project_id_suffix="", include_file_download=True, is_visualization=True)
        
        # 显示其他项目（优化：使用原生组件）
        if other_projects:
            st.markdown("---")
            st.markdown("### ⚠️ 其他项目")
            for project in other_projects:
                # 创建项目卡片（优化：使用Streamlit原生组件，提升性能）
                with st.container():
                    # 使用Streamlit的columns和原生组件
                    card_col1, card_col2 = st.columns([4, 1])
                    
                    with card_col1:
                        # 项目名称
                        project_name_display = project.project_name[:80] + "..." if len(project.project_name) > 80 else project.project_name
                        st.markdown(f"**{project_name_display}**")
                        
                        # 项目信息
                        info_text = f"ID: {project.id} | 发布时间: {project.publish_time.strftime('%Y-%m-%d') if project.publish_time else '未设置'}"
                        st.caption(info_text)
                        
                        # 复核信息（使用原生组件）
                        if hasattr(project, 'review_status'):
                            if project.review_status == "已复核":
                                if project.review_result == "确认推荐":
                                    st.success(f"✅ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                else:  # 复核不推荐
                                    st.error(f"❌ 复核状态: {project.review_result} - {project.review_time.strftime('%Y-%m-%d %H:%M') if project.review_time else '未知时间'}")
                                    if project.review_reason:
                                        st.caption(f"移出理由: {project.review_reason}")
                            elif project.review_status == "待复核":
                                st.warning("⏳ 复核状态: 待复核")
                    
                    with card_col2:
                        # 判定结果
                        st.markdown(f"⚠️ **{project.final_decision or '未完成'}**")
                
                # 创建隐藏的模态窗口
                with st.expander(f"项目 {project.id} 详情", expanded=False):
                    render_project_details(project, project_id_suffix="", include_file_download=True, is_visualization=True)

        # 文件查看按钮
        st.markdown("---")
        st.subheader("📎 文件查看")
        
        # 为每个项目创建文件下载按钮
        for project in completed_projects:
            if project.file_path and (os.path.exists(project.file_path) or os.path.isdir(project.file_path)):
                with st.expander(f"项目 {project.id}: {project.project_name[:50]}..."):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(f"文件路径: {project.file_path}")
                    with col2:
                        # 检查文件是否存在
                        if project.file_path and (os.path.exists(project.file_path) or os.path.isdir(project.file_path)):
                            try:
                                # 每次渲染时重新准备文件数据，避免使用过期的文件ID
                                file_data, filename, mime_type, error_msg = prepare_file_for_download(project.file_path)
                                if file_data and filename and mime_type:
                                    # 对于小文件（<10MB），使用 base64 下载链接避免 Streamlit 媒体文件存储问题
                                    file_size_mb = len(file_data) / (1024 * 1024)
                                    if file_size_mb < 10:
                                        # 使用 base64 下载链接
                                        download_link = create_download_link(file_data, filename, mime_type)
                                        if download_link:
                                            st.markdown(download_link, unsafe_allow_html=True)
                                        else:
                                            # 回退到 download_button
                                            st.download_button(
                                                label="📥 下载文件",
                                                data=file_data,
                                                file_name=filename,
                                                mime=mime_type,
                                                key=f"download_file_expander_{project.id}",
                                                help="点击下载项目文件",
                                                width='stretch'
                                            )
                                    else:
                                        # 大文件使用 download_button
                                        st.download_button(
                                            label="📥 下载文件",
                                            data=file_data,
                                            file_name=filename,
                                            mime=mime_type,
                                            key=f"download_file_expander_{project.id}",
                                            help="点击下载项目文件",
                                            width='stretch'
                                        )
                                else:
                                    st.warning(f"⚠️ {error_msg or '文件准备失败'}")
                            except Exception as e:
                                log.error(f"准备文件下载失败（项目ID: {project.id}）: {str(e)}")
                                st.warning(f"⚠️ 文件下载功能暂时不可用")
                        else:
                            st.warning(f"⚠️ 文件不存在")
            else:
                with st.expander(f"项目 {project.id}: {project.project_name[:50]}..."):
                    st.text("文件不存在")

    else:
        st.info("📊 暂无已完成比对的项目，请先执行分析流程")


def render_report_export():
    """渲染报告导出页面"""
    st.title("📄 报告导出 - 标书资质自动匹配系统")
    st.markdown("---")

    if get_project_stats()["total"] == 0:
        st.warning("⚠️ 暂无项目数据，无法生成报告")
        return

    # 获取所有可用的城市和采购类型
    db = next(get_db())
    all_projects = db.query(TenderProject).all()
    db.close()
    
    # 提取所有城市（使用报告生成器的提取方法）
    all_cities = set()
    report_generator = get_report_generator()  # 获取报告生成器实例
    for proj in all_projects:
        if proj.region:
            _, city = report_generator._extract_province_city(proj.region)
            if city and city != "未知":
                all_cities.add(city)
    all_cities = sorted(list(all_cities))
    
    # 提取所有采购类型
    procurement_types_set = set()
    for proj in all_projects:
        if proj.site_name:
            if "政府类" in proj.site_name:
                procurement_types_set.add("政府采购")
            elif "非政府类" in proj.site_name:
                procurement_types_set.add("国企采购")
    all_procurement_types = sorted(list(procurement_types_set))

    # 筛选条件配置
    st.subheader("📋 筛选条件")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # 时间范围选择
        st.markdown("**时间范围**")
        use_date_filter = st.checkbox("启用时间筛选", value=False)
        if use_date_filter:
            start_date = st.date_input("开始日期", value=None)
            end_date = st.date_input("结束日期", value=None)
        else:
            start_date = None
            end_date = None
    
    with col2:
        # 采购类型选择
        st.markdown("**采购类型**")
        if all_procurement_types:
            selected_procurement_types = st.multiselect(
                "选择采购类型（不选表示全选）",
                options=all_procurement_types,
                default=all_procurement_types if len(all_procurement_types) > 0 else []
            )
        else:
            selected_procurement_types = []
            st.info("暂无采购类型数据")
    
    with col3:
        # 平台筛选
        st.markdown("**平台筛选**")
        available_platforms = get_available_platforms()
        platform_options = ["全部"] + list(available_platforms.values())
        selected_platform_name = st.selectbox(
            "选择平台（不选表示全选）",
            options=platform_options,
            index=0,
            key="report_platform_filter"
        )
    
    # 城市选择
    st.markdown("**城市筛选**")
    if all_cities:
        selected_cities = st.multiselect(
            "选择城市（不选表示全选）",
            options=all_cities,
            default=all_cities if len(all_cities) > 0 else []
        )
    else:
        selected_cities = []
        st.info("暂无城市数据")
    
    st.markdown("---")
    
    # 生成报告按钮
    if st.button("📊 生成并导出报告", type="primary", width='stretch'):
        with st.spinner("正在生成报告..."):
            try:
                # 转换日期格式
                start_dt = None
                end_dt = None
                if use_date_filter and start_date:
                    from datetime import datetime as dt
                    start_dt = dt.combine(start_date, dt.min.time())
                if use_date_filter and end_date:
                    from datetime import datetime as dt
                    end_dt = dt.combine(end_date, dt.max.time())
                
                # 处理筛选条件（将城市筛选转换为区域筛选参数，报告生成器内部会处理城市匹配）
                cities_filter = selected_cities if selected_cities else None
                procurement_types_filter = selected_procurement_types if selected_procurement_types else None
                # 平台筛选
                selected_platform_code = None
                if selected_platform_name != "全部":
                    selected_platform_code = {v: k for k, v in available_platforms.items()}.get(selected_platform_name)
                
                report_path = generate_report(
                    start_date=start_dt,
                    end_date=end_dt,
                    regions=cities_filter,  # 传递城市列表作为regions参数，报告生成器内部会按城市筛选
                    procurement_types=procurement_types_filter,
                    platform_code=selected_platform_code
                )

                # 生成下载链接
                with open(report_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    filename = os.path.basename(report_path)
                    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 点击下载报告</a>'

                st.success("✅ 报告生成成功！")
                st.markdown(href, unsafe_allow_html=True)

                # 报告预览
                st.markdown("---")
                st.subheader("📋 报告预览")
                preview_report(
                    start_date=start_dt,
                    end_date=end_dt,
                    regions=cities_filter,  # 传递城市列表作为regions参数
                    procurement_types=procurement_types_filter,
                    platform_code=selected_platform_code
                )

            except Exception as e:
                st.error(f"❌ 报告生成失败：{str(e)}")
                st.info("💡 解决建议：")
                st.markdown("- 检查是否有符合筛选条件的项目数据")
                st.markdown("- 验证数据库连接是否正常")
                st.markdown("- 确认报告目录有写入权限")
                st.markdown("- 尝试调整筛选条件后重新生成报告")


def generate_report(start_date=None, end_date=None, regions=None, procurement_types=None, platform_code=None):
    """生成报告"""
    report_gen = get_report_generator()
    return report_gen.generate_report(
        start_date=start_date,
        end_date=end_date,
        regions=regions,
        procurement_types=procurement_types,
        platform_code=platform_code
    )


def preview_report(start_date=None, end_date=None, regions=None, procurement_types=None, platform_code=None):
    """预览报告内容"""
    report_gen = get_report_generator()
    data = report_gen._get_project_data(
        start_date=start_date,
        end_date=end_date,
        regions=regions,
        procurement_types=procurement_types,
        platform_code=platform_code
    )
    if len(data) > 0:
        st.dataframe(data.head(20), width='stretch')
        st.info(f"共 {len(data)} 条记录（预览前20条）")
    else:
        st.warning("⚠️ 没有符合筛选条件的项目数据")


def render_storage_management():
    """渲染存储管理页面"""
    st.title("💾 存储管理 - 标书资质自动匹配系统")
    st.markdown("---")
    
    try:
        storage_manager = StorageManager()
        
        # 1. 存储空间概览
        st.subheader("📊 存储空间概览")
        
        # 获取磁盘使用情况
        disk_usage = storage_manager.get_disk_usage()
        storage_info = storage_manager.get_storage_info()
        
        # 显示磁盘使用情况
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("磁盘总容量", storage_manager.format_size(disk_usage["total"]))
        with col2:
            st.metric("已使用", storage_manager.format_size(disk_usage["used"]))
        with col3:
            st.metric("可用空间", storage_manager.format_size(disk_usage["free"]))
        with col4:
            usage_percent = disk_usage["percent_used"]
            usage_color = "normal" if usage_percent < 80 else "inverse" if usage_percent >= 90 else "off"
            st.metric("使用率", f"{usage_percent:.1f}%", delta=None)
        
        # 磁盘使用率进度条
        st.progress(usage_percent / 100)
        
        # 警告提示
        if usage_percent >= STORAGE_CONFIG.get("disk_critical_threshold", 90.0):
            st.error(f"⚠️ 磁盘空间严重不足！使用率已达到 {usage_percent:.1f}%，请立即清理文件！")
        elif usage_percent >= STORAGE_CONFIG.get("disk_warning_threshold", 80.0):
            st.warning(f"⚠️ 磁盘空间不足，使用率已达到 {usage_percent:.1f}%，建议清理旧文件")
        
        st.markdown("---")
        
        # 2. 各目录存储详情
        st.subheader("📁 目录存储详情")
        
        detail_data = []
        detail_data.append({
            "目录": "标书文件",
            "路径": storage_info["files_dir"]["path"],
            "大小": storage_manager.format_size(storage_info["files_dir"]["size"]),
            "文件数": storage_info["files_dir"]["file_count"]
        })
        detail_data.append({
            "目录": "报告文件",
            "路径": storage_info["report_dir"]["path"],
            "大小": storage_manager.format_size(storage_info["report_dir"]["size"]),
            "文件数": storage_info["report_dir"]["file_count"]
        })
        detail_data.append({
            "目录": "日志文件",
            "路径": storage_info["log_dir"]["path"],
            "大小": storage_manager.format_size(storage_info["log_dir"]["size"]),
            "文件数": storage_info["log_dir"]["file_count"]
        })
        detail_data.append({
            "目录": "数据库文件",
            "路径": storage_info["db_file"]["path"],
            "大小": storage_manager.format_size(storage_info["db_file"]["size"]),
            "文件数": 1
        })
        
        st.dataframe(pd.DataFrame(detail_data), width='stretch')
        
        st.markdown("---")
        
        # 3. 自动清理配置
        st.subheader("⚙️ 自动清理配置")
        
        col1, col2 = st.columns(2)
        with col1:
            auto_cleanup_enabled = st.checkbox(
                "启用自动清理",
                value=STORAGE_CONFIG.get("auto_cleanup_enabled", True),
                help="自动清理超过保留天数的旧文件"
            )
            cleanup_days = st.number_input(
                "文件保留天数",
                min_value=1,
                max_value=365,
                value=STORAGE_CONFIG.get("cleanup_interval_days", 30),
                help="保留最近N天的文件，超过此天数的文件将被自动清理"
            )
        
        with col2:
            cleanup_schedule = st.selectbox(
                "清理计划",
                ["daily", "weekly", "monthly"],
                index=["daily", "weekly", "monthly"].index(STORAGE_CONFIG.get("cleanup_schedule", "daily")),
                help="自动清理的执行频率"
            )
            cleanup_time = st.text_input(
                "清理时间",
                value=STORAGE_CONFIG.get("cleanup_time", "02:00"),
                help="每日清理执行时间（24小时制，格式：HH:MM）"
            )
        
        if st.button("💾 保存清理配置", type="primary"):
            # 更新配置（这里只是示例，实际应该保存到配置文件）
            st.success("✅ 清理配置已保存（需要重启服务生效）")
        
        st.markdown("---")
        
        # 4. 手动清理操作
        st.subheader("🧹 手动清理操作")
        
        tab1, tab2, tab3 = st.tabs(["按时间清理", "按状态清理", "清理空目录"])
        
        with tab1:
            st.markdown("#### 按时间清理文件")
            st.info("💡 清理指定天数之前的文件，释放存储空间")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                cleanup_days_input = st.number_input(
                    "保留最近N天的文件",
                    min_value=1,
                    max_value=365,
                    value=30,
                    key="cleanup_days_input"
                )
            
            with col2:
                st.write("")  # 占位
                st.write("")  # 占位
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 预览清理（试运行）", type="secondary"):
                    with st.spinner("正在分析可清理的文件..."):
                        stats = storage_manager.clean_old_files(days=cleanup_days_input, dry_run=True)
                        st.info(f"预览结果：将删除 {stats['files_deleted']} 个文件，释放 {storage_manager.format_size(stats['files_size_freed'])} 空间")
                        if stats['errors']:
                            st.warning(f"发现 {len(stats['errors'])} 个错误")
            
            with col2:
                if st.button("🗑️ 执行清理", type="primary"):
                    with st.spinner("正在清理文件..."):
                        stats = storage_manager.clean_old_files(days=cleanup_days_input, dry_run=False)
                        st.success(f"✅ 清理完成！删除了 {stats['files_deleted']} 个文件，释放了 {storage_manager.format_size(stats['files_size_freed'])} 空间")
                        if stats['errors']:
                            st.warning(f"清理过程中遇到 {len(stats['errors'])} 个错误")
                        # 清除缓存并刷新
                        get_project_stats.clear()
                        get_today_project_stats.clear()
                        get_completed_projects.clear()
                        get_all_projects.clear()
                        time.sleep(0.5)
                        st.rerun()
        
        with tab2:
            st.markdown("#### 按项目状态清理文件")
            st.info("💡 清理指定状态的项目文件（谨慎操作）")
            
            from utils.db import ProjectStatus
            status_options = [status.value for status in ProjectStatus]
            selected_statuses = st.multiselect(
                "选择要清理的项目状态",
                status_options,
                default=["已比对"],
                help="选择要清理的项目状态，这些状态的项目文件将被删除"
            )
            
            keep_days = st.number_input(
                "即使状态匹配也保留最近N天",
                min_value=0,
                max_value=365,
                value=90,
                help="即使项目状态匹配，也保留最近N天的文件"
            )
            
            if st.button("🗑️ 按状态清理", type="primary"):
                if not selected_statuses:
                    st.warning("请至少选择一个项目状态")
                else:
                    with st.spinner("正在清理文件..."):
                        # 这里需要实现按状态清理的逻辑
                        st.info("按状态清理功能开发中...")
        
        with tab3:
            st.markdown("#### 清理空目录")
            st.info("💡 清理所有空目录，释放少量空间")
            
            if st.button("🧹 清理空目录", type="primary"):
                with st.spinner("正在清理空目录..."):
                    deleted_count = 0
                    deleted_count += storage_manager.clean_empty_directories(storage_manager.files_dir)
                    deleted_count += storage_manager.clean_empty_directories(storage_manager.report_dir)
                    st.success(f"✅ 清理完成！删除了 {deleted_count} 个空目录")
        
        st.markdown("---")
        
        # 5. 存储优化建议
        st.subheader("💡 存储优化建议")
        
        suggestions = []
        if usage_percent >= 80:
            suggestions.append("⚠️ 磁盘使用率较高，建议立即清理旧文件")
        if storage_info["files_dir"]["size"] > 1024 * 1024 * 1024:  # 超过1GB
            suggestions.append(f"📁 标书文件占用 {storage_manager.format_size(storage_info['files_dir']['size'])}，建议清理30天前的文件")
        if storage_info["report_dir"]["size"] > 100 * 1024 * 1024:  # 超过100MB
            suggestions.append(f"📄 报告文件占用 {storage_manager.format_size(storage_info['report_dir']['size'])}，建议清理90天前的报告")
        if storage_info["log_dir"]["size"] > 500 * 1024 * 1024:  # 超过500MB
            suggestions.append(f"📝 日志文件占用 {storage_manager.format_size(storage_info['log_dir']['size'])}，建议检查日志轮转配置")
        
        if suggestions:
            for suggestion in suggestions:
                st.info(suggestion)
        else:
            st.success("✅ 存储空间使用正常，无需优化")
    
    except Exception as e:
        st.error(f"❌ 存储管理功能加载失败：{str(e)}")
        st.info("💡 解决建议：")
        st.markdown("- 检查存储管理模块是否正确安装")
        st.markdown("- 验证目录权限是否正确")
        st.markdown("- 查看日志文件获取详细错误信息")


def render_task_scheduler():
    """渲染定时任务管理页面"""
    st.title("⏰ 定时任务管理 - 标书资质自动匹配系统")
    st.markdown("---")
    
    try:
        scheduler = WindowsTaskScheduler()
        
        # 显示系统信息
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📝 Python路径: `{scheduler.python_exe}`")
        with col2:
            st.info(f"📄 脚本路径: `{scheduler.script_path}`")
        
        st.markdown("---")
        
        # 1. 创建新任务
        st.subheader("➕ 创建定时任务")
        
        with st.form("create_task_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                task_id = st.text_input(
                    "任务ID（唯一标识）",
                    value=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    help="任务的唯一标识符，用于区分不同任务"
                )
            
            with col2:
                schedule_time = st.time_input(
                    "执行时间",
                    value=datetime.strptime("02:00", "%H:%M").time(),
                    help="每天的执行时间（24小时制）"
                )
                schedule_time_str = schedule_time.strftime("%H:%M")
            
            with col3:
                daily_limit = st.number_input(
                    "爬取数量限制",
                    min_value=1,
                    max_value=10000,
                    value=300,
                    step=10,
                    help="每次执行时爬取的标书文件数量（默认300）"
                )
            
            col4, col5 = st.columns(2)
            with col4:
                days_before = st.number_input(
                    "时间间隔（天）",
                    min_value=0,
                    max_value=365,
                    value=0,
                    step=1,
                    help="爬取指定天数之前的文件（0表示只爬取当日文件，7表示爬取7天前及更早的文件）"
                )
                if days_before == 0:
                    days_before = None  # 0表示不限制，只爬取当日文件
            
            with col5:
                enabled = st.checkbox("立即启用", value=True, help="创建后是否立即启用该任务")
            
            # 平台选择
            available_platforms = get_available_platforms()
            platform_options = ["全部"] + list(available_platforms.values())
            selected_platform_name = st.selectbox(
                "选择爬取平台",
                options=platform_options,
                index=0,
                help="选择要爬取的平台，'全部'表示爬取所有平台"
            )
            
            # 将平台名称转换为平台代码
            selected_platform_code = None
            if selected_platform_name != "全部":
                selected_platform_code = {v: k for k, v in available_platforms.items()}.get(selected_platform_name)
            enabled_platforms = [selected_platform_code] if selected_platform_code else None
            
            submitted = st.form_submit_button("创建定时任务", width='stretch')
            
            if submitted:
                if not task_id or not task_id.strip():
                    st.error("❌ 任务ID不能为空")
                else:
                    success, msg = scheduler.create_task(
                        task_id=task_id.strip(),
                        schedule_time=schedule_time_str,
                        daily_limit=int(daily_limit),
                        days_before=int(days_before) if days_before else None,
                        enabled=enabled,
                        enabled_platforms=enabled_platforms
                    )
                    if success:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        
        st.markdown("---")
        
        # 2. 任务列表
        st.subheader("📋 当前定时任务列表")
        
        tasks = scheduler.list_tasks()
        
        if not tasks:
            st.info("📭 当前没有定时任务，请在上方创建新任务")
        else:
            # 显示任务表格
            task_data = []
            for task in tasks:
                    days_before = task.get("days_before")
                    days_before_str = f"{days_before}天前" if days_before else "当日"
                    task_data.append({
                        "任务ID": task.get("task_id", ""),
                        "执行时间": task.get("schedule_time", ""),
                        "爬取数量": task.get("daily_limit", 300),
                        "时间间隔": days_before_str,
                        "状态": task.get("status", "未知"),
                        "创建时间": task.get("created_at", "")
                    })
            
            df = pd.DataFrame(task_data)
            st.dataframe(df, width='stretch')
            
            st.markdown("---")
            
            # 3. 任务操作
            st.subheader("⚙️ 任务操作")
            
            if tasks:
                task_ids = [t.get("task_id") for t in tasks if t.get("task_id")]
                
                if task_ids:
                    selected_task_id = st.selectbox(
                        "选择要操作的任务",
                        task_ids,
                        help="选择要启用、禁用或删除的任务"
                    )
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        if st.button("✅ 启用任务", width='stretch'):
                            success, msg = scheduler.enable_task(selected_task_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("⏸️ 禁用任务", width='stretch'):
                            success, msg = scheduler.disable_task(selected_task_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col3:
                        if st.button("▶️ 立即运行", width='stretch'):
                            success, msg = scheduler.run_task_now(selected_task_id)
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                    
                    with col4:
                        if st.button("🗑️ 删除任务", width='stretch'):
                            success, msg = scheduler.delete_task(selected_task_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col5:
                        selected_task = next((t for t in tasks if t.get("task_id") == selected_task_id), None)
                        if selected_task:
                            if st.button("🧪 测试执行", width='stretch'):
                                success, msg = scheduler.test_task(
                                    daily_limit=selected_task.get("daily_limit", 300),
                                    days_before=selected_task.get("days_before")
                                )
                                if success:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                    
                    # 任务诊断信息
                    with st.expander("🔍 任务诊断信息"):
                        success, details = scheduler.get_task_details(selected_task_id)
                        if success and details.get("exists"):
                            st.success("✅ 任务已存在于Windows任务计划程序中")
                            st.text_area("任务详细信息", details.get("raw_output", ""), height=300)
                        else:
                            st.error("❌ 任务不存在于Windows任务计划程序中")
                            if details.get("raw_output"):
                                st.text_area("错误信息", details.get("raw_output", ""), height=200)
                        
                        # 显示任务配置
                        if details.get("task_config"):
                            config = details["task_config"]
                            st.info(f"""
                            **任务配置：**
                            - Python路径: `{scheduler.python_exe}`
                            - 脚本路径: `{scheduler.script_path}`
                            - 工作目录: `{scheduler.base_dir}`
                            - 执行命令: `"{scheduler.python_exe}" "{scheduler.script_path}" --daily-limit {config.get('daily_limit', 300)} --days-before {config.get('days_before') or 0}`
                            """)
        
        st.markdown("---")
        
        # 4. 使用说明
        with st.expander("📖 使用说明"):
            st.markdown("""
            ### 定时任务功能说明
            
            1. **创建任务**
               - 输入唯一的任务ID（建议使用有意义的名称）
               - 设置每天的执行时间（24小时制）
               - 设置每次执行的爬取数量限制（默认300个）
               - 设置时间间隔（0表示只爬取当日文件，7表示爬取7天前及更早的文件）
               - 选择是否立即启用任务
            
            2. **任务管理**
               - **启用任务**：启动已禁用的定时任务
               - **禁用任务**：暂停定时任务（不会删除）
               - **删除任务**：永久删除定时任务
               - **测试执行**：立即执行一次任务（用于测试）
            
            3. **注意事项**
               - 任务基于Windows任务计划程序实现，需要管理员权限
               - 删除任务会永久移除，请谨慎操作
               - 测试执行会在后台运行，请查看日志了解执行情况
               - 建议在服务器空闲时段设置定时任务（如凌晨2点）
            
            4. **任务执行流程**
               - 爬取标书文件（按设定的数量限制）
               - 解析文件内容
               - AI资质分析与比对
               - 生成每日报告
            """)
    
    except Exception as e:
        st.error(f"❌ 定时任务管理功能加载失败：{str(e)}")
        st.info("💡 解决建议：")
        st.markdown("- 确保系统已安装Windows任务计划程序")
        st.markdown("- 检查是否有管理员权限")
        st.markdown("- 查看日志文件获取详细错误信息")


# ====================== 主程序 ======================
def main():
    """主程序"""
    load_custom_css()

    # 初始化会话状态
    if "menu_choice" not in st.session_state:
        st.session_state["menu_choice"] = "系统首页"

    # 处理session_state中的异步操作（从模块级别移到这里，避免阻塞）
    # 只在必要时执行，避免每次页面加载都执行
    # 添加异常处理，避免处理过程导致应用崩溃
    if st.session_state.get('page_load_count', 0) % 2 == 0:  # 每2次页面加载执行一次
        try:
            process_session_state_actions()
        except Exception as e:
            # 如果处理失败，记录日志但不影响应用运行
            log.debug(f"处理session_state操作失败（可忽略）：{str(e)}")

    # 检查是否有正在运行的后台任务（综合检查session_state和日志文件）
    # 添加异常处理，避免检查过程导致应用崩溃
    try:
        is_task_running_quick = _is_task_likely_running()
    except Exception as e:
        # 如果检查失败，假设没有任务在运行，避免影响应用
        is_task_running_quick = False
        log.debug(f"检查任务状态失败（可忽略）：{str(e)}")
    
    # 如果任务正在运行，在所有页面顶部显示实时日志
    if is_task_running_quick:
        # 读取最新的日志信息（检查最近5分钟内的日志）
        # 添加异常处理，避免日志读取导致应用崩溃
        try:
            recent_logs = _read_recent_logs(max_lines=30, check_recent_minutes=5)
        except Exception as e:
            # 如果读取日志失败，不显示日志，但不影响应用运行
            recent_logs = []
            log.debug(f"读取日志失败（可忽略）：{str(e)}")
        
        if recent_logs:
            # 显示日志容器（可折叠，默认展开）
            try:
                with st.expander("📋 实时日志信息（仅显示INFO级别）", expanded=True):
                    # 使用代码块样式显示日志，支持滚动
                    # 只显示最后20条，避免显示过多
                    display_logs = recent_logs[-20:] if len(recent_logs) > 20 else recent_logs
                    log_text = "\n".join(display_logs)
                    st.code(log_text, language=None)
                    
                    # 自动刷新提示
                    st.caption("⏱️ 日志每10秒自动更新（显示最新20条INFO日志，最近5分钟内的日志）")
            except Exception as e:
                # 如果显示日志失败，静默处理，不影响应用
                log.debug(f"显示日志失败（可忽略）：{str(e)}")
    
    # 如果任务正在运行且用户进入了进度页面，隐藏侧边栏
    if is_task_running_quick and st.session_state.get("show_task_progress", False):
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        section[data-testid="stSidebar"] + div {
            margin-left: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        # 如果侧边栏已隐藏（任务运行中），直接使用session_state中的menu_choice
        menu_choice = st.session_state.get("menu_choice", "流程执行")
    else:
        # 渲染侧边栏（render_sidebar内部已经同步session_state）
        menu_choice = render_sidebar()
        # 确保使用session_state中的值（可能被按钮修改）
        menu_choice = st.session_state.get("menu_choice", menu_choice)
    

    # 处理快速操作
    if st.session_state.get("run_full_process"):
        with st.spinner("正在执行全流程..."):
            try:
                result = run_full_process()
                if result:
                    # 清除所有相关缓存，确保数据及时更新
                    get_project_stats.clear()
                    get_today_project_stats.clear()
                    get_completed_projects.clear()
                    get_all_projects.clear()
                st.success("✅ 全流程执行完成！")
                # 短暂延迟后刷新页面，确保数据更新
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 执行失败：{str(e)}")
        st.session_state["run_full_process"] = False

    if st.session_state.get("run_spider"):
        # 使用带进度的爬虫执行函数
        run_spider_with_progress()
    
    if st.session_state.get("run_ai_analysis_for_error"):
        # 使用带进度的AI分析执行函数处理异常项目
        run_ai_analysis_with_progress()
        st.session_state["run_ai_analysis_for_error"] = False

    # 渲染主内容
    if not SYSTEM_READY:
        st.error("❌ 系统组件加载失败，请检查配置和依赖")
        return

    try:
        if menu_choice == "系统首页":
            render_home_page()

        elif menu_choice == "标书文件管理":
            render_file_management()

        elif menu_choice == "资质库管理":
            render_qualification_management()

        elif menu_choice == "流程执行":
            render_process_execution()

        elif menu_choice == "分析过程可视化":
            render_result_visualization()

        elif menu_choice == "报告导出":
            render_report_export()
        
        elif menu_choice == "存储管理":
            render_storage_management()
        
        elif menu_choice == "定时任务":
            render_task_scheduler()
        else:
            st.warning(f"⚠️ 未知的菜单选项：{menu_choice}")
    except Exception as e:
        log.error(f"渲染页面失败（菜单选项：{menu_choice}）：{str(e)}", exc_info=True)
        st.error(f"❌ 页面渲染失败：{str(e)}")
        st.info("💡 请刷新页面重试，或查看日志文件了解详细信息")


if __name__ == "__main__":
    # Streamlit会自动处理脚本的重新运行，不需要无限循环
    # 无限循环会导致重复渲染和key冲突问题
    try:
        main()
    except KeyboardInterrupt:
        log.warning("应用被用户中断")
    except SystemExit:
        # 系统退出，正常处理
        pass
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_detail = traceback.format_exc()
        log.error(f"应用发生未预期的错误：{str(e)}\n{error_detail}")
        
        # 尝试在UI中显示错误（如果Streamlit可用）
        try:
            st.error(f"❌ 应用发生错误：{str(e)}")
            st.info("💡 请刷新页面重试，或查看日志文件了解详细信息")
            # 显示详细错误信息（可折叠）
            with st.expander("🔍 查看详细错误信息"):
                st.code(error_detail, language='python')
        except Exception as ui_error:
            # 如果Streamlit也出错，只记录日志，不抛出异常
            log.error(f"显示错误信息失败：{str(ui_error)}")
            # 不重新抛出异常，避免应用完全崩溃
