"""嘉兴市招标平台爬虫实现"""

import requests
import json
import os
import time
from datetime import datetime
from typing import Optional, Tuple
# 兼容相对导入和绝对导入
try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG
    from .request_handler import get_doc_list, get_doc_detail, download_file
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.jiaxing.config import PLATFORM_CONFIG
    from spider.platforms.jiaxing.request_handler import get_doc_list, get_doc_detail, download_file

# 这些导入在所有情况下都需要，放在try-except外
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import SPIDER_CONFIG, FILES_DIR


@SpiderManager.register
class JiaXingTenderSpider(BaseSpider):
    """嘉兴禾采联综合采购服务平台爬虫"""
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """初始化爬虫"""
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        
        # 平台URL配置
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_list_url = PLATFORM_CONFIG["api_list_url"]
        
        # 请求配置
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        
        # 爬取配置
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 100)
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
        page_no = 0  # 页码从0开始（0表示第一页，10表示第二页）
        while page_no < self.max_pages * self.page_size and total_count < self.daily_limit:
            # 反爬控制
            if page_no > 0:
                time.sleep(self.request_interval)
            
            log.debug(f"正在请求第{page_no // self.page_size + 1}页数据（pn={page_no}）")
            
            # 获取列表
            result = get_doc_list(
                session=session,
                page=page_no,
                page_size=self.page_size,
                headers=self.headers_list,
                cookies=self.cookies
            )
            
            if not result or "result" not in result:
                log.warning(f"第{page_no // self.page_size + 1}页请求失败或返回错误")
                break
            
            result_data = result.get("result", {})
            records = result_data.get("records", [])
            
            if not records:
                log.info(f"第{page_no // self.page_size + 1}页无数据，停止爬取")
                break
            
            log.debug(f"第{page_no // self.page_size + 1}页获取到{len(records)}个项目")
            
            # 处理每个项目
            for item in records:
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
                    
                    # 先添加到已处理集合，避免重复处理（无论成功与否）
                    processed_project_ids.add(project_id)
                    
                    # 获取详情并下载文件
                    file_path, file_format = self._download_document(
                        session, project_id, project_data
                    )
                    
                    # 如果没有文件（找不到attachGuid或下载失败），直接跳过，不保存也不计入配额
                    if not file_path:
                        log.debug(f"项目 {project_id} 无法获取文件，跳过保存（不计入配额）")
                        continue
                    
                    # 只有成功下载文件的项目才保存到数据库
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
            
            # 下一页
            page_no += self.page_size
        
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
            item: API返回的项目数据（字典）
            today: 今日日期
            earliest_date: 最早允许的发布日期
        
        Returns:
            dict: 项目数据字典，格式需符合save_project函数要求
        """
        try:
            # 提取项目ID（必填）
            project_id = item.get("id")
            if not project_id:
                log.warning("项目缺少ID，跳过")
                return None
            
            # 提取项目标题
            project_name = item.get("titlenew") or item.get("title")
            if not project_name:
                log.warning(f"项目ID {project_id} 缺少标题，跳过")
                return None
            
            # 提取发布时间
            publish_time_str = item.get("webdate") or item.get("infodate")
            if not publish_time_str:
                log.warning(f"项目 {project_name[:50]}... 缺少发布时间，跳过")
                return None
            
            # 解析发布时间（格式：2026-01-16 09:00:00）
            try:
                publish_time = datetime.strptime(publish_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # 尝试其他格式
                    publish_time = datetime.strptime(publish_time_str, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    log.warning(f"无法解析发布时间格式: {publish_time_str}")
                    return None
            
            # 检查日期是否符合要求
            project_date = publish_time.date()
            if self.days_before is not None:
                if project_date < earliest_date or project_date > today:
                    return None  # 日期不符合要求
            else:
                if project_date < today:
                    return None  # 不是当日项目
            
            # 提取区域信息
            region = item.get("xiaquname", "嘉兴市")
            if not region:
                region = "嘉兴市"
            
            # 提取链接URL
            link_url = item.get("linkurl", "")
            detail_url = link_url
            if link_url and not link_url.startswith("http"):
                detail_url = self.base_url + link_url
            
            # 构建项目数据字典
            project_data = {
                "project_name": project_name,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),  # 毫秒时间戳
                "download_url": detail_url,
                "project_id": str(project_id),
                "region": region,
                "status": ProjectStatus.DOWNLOADED,
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
            detail_url = project_data.get("download_url")
            if not detail_url:
                log.warning(f"项目 {project_id} 缺少详情URL，跳过下载")
                return None, None
            
            # 获取attachGuid
            attach_guid = get_doc_detail(
                session=session,
                detail_url=detail_url,
                headers=self.headers_detail,
                cookies=self.cookies
            )
            
            if not attach_guid:
                # 静默处理：找不到attachGuid的项目直接跳过，不显示警告
                log.debug(f"项目 {project_id} 无法获取attachGuid，跳过下载")
                return None, None
            
            # 构建文件保存路径
            project_name = project_data.get("project_name", "unknown")
            # 清理文件名中的非法字符
            safe_name = "".join(c for c in project_name[:50] if c.isalnum() or c in (' ', '-', '_'))
            safe_name = safe_name.strip()
            if not safe_name:
                safe_name = project_id
            
            file_format = "pdf"  # 默认PDF格式
            file_name = f"{self.PLATFORM_CODE}_{project_id}_{safe_name}.{file_format}"
            file_path = os.path.join(FILES_DIR, self.PLATFORM_CODE, file_name)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 下载文件（使用备用验证码）
            validate_code = PLATFORM_CONFIG.get("validate_code_fallback")
            success = download_file(
                session=session,
                attach_guid=attach_guid,
                save_path=file_path,
                validate_code=validate_code,
                headers=None,  # 使用函数内部默认headers
                cookies=self.cookies
            )
            
            if success and os.path.exists(file_path):
                log.info(f"文件下载成功: {file_path}")
                return file_path, file_format
            else:
                log.warning(f"文件下载失败: {file_path}")
                return None, None
            
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None
