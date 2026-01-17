"""杭州市招标平台爬虫实现"""

import requests
import json
import os
import time
from datetime import datetime
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
    from spider.platforms.hangzhou.config import PLATFORM_CONFIG
    from spider.platforms.hangzhou.request_handler import get_doc_list, get_doc_detail, download_file

# 这些导入在所有情况下都需要，放在try-except外
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import SPIDER_CONFIG, FILES_DIR


@SpiderManager.register
class HangZhouTenderSpider(BaseSpider):
    """杭州市公共资源交易网爬虫"""
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """初始化爬虫"""
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        
        # 平台URL配置
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_list_url = PLATFORM_CONFIG["api_list_url"]
        self.api_detail_url = PLATFORM_CONFIG["api_detail_url"]
        self.api_download_url = PLATFORM_CONFIG["api_download_url"]
        
        # 请求配置
        self.headers = PLATFORM_CONFIG["headers"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        
        # 爬取配置
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 10)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)
        self.default_params = PLATFORM_CONFIG.get("default_params", {})
    
    def run(self):
        """执行爬虫主逻辑"""
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        
        # 创建会话
        session = requests.Session()
        session.headers.update(self.headers)
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
        page_no = 1
        while page_no <= self.max_pages and total_count < self.daily_limit:
            # 反爬控制
            if page_no > 1:
                time.sleep(self.request_interval)
            
            log.debug(f"正在请求第{page_no}页数据")
            
            # 获取列表
            result = get_doc_list(
                session=session,
                current=page_no,
                size=self.page_size,
                area=self.default_params.get("area", 0),
                tradeType=self.default_params.get("tradeType", 5),
                afficheType=self.default_params.get("afficheType", 21),
                headers=self.headers,
                cookies=self.cookies
            )
            
            if not result or result.get("code") != 200:
                log.warning(f"第{page_no}页请求失败或返回错误")
                break
            
            data = result.get("data", {})
            records = data.get("records", [])
            
            if not records:
                log.info(f"第{page_no}页无数据，停止爬取")
                break
            
            log.debug(f"第{page_no}页获取到{len(records)}个项目")
            
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
                    
                    # 添加到已处理集合
                    processed_project_ids.add(project_id)
                    
                    # 获取详情并下载文件
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
                    log.error(f"处理项目失败: {str(e)}")
                    continue
            
            page_no += 1
        
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
            project_name = item.get("tenderName") or item.get("title")
            if not project_name:
                log.warning(f"项目ID {project_id} 缺少标题，跳过")
                return None
            
            # 提取发布时间
            publish_time_str = item.get("publishStarttime") or item.get("createTime")
            if not publish_time_str:
                log.warning(f"项目 {project_name[:50]}... 缺少发布时间，跳过")
                return None
            
            # 解析发布时间
            try:
                publish_time = datetime.strptime(publish_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
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
            
            # 提取区域信息（从area字段或其他字段）
            region = "杭州市"  # 默认值
            area_code = item.get("area")
            # 可以根据area_code映射到具体区域，这里先使用默认值
            
            # 构建项目数据字典
            project_data = {
                "project_name": project_name,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),  # 毫秒时间戳
                "download_url": f"{self.base_url}/detail/{project_id}",
                "project_id": str(project_id),
                "region": region,
                "status": ProjectStatus.DOWNLOADED,
            }
            
            return project_data
            
        except Exception as e:
            log.error(f"解析项目数据失败: {str(e)}")
            return None
    
    def _download_document(self, session, project_id, project_data):
        """
        下载项目文档
        
        Args:
            session: requests.Session对象
            project_id: 项目ID
            project_data: 项目数据字典
        
        Returns:
            tuple: (file_path, file_format) 或 (None, None)
        """
        try:
            # 获取详情
            detail_result = get_doc_detail(
                session=session,
                doc_id=project_id,
                headers=self.headers,
                cookies=self.cookies
            )
            
            if not detail_result or detail_result.get("code") != 200:
                log.warning(f"获取项目详情失败: {project_id}")
                return None, None
            
            detail_data = detail_result.get("data", {})
            file_list = detail_data.get("list", [])
            
            if not file_list:
                log.warning(f"项目 {project_id} 没有附件文件")
                return None, None
            
            # 查找招标文件（fileType=7通常是电子招标文件）
            target_file = None
            for file_item in file_list:
                file_type = file_item.get("fileType")
                # 优先选择fileType为7的文件（电子招标文件）
                if file_type == "7":
                    target_file = file_item
                    break
            
            # 如果没有找到type=7的文件，使用第一个文件
            if not target_file and file_list:
                target_file = file_list[0]
            
            if not target_file:
                log.warning(f"项目 {project_id} 未找到可下载的文件")
                return None, None
            
            file_service_id = target_file.get("fileServiceId")
            if not file_service_id:
                log.warning(f"文件缺少fileServiceId")
                return None, None
            
            # 生成文件名
            safe_project_id = str(project_id).replace('/', '_').replace('\\', '_')
            project_name = project_data.get("project_name", "")[:50]
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
                project_name = project_name.replace(char, '_')
            
            file_extension = target_file.get("fileExtension") or "pdf"
            filename = f"HZ_{project_name}_{safe_project_id}.{file_extension}"
            filepath = os.path.join(FILES_DIR, filename)
            
            # 下载文件
            if download_file(session, file_service_id, filepath, self.headers, self.cookies):
                return filepath, file_extension
            else:
                return None, None
                
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}")
            return None, None
