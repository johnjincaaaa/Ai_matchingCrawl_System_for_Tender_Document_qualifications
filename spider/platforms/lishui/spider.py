"""丽水市阳光采购服务平台爬虫实现"""

import os
import re
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
    from .request_handler import get_doc_list, get_doc_detail, download_file
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.lishui.config import PLATFORM_CONFIG
    from spider.platforms.lishui.request_handler import get_doc_list, get_doc_detail, download_file


@SpiderManager.register
class LiShuiTenderSpider(BaseSpider):
    """丽水市阳光采购服务平台爬虫"""

    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]

    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 10)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)

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

            items = get_doc_list(session=session, page=page_no, headers=self.headers_list, cookies=self.cookies)
            if items is None:
                log.warning(f"第{page_no}页请求失败")
                break
            if not items:
                log.info(f"第{page_no}页无数据，停止爬取")
                break

            for item in items:
                if total_count >= self.daily_limit:
                    break
                try:
                    project_data = self._parse_project(item, today, earliest_date)
                    if not project_data:
                        continue

                    project_id = project_data["project_id"]
                    if project_id in processed_ids:
                        continue
                    processed_ids.add(project_id)

                    file_path, file_format = self._download_document(session, project_id, project_data)
                    if not file_path:
                        continue

                    project_data["file_path"] = file_path
                    project_data["file_format"] = file_format

                    saved = save_project(self.db, project_data)
                    projects.append(saved)
                    total_count += 1
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
        try:
            project_name = item.get("title")
            detail_url = item.get("url")
            date_str = item.get("date") or ""
            region = item.get("region") or "丽水市"

            if not (project_name and detail_url and date_str):
                return None

            # project_id: 优先取 URL 里的 uuid
            m = re.search(r"/([0-9a-fA-F-]{36})\\.html", detail_url)
            if m:
                project_id = m.group(1)
            else:
                import hashlib

                project_id = hashlib.md5(detail_url.encode()).hexdigest()

            publish_time = None
            for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
                try:
                    publish_time = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            if not publish_time:
                return None

            project_date = publish_time.date()
            if self.days_before is not None:
                if earliest_date and (project_date < earliest_date or project_date > today):
                    return None
            else:
                if project_date < today:
                    return None

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
        except Exception:
            return None

    def _download_document(self, session, project_id, project_data):
        try:
            detail_url = project_data.get("download_url")
            attach_guid = get_doc_detail(
                session=session,
                detail_url=detail_url,
                headers=self.headers_detail,
                cookies=self.cookies,
            )
            if not attach_guid:
                return None, None

            project_name = project_data.get("project_name", "unknown")
            safe_name = "".join(c for c in project_name[:50] if c.isalnum() or c in (" ", "-", "_")).strip() or project_id
            file_format = "pdf"
            file_name = f"{self.PLATFORM_CODE}_{project_id}_{safe_name}.{file_format}"
            file_path = os.path.join(FILES_DIR, self.PLATFORM_CODE, file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            sid = None
            verification_code = None
            verification_guid = None

            # 自动获取 sid
            if PLATFORM_CONFIG.get("ocr_enabled", False):
                try:
                    from .utils import auto_get_sid, DDDDOCR_AVAILABLE, DRISSIONPAGE_AVAILABLE

                    if DRISSIONPAGE_AVAILABLE:
                        sid = auto_get_sid(detail_url)
                    else:
                        log.error("OCR已启用，但DrissionPage未安装。请安装: pip install DrissionPage")

                    if sid and DDDDOCR_AVAILABLE:
                        from .utils import get_verification_code_with_ocr

                        info = get_verification_code_with_ocr(sid)
                        if info:
                            verification_code = info.get("code")
                            verification_guid = info.get("guid")
                except Exception as e:
                    log.debug(f"自动获取sid/验证码失败: {str(e)}")

            # fallback
            sid = sid or PLATFORM_CONFIG.get("sid_fallback") or self.cookies.get("sid")
            if not sid:
                log.warning(f"项目 {project_id} 缺少sid配置，无法下载（可在 lishui/config.py 设置 sid_fallback 或启用OCR）")
                return None, None

            if not verification_code:
                verification_code = PLATFORM_CONFIG.get("verification_code_fallback")
            if not verification_guid and verification_code:
                verification_guid = verification_code

            if PLATFORM_CONFIG.get("ocr_enabled", False) and (not verification_code or not verification_guid):
                try:
                    from .utils import get_verification_code_with_ocr, DDDDOCR_AVAILABLE

                    if DDDDOCR_AVAILABLE:
                        info = get_verification_code_with_ocr(sid)
                        if info:
                            verification_code = info.get("code")
                            verification_guid = info.get("guid")
                except Exception:
                    pass

            if not (verification_code and verification_guid):
                log.warning(f"项目 {project_id} 缺少验证码配置，无法下载（建议启用OCR或设置备用验证码）")
                return None, None

            ok = download_file(
                session=session,
                attach_guid=attach_guid,
                save_path=file_path,
                verification_code=verification_code,
                verification_guid=verification_guid,
                sid=sid,
                headers=None,
                cookies=self.cookies,
            )
            if ok and os.path.exists(file_path):
                return file_path, file_format
            return None, None
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None

