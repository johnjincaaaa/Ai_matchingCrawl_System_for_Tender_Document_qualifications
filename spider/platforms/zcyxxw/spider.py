"""浙江企业采购信息网（b.zhengcaiyun.cn）爬虫实现

爬取范围：采购公告 -> 公开招标公告（categoryCode = ZcyAnnouncement3001）。
"""

import os
import time
from datetime import datetime, timedelta

from utils.log import log
from utils.db import save_project, ProjectStatus
from config import FILES_DIR

try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG, BASE_URL, DETAIL_PARENT_ID
    from .request_handler import (
        ZcyBrowser, get_project_list, get_doc_detail, parse_attachments,
        download_file, extract_body_text, NO_ATTACHMENT,
    )
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.zcyxxw.config import PLATFORM_CONFIG, BASE_URL, DETAIL_PARENT_ID
    from spider.platforms.zcyxxw.request_handler import (
        ZcyBrowser, get_project_list, get_doc_detail, parse_attachments,
        download_file, extract_body_text, NO_ATTACHMENT,
    )


@SpiderManager.register
class ZcyXxwTenderSpider(BaseSpider):
    """浙江企业采购信息网爬虫（公开招标公告）"""

    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]

    def __init__(self, daily_limit=None, days_before=None, gov_cities=None, **kwargs):
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.gov_cities = gov_cities
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.headers_download = PLATFORM_CONFIG["headers_download"]
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 15)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)

    def run(self):
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        if self.gov_cities:
            log.info(f"地级市筛选：仅采集 {', '.join(self.gov_cities)}")

        # 列表/详情走无头浏览器（页面自带 X-Sign 签名并通过 WAF）；附件走 requests 直下 OSS。
        try:
            browser = ZcyBrowser().open()
        except Exception as e:
            log.error(f"{self.PLATFORM_NAME} 浏览器启动失败，无法爬取：{str(e)}", exc_info=True)
            self.db.close()
            self.crawled_count = 0
            return []

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
            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")

        page_no = 1
        while page_no <= self.max_pages and total_count < self.daily_limit:
            if page_no > 1:
                time.sleep(self.request_interval)

            log.debug(f"正在请求第{page_no}页数据")
            result = get_project_list(
                browser=browser,
                page=page_no,
                page_size=self.page_size,
            )
            if not result:
                log.warning(f"第{page_no}页请求失败或返回为空")
                break

            data_node = (result.get("result") or {}).get("data") or {}
            records = data_node.get("data") or []
            totalcount = data_node.get("total", 0)
            log.debug(f"第{page_no}页获取到{len(records)}个项目（总数{totalcount}）")

            if not records:
                log.info(f"第{page_no}页无数据，停止爬取")
                break

            # 当前页是否已全部早于时间范围（用于提前终止：列表按发布时间倒序）
            page_all_too_old = True

            for item in records:
                if total_count >= self.daily_limit:
                    break
                try:
                    project_data = self._parse_project(item, today, earliest_date)
                    if project_data is None:
                        continue
                    if project_data == "TOO_OLD":
                        continue  # 早于时间范围，但不代表整页都旧，继续看其它项
                    page_all_too_old = False

                    project_id = project_data.get("project_id")
                    if project_id in processed_ids:
                        log.debug(f"项目已存在，跳过: {project_id}")
                        continue
                    processed_ids.add(project_id)

                    file_path, file_format = self._download_document(browser, project_id, project_data)
                    if file_path == NO_ATTACHMENT:
                        project_data["status"] = ProjectStatus.EXCLUDED
                        project_data["error_msg"] = "详情页无附件（纯正文公告/公示），无标书文件可下载"
                        log.info(f"⏭️ 项目 {project_id} 详情页无附件，标记为已排除")
                    elif file_path:
                        project_data["file_path"] = file_path
                        project_data["file_format"] = file_format

                    saved_project = save_project(self.db, project_data)
                    projects.append(saved_project)
                    total_count += 1
                    log.debug(f"已爬取项目: {project_data['project_name'][:50]}...")
                except Exception as e:
                    log.error(f"处理项目失败: {str(e)}", exc_info=True)
                    continue

            # 若限定了时间范围且整页项目都早于范围，说明后续页更旧，停止翻页
            if earliest_date is not None and page_all_too_old:
                log.info(f"第{page_no}页所有项目均早于 {earliest_date}，停止翻页")
                break

            page_no += 1

        browser.close()
        self.db.close()
        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")
        return projects

    def _parse_project(self, item, today, earliest_date):
        """解析列表项为项目数据。日期早于范围返回 'TOO_OLD'；无效返回 None。"""
        try:
            article_id = item.get("articleId")
            if not article_id:
                log.warning("项目缺少 articleId，跳过")
                return None

            project_name = item.get("title") or item.get("projectName")
            if not project_name:
                log.warning(f"项目 {article_id} 缺少标题，跳过")
                return None

            # 发布时间为毫秒时间戳
            ts = item.get("publishDate")
            publish_time = None
            if ts:
                try:
                    publish_time = datetime.fromtimestamp(int(ts) / 1000)
                except Exception:
                    publish_time = None
            if not publish_time:
                log.warning(f"项目 {article_id} 发布时间无法解析：{ts}，跳过")
                return None

            project_date = publish_time.date()
            if self.days_before is not None:
                if project_date < earliest_date or project_date > today:
                    return "TOO_OLD"
            else:
                if project_date < today:
                    return "TOO_OLD"

            region = item.get("districtName") or "浙江省"

            # 地级市过滤：若设定了城市筛选，只保留 districtName 匹配的项目
            if self.gov_cities:
                if not any(city in (region or "") for city in self.gov_cities):
                    return None

            # 详情页入口 URL（浏览器可访问，供报告「来源网站」兜底/追溯）
            from urllib.parse import quote
            detail_url = (
                f"{BASE_URL}/luban/detail?articleId={quote(str(article_id), safe='')}"
                f"&parentId={DETAIL_PARENT_ID}"
            )

            return {
                "project_name": project_name,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),
                "download_url": detail_url,
                "project_id": str(article_id),
                "region": region,
                "status": ProjectStatus.DOWNLOADED,
                # 供 _download_document 使用（不落库）
                "_article_id": str(article_id),
            }
        except Exception as e:
            log.error(f"解析项目数据失败: {str(e)}", exc_info=True)
            return None

    def _download_document(self, browser, project_id, project_data):
        """获取详情、下载附件。返回 (file_path, file_ext)；无附件返回 (NO_ATTACHMENT, None)。"""
        try:
            article_id = project_data.pop("_article_id", None) or project_id
            detail_data = get_doc_detail(browser=browser, article_id=article_id)
            if not detail_data:
                log.warning(f"项目 {project_id} 详情获取失败，跳过下载")
                return None, None

            attachments = parse_attachments(detail_data)

            # 无附件：抓正文回填，交由上层标记排除、不当失败
            if not attachments:
                body = extract_body_text(detail_data)
                if body:
                    project_data["evaluation_content"] = body
                return NO_ATTACHMENT, None

            # 准备保存路径
            project_name = project_data.get("project_name", "")[:50]
            safe_name = "".join(c for c in project_name if c.isalnum() or c in (" ", "-", "_")).strip()
            safe_name = safe_name or str(project_id)
            safe_id = str(project_id).replace("/", "_").replace("\\", "_").replace("+", "_").replace("=", "")
            file_dir = os.path.join(FILES_DIR, self.PLATFORM_CODE)
            os.makedirs(file_dir, exist_ok=True)

            # 优先下载“正文/招标文件”类附件（取第一个可下载的即可满足解析需要）
            att = attachments[0]
            # 用附件原名的后缀（若有）确定初始保存名
            _, ext_from_name = os.path.splitext(att.get("name") or "")
            init_ext = ext_from_name.lstrip(".").lower() or "pdf"
            save_path = os.path.join(file_dir, f"{self.PLATFORM_CODE}_{safe_id}_{safe_name}.{init_ext}")

            file_ext = download_file(url=att["url"], save_path=save_path, headers=self.headers_download)
            if file_ext:
                if not save_path.endswith(f".{file_ext}"):
                    new_path = save_path.rsplit(".", 1)[0] + f".{file_ext}"
                    if os.path.exists(save_path):
                        if os.path.exists(new_path):
                            os.remove(new_path)
                        os.rename(save_path, new_path)
                    save_path = new_path
                return save_path, file_ext

            log.warning(f"项目 {project_id} 下载文件失败")
            return None, None
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None
