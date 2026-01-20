"""宁波市招标平台爬虫实现"""

import requests
import os
import time
from datetime import datetime
from typing import Optional, Tuple
# 兼容相对导入和绝对导入
try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG, get_access_token
    from .request_handler import get_doc_list, get_file_url, download_file
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.ningbo.config import PLATFORM_CONFIG, get_access_token
    from spider.platforms.ningbo.request_handler import get_doc_list, get_file_url, download_file

# 这些导入在所有情况下都需要，放在try-except外
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import SPIDER_CONFIG, FILES_DIR


@SpiderManager.register
class NingBoTenderSpider(BaseSpider):
    """宁波市阳光采购服务平台爬虫"""
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """初始化爬虫"""
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        
        # 平台URL配置
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_list_url = PLATFORM_CONFIG["api_list_url"]
        
        # 请求配置（复制headers，避免修改原配置）
        self.headers_list = PLATFORM_CONFIG["headers_list"].copy()
        self.headers_download = PLATFORM_CONFIG["headers_download"].copy()
        self.cookies = PLATFORM_CONFIG["cookies"]
        
        # 动态获取access_token并更新headers
        access_token = get_access_token()
        if access_token:
            self.headers_list['access_token'] = access_token
            log.info(f"成功获取并设置access_token（长度: {len(access_token)}）")
        else:
            log.warning("获取access_token失败，将使用默认值或空值")
        
        # 爬取配置
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 10)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)
    
    def run(self):
        """执行爬虫主逻辑"""
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        
        # 创建会话
        session = requests.Session()
        session.headers.update(self.headers_list)
        if self.cookies:
            session.cookies.update(self.cookies)
        
        # 初始化
        projects = []
        total_count = 0
        today = datetime.now().date()
        
        # 批量查询已存在的项目ID
        from utils.db import TenderProject
        existing_project_ids = set(
            row[0] for row in self.db.query(TenderProject.project_id)
            .filter(TenderProject.project_id.isnot(None))
            .filter(TenderProject.site_name.like(f"%{self.PLATFORM_NAME}%"))
            .all()
        )
        processed_project_ids = set(existing_project_ids)
        log.info(f"已加载 {len(existing_project_ids)} 个已存在的项目ID到内存缓存")
        
        # 计算最早允许的发布日期
        earliest_date = None
        if self.days_before is not None and self.days_before > 0:
            from datetime import timedelta
            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")
        
        # 爬取列表
        page_index = 1  # 页码从1开始
        while page_index <= self.max_pages and total_count < self.daily_limit:
            # 反爬控制
            if page_index > 1:
                time.sleep(self.request_interval)
            
            log.debug(f"正在请求第{page_index}页数据")
            
            # 获取列表（带重试机制）
            max_page_retries = 3
            result = None
            for retry in range(max_page_retries):
                try:
                    result = get_doc_list(
                        session=session,
                        page_index=page_index,
                        page_size=self.page_size,
                        headers=self.headers_list
                    )
                    
                    if result and "data" in result:
                        break  # 成功获取数据，退出重试循环
                    else:
                        log.warning(f"第{page_index}页请求失败（第{retry+1}次尝试），响应无效")
                        
                except Exception as e:
                    log.warning(f"第{page_index}页请求异常（第{retry+1}次尝试）: {str(e)}")
                
                # 如果不是最后一次尝试，等待后重试
                if retry < max_page_retries - 1:
                    wait_time = (retry + 1) * 2  # 递增等待时间：2秒、4秒、6秒
                    log.info(f"等待 {wait_time} 秒后重试第{page_index}页...")
                    time.sleep(wait_time)
            
            # 如果所有重试都失败，记录错误并继续下一页（不中断整个爬虫）
            if not result or "data" not in result:
                log.error(f"第{page_index}页请求失败，已达最大重试次数，跳过该页继续爬取")
                page_index += 1
                continue
            
            data = result.get("data", {})
            rows = data.get("rows", [])
            
            if not rows:
                log.info(f"第{page_index}页无数据，停止爬取")
                break
            
            log.debug(f"第{page_index}页获取到{len(rows)}个项目")
            
            # 处理每个项目
            for item in rows:
                if total_count >= self.daily_limit:
                    break
                
                try:
                    # 解析项目数据
                    project_data = self._parse_project(item, today, earliest_date)
                    
                    if not project_data:
                        continue
                    
                    # 检查是否已存在
                    project_id = project_data.get("project_id")
                    if project_id in processed_project_ids:
                        log.debug(f"项目已存在，跳过: {project_id}")
                        continue
                    
                    # 添加到已处理集合
                    processed_project_ids.add(project_id)
                    
                    # 获取文件URL并下载文件
                    file_path, file_format = self._download_document(
                        session, project_id, project_data
                    )
                    if file_path:
                        project_data["file_path"] = file_path
                        project_data["file_format"] = file_format
                    
                    # 保存项目
                    saved_project = save_project(self.db, project_data)
                    projects.append(saved_project)
                    total_count += 1
                    log.debug(f"已爬取项目: {project_data['project_name'][:50]}...")
                    
                except Exception as e:
                    log.error(f"处理项目失败: {str(e)}", exc_info=True)
                    continue
            
            # 检查是否还有更多页
            total = data.get("total", 0)
            if page_index * self.page_size >= total:
                log.info(f"已爬取所有页面（共 {total} 个项目）")
                break
            
            # 下一页
            page_index += 1
        
        # 关闭会话和数据库连接
        session.close()
        self.db.close()
        
        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")
        
        return projects
    
    def _parse_project(self, item, today, earliest_date):
        """
        解析项目数据
        
        Args:
            item: API返回的项目数据项
            today: 今天的日期
            earliest_date: 最早允许的发布日期（None表示不限制）
        
        Returns:
            项目数据字典，解析失败返回None
        """
        try:
            # 提取项目ID
            prj_id = item.get("PrjId")
            if not prj_id:
                log.warning(f"项目数据缺少PrjId: {item}")
                return None
            
            # 提取项目名称
            prj_name = item.get("PrjName", "").strip()
            if not prj_name:
                log.warning(f"项目 {prj_id} 缺少项目名称")
                return None
            
            # 提取发布时间
            signup_start_date_str = item.get("SignUpStartDate", "")
            if not signup_start_date_str:
                log.warning(f"项目 {prj_id} 缺少发布时间")
                return None
            
            # 解析发布时间（需要返回 datetime 对象，因为数据库字段是 DateTime 类型）
            try:
                signup_start_datetime = datetime.strptime(signup_start_date_str, "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    signup_start_datetime = datetime.strptime(signup_start_date_str, "%Y-%m-%d")
                except:
                    log.warning(f"项目 {prj_id} 发布时间格式错误: {signup_start_date_str}")
                    return None
            
            # 时间过滤（转换为 date 进行比较）
            signup_start_date = signup_start_datetime.date()
            if earliest_date and signup_start_date < earliest_date:
                log.debug(f"项目 {prj_id} 发布时间 {signup_start_date} 早于限制日期 {earliest_date}，跳过")
                return None
            
            # 过滤：只爬取"公开招标的项目"（根据注释，但实际API中可能是"电子比选"等）
            # 如果需要过滤特定类型，可以在这里添加
            ztb_type_name = item.get("ZTBTypeName", "")
            # log.debug(f"项目 {prj_id} 类型: {ztb_type_name}")
            
            # 提取项目编号
            prj_no = item.get("PrjNo", "")
            
            # 提取报名截止时间
            signup_end_date_str = item.get("SignUpEndDate", "")
            signup_end_date = None
            if signup_end_date_str:
                try:
                    signup_end_date = datetime.strptime(signup_end_date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    try:
                        signup_end_date = datetime.strptime(signup_end_date_str, "%Y-%m-%d")
                    except:
                        pass
            
            # 构建项目数据
            project_data = {
                "project_id": prj_id,
                "project_name": prj_name,
                "site_name": f"{self.PLATFORM_NAME}",
                "publish_time": signup_start_datetime,  # 使用 publish_time 而不是 publish_date，必须是 datetime 对象
                # 注意：project_no 和 project_type 不是数据库字段，相关信息已包含在 evaluation_content 中
                "status": ProjectStatus.DOWNLOADED,
                "evaluation_content": f"项目编号：{prj_no}\n项目类型：{ztb_type_name}\n报名开始时间：{signup_start_date_str}\n报名截止时间：{signup_end_date_str if signup_end_date_str else '未知'}",
            }
            
            return project_data
            
        except Exception as e:
            log.error(f"解析项目数据失败: {str(e)}", exc_info=True)
            return None
    
    def _download_document(self, session, project_id, project_data):
        """
        下载项目文档
        
        Args:
            session: requests.Session 对象
            project_id: 项目ID
            project_data: 项目数据字典
        
        Returns:
            (file_path, file_format) 元组，失败返回 (None, None)
        """
        try:
            # 获取文件URL
            file_url = get_file_url(
                session=session,
                prj_id=project_id,
                headers=self.headers_list
            )
            
            if not file_url:
                log.warning(f"项目 {project_id} 获取文件URL失败")
                return None, None
            
            # 从file_url中提取文件名
            # file_url格式: /MyUpfiles/2026/01/16/xxx_文件名.doc
            file_url_parts = file_url.split('/')
            original_filename = file_url_parts[-1] if file_url_parts else "document"
            
            # 确定文件格式
            if original_filename.lower().endswith('.pdf'):
                file_format = 'pdf'
            elif original_filename.lower().endswith('.doc'):
                file_format = 'doc'
            elif original_filename.lower().endswith('.docx'):
                file_format = 'docx'
            else:
                # 尝试从Content-Type判断，这里先默认pdf
                file_format = 'pdf'
            
            # 构建保存路径
            # 使用项目ID和文件名构建唯一文件名
            safe_project_name = "".join(c for c in project_data.get("project_name", "")[:50] if c.isalnum() or c in (' ', '-', '_', '(', ')')).strip()
            safe_project_name = safe_project_name.replace(' ', '_')
            
            filename = f"ningbo_{project_id}_{safe_project_name}.{file_format}"
            file_path = os.path.join(FILES_DIR, "ningbo", filename)
            
            # 下载文件
            success = download_file(
                session=session,
                file_url=file_url,
                save_path=file_path,
                headers=self.headers_download
            )
            
            if success:
                log.info(f"文件下载成功: {file_path}")
                return file_path, file_format
            else:
                log.warning(f"项目 {project_id} 文件下载失败")
                return None, None
                
        except Exception as e:
            log.error(f"下载项目 {project_id} 文档失败: {str(e)}", exc_info=True)
            return None, None
