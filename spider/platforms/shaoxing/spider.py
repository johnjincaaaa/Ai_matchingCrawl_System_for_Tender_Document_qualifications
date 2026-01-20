"""绍兴市阳光采购服务平台爬虫实现"""

import os
import time
from datetime import datetime

import requests
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import FILES_DIR

try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG
    from .request_handler import get_bulletin_list, download_file
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.shaoxing.config import PLATFORM_CONFIG
    from spider.platforms.shaoxing.request_handler import get_bulletin_list, download_file


@SpiderManager.register
class ShaoXingTenderSpider(BaseSpider):
    """绍兴市阳光采购服务平台爬虫"""

    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]

    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_list_url = PLATFORM_CONFIG["api_list_url"]
        self.api_download_url = PLATFORM_CONFIG["api_download_url"]
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_download = PLATFORM_CONFIG["headers_download"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 8)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)
        self.default_params = PLATFORM_CONFIG.get("default_params", {})

    def run(self):
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")

        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")

        session = requests.Session()
        session.headers.update(self.headers_list)
        session.cookies.update(self.cookies)

        projects = []
        total_count = 0
        today = datetime.now().date()

        from utils.db import TenderProject

        existing_ids = set(
            row[0]
            for row in self.db.query(TenderProject.project_id)
            .filter(TenderProject.project_id.isnot(None))
            .all()
        )
        processed_ids = set(existing_ids)
        log.info(f"已加载 {len(existing_ids)} 个已存在的项目ID到内存缓存")

        earliest_date = None
        if self.days_before is not None and self.days_before > 0:
            from datetime import timedelta

            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")

        page_no = 1
        while page_no <= self.max_pages and total_count < self.daily_limit:
            if page_no > 1:
                time.sleep(self.request_interval)

            log.debug(f"正在请求第{page_no}页数据")
            result = get_bulletin_list(
                session=session,
                page_index=page_no,
                page_size=self.page_size,
                info_type_id=self.default_params.get("InfoTypeId", "D01"),
                class_id=self.default_params.get("classID", "21"),
                headers=self.headers_list,
                cookies=self.cookies,
            )

            if not result:
                log.warning(f"第{page_no}页请求失败或返回为空")
                break

            data = result.get("body", {}).get("data", {})
            records = data.get("bulletinList") or []

            if not records:
                log.info(f"第{page_no}页无数据，停止爬取")
                break

            log.debug(f"第{page_no}页获取到{len(records)}个项目")

            for item in records:
                if total_count >= self.daily_limit:
                    break
                try:
                    project_data = self._parse_project(item, today, earliest_date)
                    if not project_data:
                        continue

                    project_id = project_data.get("project_id")
                    if project_id in processed_ids:
                        log.debug(f"项目已存在，跳过: {project_id}")
                        continue
                    processed_ids.add(project_id)

                    file_path, file_format = self._download_document(session, project_id, project_data)
                    if file_path:
                        project_data["file_path"] = file_path
                        project_data["file_format"] = file_format

                    saved_project = save_project(self.db, project_data)
                    projects.append(saved_project)
                    total_count += 1
                    log.debug(f"已爬取项目: {project_data['project_name'][:50]}...")
                except Exception as e:
                    log.error(f"处理项目失败: {str(e)}", exc_info=True)
                    continue

            page_no += 1

        session.close()
        self.db.close()

        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")
        return projects

    def _parse_project(self, item, today, earliest_date):
        """解析列表项为项目数据"""
        try:
            project_id = item.get("bulletinId")
            if not project_id:
                log.warning("项目缺少bulletinId，跳过")
                return None

            project_name = item.get("bulletinTitle")
            if not project_name:
                log.warning(f"项目 {project_id} 缺少标题，跳过")
                return None

            publish_time_str = item.get("publishDate")
            if not publish_time_str:
                log.warning(f"项目 {project_id} 缺少发布时间，跳过")
                return None

            publish_time = None
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    publish_time = datetime.strptime(publish_time_str, fmt)
                    break
                except ValueError:
                    continue

            if not publish_time:
                log.warning(f"无法解析发布时间格式: {publish_time_str}")
                return None

            project_date = publish_time.date()
            if self.days_before is not None:
                if project_date < earliest_date or project_date > today:
                    return None
            else:
                if project_date < today:
                    return None

            region = item.get("areaName") or "绍兴市"
            detail_url = f"{self.base_url}/detail?bulletinId={project_id}"

            return {
                "project_name": project_name,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),
                "download_url": detail_url,
                "project_id": str(project_id),
                "region": region,
                "status": ProjectStatus.DOWNLOADED,
            }
        except Exception as e:
            log.error(f"解析项目数据失败: {str(e)}", exc_info=True)
            return None

    def _download_document(self, session, project_id, project_data):
        """下载附件"""
        try:
            project_name = project_data.get("project_name", "")[:50]
            safe_name = "".join(c for c in project_name if c.isalnum() or c in (" ", "-", "_")).strip()
            safe_name = safe_name or str(project_id)
            safe_id = str(project_id).replace("/", "_").replace("\\", "_")

            file_dir = os.path.join(FILES_DIR, self.PLATFORM_CODE)
            os.makedirs(file_dir, exist_ok=True)
            file_path = os.path.join(file_dir, f"{self.PLATFORM_CODE}_{safe_id}_{safe_name}.pdf")

            file_ext = download_file(
                session=session,
                bulletin_id=project_id,
                save_path=file_path,
                headers=self.headers_download,
                cookies=self.cookies,
            )

            if file_ext:
                if not file_path.endswith(f".{file_ext}"):
                    new_path = file_path.rsplit(".", 1)[0] + f".{file_ext}"
                    os.rename(file_path, new_path)
                    file_path = new_path
                return file_path, file_ext

            log.warning(f"项目 {project_id} 下载文件失败")
            return None, None
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None

