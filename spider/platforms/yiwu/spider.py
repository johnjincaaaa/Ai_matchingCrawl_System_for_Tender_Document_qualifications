"""义乌市阳光招标采购平台爬虫实现"""

import os
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import FILES_DIR

try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG
    from .request_handler import get_project_list, get_doc_detail, download_file
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.yiwu.config import PLATFORM_CONFIG
    from spider.platforms.yiwu.request_handler import get_project_list, get_doc_detail, download_file


@SpiderManager.register
class YiWuTenderSpider(BaseSpider):
    """义乌市阳光招标采购平台爬虫"""

    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]

    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_list_url = PLATFORM_CONFIG["api_list_url"]
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.headers_download = PLATFORM_CONFIG["headers_download"]
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
        # demo文件中没有使用cookies，所以这里也不更新cookies（即使COOKIES为空）
        # session.cookies.update(self.cookies)

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
        sdt = None  # API开始日期参数
        edt = None  # API结束日期参数
        
        # 注意：义乌市平台API可能不支持sdt和edt参数，或者这些参数会导致无数据
        # 因此，即使设置了days_before，也不在API层面设置时间范围
        # 而是在获取数据后，在代码层面进行时间过滤
        if self.days_before is not None and self.days_before > 0:
            from datetime import timedelta

            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")
            log.info(f"注意：不在API层面设置时间范围，将在代码层面进行过滤")
            
            # 不设置API时间范围参数，保持为空字符串（与demo一致）
            # sdt = earliest_date.strftime("%Y-%m-%d")
            # edt = today.strftime("%Y-%m-%d")

        page_no = 1
        while page_no <= self.max_pages and total_count < self.daily_limit:
            if page_no > 1:
                time.sleep(self.request_interval)

            log.debug(f"正在请求第{page_no}页数据")
            result = get_project_list(
                session=session,
                page=page_no,
                page_size=self.page_size,
                headers=self.headers_list,
                cookies=self.cookies,
                sdt=sdt,
                edt=edt,
            )

            if not result:
                log.warning(f"第{page_no}页请求失败或返回为空")
                break

            # 解析返回的JSON数据
            result_data = result.get("result", {})
            records = result_data.get("records", [])
            totalcount = result_data.get("totalcount", 0) if result_data else 0
            
            # 调试日志：记录解析结果
            log.debug(f"第{page_no}页解析结果: result_data键={list(result_data.keys())}, records数量={len(records)}")
            if result_data and "totalcount" in result_data:
                log.debug(f"第{page_no}页总记录数: {result_data.get('totalcount')}")
            
            # 不再需要fallback机制，因为已经不在API层面设置时间范围
            
            if not records:
                log.info(f"第{page_no}页无数据，停止爬取")
                # 调试日志：记录为什么无数据
                if not result_data:
                    log.warning(f"第{page_no}页result_data为空")
                elif "totalcount" in result_data:
                    log.warning(f"第{page_no}页totalcount={result_data.get('totalcount')}, 但records为空")
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
            # 从JSON数据中提取信息
            project_id = item.get("infoid") or item.get("id")
            if not project_id:
                log.warning("项目缺少infoid或id，跳过")
                return None

            project_name = item.get("title")
            if not project_name:
                log.warning(f"项目 {project_id} 缺少标题，跳过")
                return None

            # 解析发布时间
            publish_time_str = item.get("infodate") or item.get("webdate")
            if not publish_time_str:
                log.warning(f"项目 {project_id} 缺少发布时间，跳过")
                return None

            publish_time = None
            # 尝试多种时间格式
            time_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d",
            ]
            
            for fmt in time_formats:
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
                    log.debug(f"项目 {project_id} 日期 {project_date} 不在时间范围内 ({earliest_date} 至 {today})，跳过")
                    return None
            else:
                if project_date < today:
                    log.debug(f"项目 {project_id} 日期 {project_date} 早于今天 {today}，跳过")
                    return None

            # 构建详情页URL
            linkurl = item.get("linkurl", "")
            if linkurl:
                if linkurl.startswith('/'):
                    detail_url = urljoin(self.base_url, linkurl)
                elif linkurl.startswith('http'):
                    detail_url = linkurl
                else:
                    detail_url = urljoin(self.base_url, '/' + linkurl)
            else:
                log.warning(f"项目 {project_id} 缺少linkurl，跳过")
                return None

            region = item.get("infoa") or "义乌市"

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
            detail_url = project_data.get("download_url")
            if not detail_url:
                log.warning(f"项目 {project_id} 缺少详情URL，跳过下载")
                return None, None

            # 获取详情页并解析下载链接
            download_url = get_doc_detail(
                session=session,
                detail_url=detail_url,
                headers=self.headers_detail,
                cookies=self.cookies,
            )

            if not download_url:
                log.warning(f"项目 {project_id} 无法获取下载链接，跳过下载")
                return None, None

            # 准备文件保存路径
            project_name = project_data.get("project_name", "")[:50]
            safe_name = "".join(c for c in project_name if c.isalnum() or c in (" ", "-", "_")).strip()
            safe_name = safe_name or str(project_id)
            safe_id = str(project_id).replace("/", "_").replace("\\", "_")

            file_dir = os.path.join(FILES_DIR, self.PLATFORM_CODE)
            os.makedirs(file_dir, exist_ok=True)
            file_path = os.path.join(file_dir, f"{self.PLATFORM_CODE}_{safe_id}_{safe_name}.pdf")

            # 下载文件
            file_ext = download_file(
                session=session,
                download_url=download_url,
                save_path=file_path,
                headers=self.headers_download,
                cookies=self.cookies,
            )

            if file_ext:
                # 如果文件扩展名不匹配，重命名文件
                if not file_path.endswith(f".{file_ext}"):
                    new_path = file_path.rsplit(".", 1)[0] + f".{file_ext}"
                    if os.path.exists(file_path):
                        os.rename(file_path, new_path)
                    file_path = new_path
                return file_path, file_ext

            log.warning(f"项目 {project_id} 下载文件失败")
            return None, None
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None
