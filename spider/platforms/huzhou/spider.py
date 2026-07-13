"""湖州市招标平台爬虫实现"""

import os
import time
import re
from datetime import datetime
from typing import Optional, Tuple

import requests
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import FILES_DIR

# 兼容相对导入和绝对导入
try:
    from ...base_spider import BaseSpider
    from ...spider_manager import SpiderManager
    from .config import PLATFORM_CONFIG
    from .request_handler import get_doc_list, get_doc_detail, download_file
except ImportError:
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager
    from spider.platforms.huzhou.config import PLATFORM_CONFIG
    from spider.platforms.huzhou.request_handler import get_doc_list, get_doc_detail, download_file


@SpiderManager.register
class HuZhouTenderSpider(BaseSpider):
    """湖州市绿色采购服务平台爬虫"""
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """初始化爬虫"""
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        
        # 平台URL配置
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.list_url_template = PLATFORM_CONFIG["list_url_template"]
        
        # 请求配置
        self.headers_list = PLATFORM_CONFIG["headers_list"]
        self.headers_detail = PLATFORM_CONFIG["headers_detail"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        
        # 爬取配置
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 10)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)

        # 整轮复用的 sid（避免每个项目都开浏览器获取），首次获取后缓存
        self._sid = None
        # 连续下载失败计数：sid 失效/系统性失败时用于尽早终止，避免空跑 50 页
        self._consecutive_dl_failures = 0
        self._max_consecutive_dl_failures = PLATFORM_CONFIG.get("max_consecutive_dl_failures", 5)

    def run(self):
        """执行爬虫主逻辑"""
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        
        # 创建会话
        session = requests.Session()
        session.headers.update(self.headers_list)
        session.cookies.update(self.cookies)

        # CloudWAF 预热：湖州站点位于华为 CloudWAF 之后，纯 requests + 过期 Cookie 会被
        # 直接 418 拦截。这里用一次真实浏览器访问取回新鲜 Cookie，供整轮 requests 复用，
        # 避免为每个项目反复开浏览器（此前“死循环重试”的主因之一）。
        self._warmup_waf(session)

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
            
            # 获取列表（HTML解析）
            items = get_doc_list(
                session=session,
                page=page_no,
                headers=self.headers_list,
                cookies=self.cookies
            )
            
            if items == "WAF_BLOCKED":
                log.error(
                    f"{self.PLATFORM_NAME}被 CloudWAF 拦截，终止本轮爬取。"
                    f"请更新 config.py 中的 Cookie，或确保已安装 DrissionPage 以自动预热。"
                )
                break

            if items is None:
                log.warning(f"第{page_no}页请求失败")
                break

            if not items:
                log.info(f"第{page_no}页无数据，停止爬取")
                break
            
            log.debug(f"第{page_no}页获取到{len(items)}个项目")
            
            # 处理每个项目
            for item in items:
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
                    
                    # 如果没有文件（找不到attachGuid或下载失败），直接跳过，不保存也不计入配额
                    if not file_path:
                        log.debug(f"项目 {project_id} 无法获取文件，跳过保存（不计入配额）")
                        # 连续多次因系统性原因（如 sid 失效导致验证码 100% 失败）下载失败时，
                        # 提前终止整轮，避免空跑剩余页码（此前“死循环重试”的观感来源）。
                        if self._consecutive_dl_failures >= self._max_consecutive_dl_failures:
                            log.error(
                                f"连续 {self._consecutive_dl_failures} 个项目下载失败，"
                                f"疑似 sid 失效或验证码接口异常，提前终止{self.PLATFORM_NAME}爬取。"
                                f"请刷新 config.py 中的 sid/Cookie。"
                            )
                            page_no = self.max_pages + 1  # 触发外层 while 退出
                            break
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
            
            page_no += 1
        
        # 关闭会话和数据库连接
        session.close()
        self.db.close()
        
        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")

        return projects

    def _warmup_waf(self, session):
        """用真实浏览器预热一次，取回可通过 CloudWAF 的新鲜 Cookie 并写入 session/self.cookies。"""
        if not PLATFORM_CONFIG.get("ocr_enabled", False):
            return
        try:
            from .utils import warmup_waf_cookies, DRISSIONPAGE_AVAILABLE
            if not DRISSIONPAGE_AVAILABLE:
                log.warning("未安装 DrissionPage，跳过 CloudWAF 预热，列表请求可能被 418 拦截")
                return
            fresh = warmup_waf_cookies(self.base_url + "/")
            if fresh:
                # 合并新鲜 Cookie（保留 oauth 等必要项）
                self.cookies.update({k: v for k, v in fresh.items() if v})
                session.cookies.update(self.cookies)
                if fresh.get("sid"):
                    self._sid = fresh["sid"]
                log.info("CloudWAF 预热完成，已更新会话 Cookie")
        except Exception as e:
            log.warning(f"CloudWAF 预热异常（将继续尝试直连）: {str(e)}")

    def _parse_project(self, item, today, earliest_date):
        """
        解析项目数据
        
        Args:
            item: 从HTML解析出的项目数据（字典）
            today: 今日日期
            earliest_date: 最早允许的发布日期
        
        Returns:
            dict: 项目数据字典，格式需符合save_project函数要求
        """
        try:
            # 提取项目标题
            project_name = item.get("title")
            if not project_name:
                log.warning("项目缺少标题，跳过")
                return None
            
            # 提取详情URL
            detail_url = item.get("url")
            if not detail_url:
                log.warning(f"项目 {project_name[:50]}... 缺少详情URL，跳过")
                return None
            
            # 从URL中提取项目ID（URL格式：/jyxx/.../日期/uuid.html）
            # 例如：/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html
            url_match = re.search(r'/([0-9a-fA-F-]{36})\.html', detail_url)
            if url_match:
                project_id = url_match.group(1)
            else:
                # 如果无法提取UUID，使用URL的hash作为ID
                import hashlib
                project_id = hashlib.md5(detail_url.encode()).hexdigest()
            
            # 提取发布时间
            date_str = item.get("date", "")
            if not date_str:
                log.warning(f"项目 {project_name[:50]}... 缺少发布时间，跳过")
                return None
            
            # 解析发布时间（格式：2026/01/19）
            try:
                publish_time = datetime.strptime(date_str, "%Y/%m/%d")
            except ValueError:
                try:
                    publish_time = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    log.warning(f"无法解析发布时间格式: {date_str}")
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
            region = item.get("region", "湖州市")
            
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
            session: requests.Session对象
            project_id: 项目ID
            project_data: 项目数据字典
        
        Returns:
            tuple: (file_path, file_format) 或 (None, None)
        """
        try:
            detail_url = project_data.get("download_url")
            if not detail_url:
                log.warning(f"项目 {project_id} 缺少详情URL，跳过下载")
                return None, None
            
            attach_guid = get_doc_detail(
                session=session,
                detail_url=detail_url,
                headers=self.headers_detail,
                cookies=self.cookies
            )
            
            if not attach_guid:
                log.debug(f"项目 {project_id} 无法获取attachGuid，跳过下载")
                return None, None
            
            project_name = project_data.get("project_name", "unknown")
            safe_name = "".join(c for c in project_name[:50] if c.isalnum() or c in (' ', '-', '_'))
            safe_name = safe_name.strip()
            if not safe_name:
                safe_name = project_id
            
            file_format = "pdf"
            file_name = f"{self.PLATFORM_CODE}_{project_id}_{safe_name}.{file_format}"
            file_path = os.path.join(FILES_DIR, self.PLATFORM_CODE, file_name)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # sid 复用策略：整轮只获取一次，避免每个项目都开浏览器（此前“死循环”主因）。
            sid = self._sid
            dddd_ocr_available = False

            if PLATFORM_CONFIG.get("ocr_enabled", False):
                try:
                    from .utils import auto_get_sid, DDDDOCR_AVAILABLE, DRISSIONPAGE_AVAILABLE
                    dddd_ocr_available = DDDDOCR_AVAILABLE

                    if not DRISSIONPAGE_AVAILABLE:
                        log.error("OCR已启用，但DrissionPage未安装。请安装: pip install DrissionPage")
                    elif not DDDDOCR_AVAILABLE:
                        log.error("OCR已启用，但ddddocr未安装。请安装: pip install ddddocr")
                    elif not sid:
                        # 仅当尚无缓存 sid 时才开浏览器获取一次
                        log.info(f"OCR已启用，开始自动获取sid（详情页: {detail_url[:80]}...）")
                        auto_sid = auto_get_sid(detail_url)
                        if auto_sid:
                            sid = auto_sid
                            self._sid = auto_sid  # 缓存，供后续项目复用
                            log.info(f"自动获取sid成功: {sid[:20]}...")
                        else:
                            log.warning("自动获取sid返回None，将尝试其他方式")
                except ImportError as e:
                    log.error(f"导入OCR工具失败: {str(e)}。请确保已安装: pip install ddddocr DrissionPage")
                except Exception as e:
                    log.warning(f"自动获取sid失败: {str(e)}", exc_info=True)

            if not sid:
                sid = PLATFORM_CONFIG.get("sid_fallback")

            if not sid:
                sid = self.cookies.get("sid")
            
            if not sid:
                log.warning(
                    f"项目 {project_id} 缺少sid配置，无法下载\n"
                    f"解决方案：\n"
                    f"1. 在 config.py 中设置 sid_fallback\n"
                    f"2. 或在 config.py 中设置 ocr_enabled=True（需要安装DrissionPage）"
                )
                return None, None
            
            max_captcha_retries = PLATFORM_CONFIG.get("max_captcha_retries", 5)
            captcha_attempt = 0
            last_error = ""
            
            while captcha_attempt <= max_captcha_retries:
                captcha_attempt += 1
                
                verification_code = None
                verification_guid = None
                
                if PLATFORM_CONFIG.get("ocr_enabled", False) and dddd_ocr_available:
                    try:
                        from .utils import get_verification_code_with_ocr
                        log.info(f"正在获取验证码（第{captcha_attempt}次，最多{max_captcha_retries}次）...")
                        verification_info = get_verification_code_with_ocr(sid)
                        if verification_info:
                            verification_code = verification_info.get("code")
                            verification_guid = verification_info.get("guid")
                            log.info(f"验证码获取成功: {verification_code}, guid: {verification_guid[:20] if verification_guid else 'None'}...")
                        else:
                            log.warning("验证码获取失败，将尝试使用备用验证码")
                    except Exception as e:
                        log.warning(f"自动获取验证码失败: {str(e)}", exc_info=True)
                
                if not verification_code:
                    verification_code = PLATFORM_CONFIG.get("verification_code_fallback")
                    if verification_code:
                        log.info("使用备用验证码")
                        if not verification_guid and sid and dddd_ocr_available and PLATFORM_CONFIG.get("ocr_enabled", False):
                            try:
                                from .utils import get_verification_code_with_ocr
                                log.info("备用验证码缺少guid，尝试重新获取验证码...")
                                verification_info = get_verification_code_with_ocr(sid)
                                if verification_info:
                                    verification_code = verification_info.get("code")
                                    verification_guid = verification_info.get("guid")
                                    log.info(f"重新获取验证码成功: {verification_code}")
                            except Exception as e:
                                log.debug(f"重新获取验证码失败: {str(e)}")
                
                if not sid or not verification_code:
                    log.warning(
                        f"项目 {project_id} 缺少sid或验证码配置，无法下载。\n"
                        f"解决方案：\n"
                        f"1. 在 config.py 中配置 sid_fallback 和 verification_code_fallback\n"
                        f"2. 或安装 ddddocr 和 DrissionPage，启用自动获取：\n"
                        f"   - pip install ddddocr DrissionPage\n"
                        f"   - 在 config.py 中设置 ocr_enabled=True\n"
                        f"3. 或使用辅助工具手动获取（参考 spider/platforms/huzhou/utils.py）"
                    )
                    return None, None
                
                if not verification_guid:
                    verification_guid = verification_code
                    log.warning("verification_guid未设置，使用verification_code作为guid（可能影响下载成功率）")
                
                result = download_file(
                    session=session,
                    attach_guid=attach_guid,
                    save_path=file_path,
                    verification_code=verification_code,
                    verification_guid=verification_guid,
                    sid=sid,
                    headers=None,
                    cookies=None
                )
                
                if result.get("success") and os.path.exists(file_path):
                    log.info(f"文件下载成功: {file_path}")
                    self._consecutive_dl_failures = 0  # 成功即清零系统性失败计数
                    return file_path, file_format

                if result.get("is_captcha_error"):
                    last_error = result.get("error_msg", "验证码错误")
                    if captcha_attempt <= max_captcha_retries:
                        log.warning(f"验证码验证失败（第{captcha_attempt}次），将重新获取验证码后重试...")
                        time.sleep(2)
                        continue
                    else:
                        log.error(f"验证码重试已达最大次数（{max_captcha_retries}次），放弃下载: {last_error}")
                        break
                else:
                    last_error = result.get("error_msg", "未知错误")
                    log.warning(f"文件下载失败: {last_error}")
                    break

            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

            # 走到这里说明本项目在拿到 attachGuid 后仍下载失败（验证码耗尽/其他错误），
            # 属于系统性失败信号，计入连续失败计数供 run() 判断是否提前终止。
            self._consecutive_dl_failures += 1
            return None, None
            
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}", exc_info=True)
            return None, None
