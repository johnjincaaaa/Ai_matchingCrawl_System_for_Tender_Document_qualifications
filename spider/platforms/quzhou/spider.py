"""衢州市阳光交易服务平台爬虫实现"""

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
    from .request_handler import (
        get_project_list,
        get_doc_detail,
        init_captcha,
        check_captcha,
        download_file,
    )
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.quzhou.config import PLATFORM_CONFIG
    from spider.platforms.quzhou.request_handler import (
        get_project_list,
        get_doc_detail,
        init_captcha,
        check_captcha,
        download_file,
    )


@SpiderManager.register
class QuZhouTenderSpider(BaseSpider):
    """衢州市阳光交易服务平台爬虫"""

    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]

    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.headers_download = PLATFORM_CONFIG["headers_download"]
        self.headers_captcha = PLATFORM_CONFIG["headers_captcha"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
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

            log.debug(f"正在请求第{page_no}页数据")
            result = get_project_list(
                session=session,
                page=page_no,
                headers=self.headers_list,
                cookies=self.cookies,
            )

            if not result:
                log.warning(f"第{page_no}页请求失败或返回为空")
                break

            if len(result) == 0:
                log.info(f"第{page_no}页无数据，停止爬取")
                break

            log.debug(f"第{page_no}页获取到{len(result)}个项目")

            for item in result:
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

                    file_path, file_format = self._download_document(
                        session, project_id, project_data
                    )
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
            href = item.get("href", "")
            title = item.get("title", "")
            date_str = item.get("date", "")
            region = item.get("region", "衢州市")

            if not href or not title:
                log.warning("项目缺少href或title，跳过")
                return None

            # 从href中提取项目ID（使用URL的最后一部分作为ID）
            # 格式：/jyxx/001004/001004001/001004001001/20260123/c8258eb1-cc17-45b0-a68d-6c78be53594e.html
            project_id = href.split('/')[-1].replace('.html', '')
            if not project_id:
                log.warning(f"无法从href提取项目ID: {href}")
                return None

            # 解析发布时间
            publish_time = None
            if date_str:
                try:
                    publish_time = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    log.warning(f"无法解析发布时间格式: {date_str}")
                    return None
            else:
                # 如果没有日期，尝试从href中提取（格式：/jyxx/.../20260123/...）
                parts = href.split('/')
                for part in parts:
                    if len(part) == 8 and part.isdigit():
                        try:
                            publish_time = datetime.strptime(part, "%Y%m%d")
                            break
                        except ValueError:
                            continue

            if not publish_time:
                log.warning(f"无法确定发布时间: {href}")
                return None

            project_date = publish_time.date()
            if self.days_before is not None:
                if project_date < earliest_date or project_date > today:
                    log.debug(
                        f"项目 {project_id} 日期 {project_date} 不在时间范围内 ({earliest_date} 至 {today})，跳过"
                    )
                    return None
            else:
                if project_date < today:
                    log.debug(
                        f"项目 {project_id} 日期 {project_date} 早于今天 {today}，跳过"
                    )
                    return None

            # 构建详情页URL
            if href.startswith('/'):
                detail_url = urljoin(self.base_url, href)
            elif href.startswith('http'):
                detail_url = href
            else:
                detail_url = urljoin(self.base_url, '/' + href)

            return {
                "project_name": title,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),
                "download_url": detail_url,
                "project_id": project_id,
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

            # 获取详情页并解析下载信息
            download_info = get_doc_detail(
                session=session,
                detail_url=detail_url,
                headers=self.headers_detail,
                cookies=self.cookies,
            )

            if not download_info:
                log.warning(f"项目 {project_id} 无法获取下载信息，跳过下载")
                return None, None

            attach_guid = download_info.get("attachGuid")
            app_url_flag = download_info.get("appUrlFlag", "ztb001")
            site_guid = download_info.get("siteGuid", "")

            if not attach_guid:
                log.warning(f"项目 {project_id} 缺少attachGuid，跳过下载")
                return None, None

            # 初始化验证码
            captcha_info = init_captcha(
                session=session,
                headers=self.headers_captcha,
                cookies=self.cookies,
            )

            if not captcha_info:
                log.warning(f"项目 {project_id} 无法初始化验证码，跳过下载")
                return None, None

            # 验证验证码
            validate_code = check_captcha(
                session=session,
                captcha_id=captcha_info.get("captchaID"),
                click_words=captcha_info.get("clickWords", []),
                backpic_image_base64=captcha_info.get("backpicImageBase64", ""),
                headers=self.headers_captcha,
                cookies=self.cookies,
            )

            if not validate_code:
                log.warning(f"项目 {project_id} 验证码验证失败，跳过下载")
                return None, None

            # 准备文件保存路径
            project_name = project_data.get("project_name", "")[:50]
            safe_name = "".join(
                c for c in project_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()
            safe_name = safe_name or str(project_id)
            safe_id = str(project_id).replace("/", "_").replace("\\", "_")

            file_dir = os.path.join(FILES_DIR, self.PLATFORM_CODE)
            os.makedirs(file_dir, exist_ok=True)
            file_path = os.path.join(
                file_dir, f"{self.PLATFORM_CODE}_{safe_id}_{safe_name}.pdf"
            )

            # 下载文件
            file_ext = download_file(
                session=session,
                attach_guid=attach_guid,
                app_url_flag=app_url_flag,
                site_guid=site_guid,
                validate_code=validate_code,
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
