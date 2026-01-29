import time
import requests
import json
import os
import shutil
from utils.log import log
from config import SPIDER_CONFIG, FILES_DIR
from utils.db import get_db, save_project, TenderProject, ProjectStatus
from datetime import datetime
# 兼容相对导入和绝对导入
try:
    from .base_spider import BaseSpider
    from .spider_manager import SpiderManager
except ImportError:
    # 如果相对导入失败，尝试绝对导入（用于直接运行脚本时）
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager


class ZheJiangTenderSpider(BaseSpider):
    """浙江省招标网爬虫（支持多分类均衡爬取）

    说明：
    - daily_limit 为可选参数，不传时使用 config 中的默认值；
    - 通过 **kwargs 兼容旧代码中可能传入的多余关键词参数，避免出现
      "got an unexpected keyword argument" 之类的错误，使调用更健壮。
    """
    PLATFORM_NAME = "浙江省政府采购网"
    PLATFORM_CODE = "zhejiang"
    
    BASE_URL = "https://zfcg.czt.zj.gov.cn"
    API_URL = "https://zfcg.czt.zj.gov.cn/portal/category"
    # 旧版下载接口（已废弃，仅保留常量，实际下载逻辑见 _download_document）
    DOWNLOAD_URL = "https://zfcg.czt.zj.gov.cn/attachment/downloadUrl"

    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        # 调用父类初始化
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        # 兼容性处理：忽略未使用的关键字参数，防止旧脚本或外部调用传入多余参数时报错
        # 分类配置（新增）
        self.category_codes = [
            {"code": "110-978863", "name": "政府类"},
            {"code": "110-420383", "name": "非政府类"}
        ]
        # 区域配置
        self.district_codes = {
            "339900": "浙江省本级",
            "330100": "杭州市",
            "330200": "宁波市",
            "330300": "温州市",
            "330400": "嘉兴市",
            "330500": "湖州市",
            "330600": "绍兴市",
            "330700": "金华市",
            "330800": "衢州市",
            "330900": "舟山市",
            "331000": "台州市",
            "331100": "丽水市"
        }
        # 每个分类的爬取配额（平均分配，确保至少为1）
        self.category_quota = max(self.daily_limit // len(self.category_codes), 1)
        # 每个区域的爬取配额（确保至少为1）
        self.district_quota = max(self.category_quota // len(self.district_codes), 1)
        # 注意：crawled_count 和 max_retries 已在父类中初始化
        # 优化headers使其更像真实浏览器
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.BASE_URL,
            "Pragma": "no-cache",
            "Referer": f"{self.BASE_URL}/site/category?parentId=600007&childrenCode=ZcyAnnouncement",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }
        # cookies配置（用于浙江政府采购网列表与详情接口）
        self.cookies = {
            "_zcy_log_client_uuid": "3b7c1220-cba3-11f0-861e-89fd9d7f1874",
            "sensorsdata2015jssdkcross": "%7B%22distinct_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fmiddle.zcygov.cn%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlhYzVkZGQ1NWNhZmMtMDc5NTNlZGJkNDc0OTY0LTI2MDYxYjUxLTEzMjcxMDQtMTlhYzVkZGQ1NWRlNTMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%7D",
            "zcy_im_uuid": "7fc1785c-e118-40de-9121-f70e75b33961",
            "arialoadData": "false"
        }

        # 政采云主站登录配置（用于招标文件下载的新流程）
        # 默认使用 demo 账号密码，建议在生产环境通过环境变量 ZCY_USERNAME / ZCY_PASSWORD 配置
        self.zcy_username = os.getenv("ZCY_USERNAME", "qy1234567")
        self.zcy_password = os.getenv("ZCY_PASSWORD", "wqh284704256")
        self.zcy_login_url = "https://login.zcygov.cn/login"
        self.zcy_session: requests.Session | None = None


    def _fetch_page(self, session, category_code, page_no, district_code=None, is_gov=True):
        """获取单页数据（带重试机制）"""
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                data = {
                    "pageNo": page_no,
                    "pageSize": 15,
                    "categoryCode": category_code,
                    "procurementMethodCode": 1,
                    "isGov": is_gov,
                    "excludeDistrictPrefix": ["90", "006011", "H0"],
                    "_t": int(time.time() * 1000)
                }
                
                # 添加区域参数
                if district_code:
                    data["districtCode"] = [district_code]
                
                # 使用json.dumps格式化数据，与aaaa.py保持一致
                json_data = json.dumps(data, separators=(',', ':'))

                log.debug(f"正在请求分类[{category_code}]第{page_no}页数据")
                
                response = session.post(
                    self.API_URL,
                    data=json_data,  # 使用data参数而不是json参数
                    timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 15)
                )
                response.raise_for_status()
                
                # 检查响应是否有效
                if response.status_code == 200:
                    try:
                        json_response = response.json()
                        
                        # 检查success字段（如果存在）
                        if 'success' in json_response and not json_response.get('success'):
                            error_msg = json_response.get('error', '未知错误')
                            log.error(f"爬取分类[{category_code}]第{page_no}页API返回失败: {error_msg}")
                            return None
                        
                        # 按照aaaa.py的逻辑解析数据结构
                        # API响应结构: {success: true, result: {data: {data: [...]}}}
                        if json_response.get('result') and json_response['result'].get('data'):
                            data_obj = json_response['result']['data']
                            # 检查data字段中是否有data数组
                            if isinstance(data_obj, dict) and 'data' in data_obj:
                                items = data_obj.get('data', [])
                                if items:
                                    log.debug(f"成功获取分类[{category_code}]第{page_no}页数据，共{len(items)}条")
                                    return json_response
                                else:
                                    log.warning(f"爬取分类[{category_code}]第{page_no}页返回的数据列表为空")
                            else:
                                log.warning(f"爬取分类[{category_code}]第{page_no}页返回的数据结构异常: data字段格式不正确")
                                log.debug(f"响应内容: {json.dumps(json_response, ensure_ascii=False, default=str)[:500]}")
                        else:
                            log.warning(f"爬取分类[{category_code}]第{page_no}页返回的数据结构异常: 缺少result或data字段")
                            log.debug(f"响应内容: {json.dumps(json_response, ensure_ascii=False, default=str)[:500]}")
                    except ValueError as e:
                        log.error(f"爬取分类[{category_code}]第{page_no}页返回的不是有效的JSON数据: {str(e)}")
                        log.debug(f"响应内容（前500字符）: {response.text[:500]}")
                    except Exception as e:
                        log.error(f"解析分类[{category_code}]第{page_no}页响应时发生错误: {str(e)}")
                        import traceback
                        log.debug(traceback.format_exc())
                
            except requests.ConnectionError as e:
                log.error(f"爬取分类[{category_code}]第{page_no}页连接错误: {str(e)}")
                # 连接错误时增加等待时间
                if "10053" in str(e):  # Windows连接中止错误代码
                    wait_time = 5 * (retry_count + 1)
                    log.info(f"遇到连接中止错误，等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    time.sleep(SPIDER_CONFIG["anti_crawl"]["request_interval"])
            except requests.Timeout as e:
                log.error(f"爬取分类[{category_code}]第{page_no}页超时: {str(e)}")
                time.sleep(2)
            except Exception as e:
                log.error(f"爬取分类[{category_code}]第{page_no}页失败: {str(e)}")
                time.sleep(SPIDER_CONFIG["anti_crawl"]["request_interval"])
            
            retry_count += 1
            
            if retry_count <= self.max_retries:
                log.info(f"正在第{retry_count}次重试爬取分类[{category_code}]第{page_no}页...")
                # 指数退避策略
                backoff_time = SPIDER_CONFIG["anti_crawl"]["request_interval"] * (2 ** (retry_count - 1))
                time.sleep(min(backoff_time, 30))  # 最大等待30秒
            else:
                log.error(f"爬取分类[{category_code}]第{page_no}页达到最大重试次数，放弃该页")
        
        return None
    
    def _get_acquire_purfile_detail_url(self, article_id: str, session: requests.Session) -> str | None:
        """
        新流程第1步：通过浙江政府采购网详情接口获取 acquirePurFileDetailUrl
        等价于 aaaa_update.py 中的 get_download_url
        """
        try:
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": self.headers.get("User-Agent"),
                "X-Requested-With": "XMLHttpRequest",
                "sec-ch-ua": self.headers.get("sec-ch-ua", ""),
                "sec-ch-ua-mobile": self.headers.get("sec-ch-ua-mobile", "?0"),
                "sec-ch-ua-platform": self.headers.get("sec-ch-ua-platform", "\"Windows\""),
            }
            cookies = self.cookies.copy()
            url = f"{self.BASE_URL}/portal/detail"
            params = {
                "articleId": article_id,
                "timestamp": str(int(time.time() * 1000)),
            }
            resp = session.get(url, headers=headers, cookies=cookies, params=params,
                               timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 15))
            resp.raise_for_status()
            data = resp.json()
            log.debug(f"获取详情接口成功 articleId={article_id}, 响应前500字符: {json.dumps(data, ensure_ascii=False)[:500]}")
            result = data.get("result") or {}
            detail_data = result.get("data") or {}
            attachment_vo = detail_data.get("attachmentVO") or {}
            acquire_url = attachment_vo.get("acquirePurFileDetailUrl")
            if not acquire_url:
                log.warning(f"未从详情接口获取到 acquirePurFileDetailUrl, articleId={article_id}")
                return None
            log.info(f"获取到 acquirePurFileDetailUrl: {acquire_url}")
            return acquire_url
        except Exception as e:
            log.error(f"获取 acquirePurFileDetailUrl 失败 articleId={article_id}: {str(e)}")
            return None

    def _ensure_zcy_login(self) -> requests.Session | None:
        """
        新流程第2步：登录政采云主站（www.zcygov.cn），获取带鉴权 Cookie 的 Session
        等价于 aaaa_update.py 中的 login 函数，增加了日志与错误处理
        """
        if self.zcy_session is not None:
            return self.zcy_session

        session = requests.Session()

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Origin": "https://login.zcygov.cn",
            "Referer": "https://login.zcygov.cn/user-login/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"Microsoft Edge\";v=\"144\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
        }

        params = {
            "current_uri": "https://login.zcygov.cn/user-login/#/login",
        }

        try:
            # 预加载登录页，建立初始 Cookie
            session.get("https://login.zcygov.cn/user-login/#/login", headers=headers, timeout=15)

            files = {
                "platformCode": (None, "zcy"),
                "loginType": (None, "password"),
                "requestType": (None, "async"),
                "username": (None, self.zcy_username),
                "password": (None, self.zcy_password),
                "agreement": (None, "general_login_agreement"),
            }

            log.info("正在登录政采云主站用于下载招标文件...")
            resp = session.post(
                url=self.zcy_login_url,
                    params=params,
                headers=headers,
                files=files,
                timeout=15,
            )
            resp.raise_for_status()

            # 尝试解析 JSON，检查是否有 success 字段
            try:
                resp_json = resp.json()
                log.debug(f"政采云登录响应: {json.dumps(resp_json, ensure_ascii=False)[:500]}")
            except Exception:
                log.debug(f"政采云登录非JSON响应，前500字符: {resp.text[:500]}")

            # 简单校验：登录后应当持有部分关键 Cookie
            if not session.cookies:
                log.error("政采云登录后未获得任何 Cookie，可能登录失败")
                return None

            self.zcy_session = session
            log.info("政采云登录成功，将复用该会话下载文件")
            return session
        except Exception as e:
            log.error(f"政采云登录失败: {str(e)}")
            return None

    def _submit_and_get_file_url(self, login_session: requests.Session, acquire_url: str) -> tuple[str | None, str | None]:
        """
        新流程第3步+第4步：
        - 访问 acquirePurFileDetailUrl 页面
        - 提交表单 acquirePurFile/submit
        - 轮询 acquirePurFile/getPurFile 获取真实文件下载链接 fileUrl

        等价于 aaaa_update.py 中的 download 函数。
        返回 (file_url, file_name)
        """
        try:
            # projectId 为 acquire_url 最后一段
            project_id = acquire_url.rstrip("/").split("/")[-1]

            # 1）访问详情页，建立上下文
            login_session.get(acquire_url, timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 15))

            # 2）提交获取资格的表单
            submit_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/submit"
            payload = {
                "legalPerson": "王庆浩",
                "name": "衢州市乾元文化传媒有限公司",
                "contactAddress": "浙江省衢州市柯城区盈川西路2号1幢409室",
                "contactEmail": "2912492958@qq.com",
                "contactPhone": "15857012066",
                "contactName": "王庆浩",
                "projectId": project_id,
                "attachments": [],
                "needBilling": 1,
                "invoicinMethod": 2,
                "tabType": 0,
                "intentionItemList": [1],
            }
            data = json.dumps(payload, separators=(",", ":"))
            resp_submit = login_session.post(submit_url, data=data, timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 30))
            resp_submit.raise_for_status()
            log.debug(f"提交 acquirePurFile/submit 响应: {resp_submit.text[:300]}")

            # 3）获取真实文件下载链接
            get_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/getPurFile"
            params = {
                "timestamp": str(int(time.time() * 1000)),
                "projectId": project_id,
            }
            resp_get = login_session.get(get_url, params=params, timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 30))
            resp_get.raise_for_status()

            result = resp_get.json()
            log.debug(f"acquirePurFile/getPurFile 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
            if not result.get("success"):
                log.error(f"acquirePurFile/getPurFile 返回失败: {result}")
                return None, None

            files = result.get("result") or []
            if not files:
                log.warning("acquirePurFile/getPurFile 返回空文件列表")
                return None, None

            first_file = files[0]
            file_url = first_file.get("fileUrl")
            file_name = first_file.get("name")
            if not file_url:
                log.error(f"acquirePurFile/getPurFile 未包含 fileUrl: {first_file}")
                return None, None

            log.info(f"获取到政采云文件下载链接: {file_url}")
            return file_url, file_name
        except Exception as e:
            log.error(f"获取政采云文件下载链接失败: {str(e)}")
            return None, None

    def _download_document(self, article_id, project_title="", session=None):
        """下载招标文件（使用政采云新流程，带重试机制和增强的错误处理）"""
        max_retries = SPIDER_CONFIG["anti_crawl"].get("retry_times", 3)
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 1）通过浙江政府采购网详情接口拿到 acquirePurFileDetailUrl
                if not session:
                    # 如果上层未传入 session，则使用一个新的 session 访问 zfcg.czt.zj.gov.cn
                    use_zfcg_session = requests.Session()
                    use_zfcg_session.headers.update(self.headers)
                    use_zfcg_session.cookies.update(self.cookies)
                else:
                    use_zfcg_session = session

                acquire_url = self._get_acquire_purfile_detail_url(article_id, use_zfcg_session)
                if not acquire_url:
                    log.error(f"articleId={article_id} 未能获取 acquirePurFileDetailUrl")
                    return None, None

                # 2）确保已登录政采云主站，获取登录会话
                login_session = self._ensure_zcy_login()
                if not login_session:
                    log.error("无法登录政采云主站，放弃下载该文件")
                    return None, None

                # 3）提交 acquirePurFile 表单并获取最终文件下载链接
                download_link, remote_name = self._submit_and_get_file_url(login_session, acquire_url)
                if download_link:
                    log.info(f"获取到最终文件下载链接: {download_link}")
                        
                    # 提取文件扩展名
                    file_extension = download_link.split(".")[-1].split("?")[0]

                    # 处理article_id中的特殊字符，确保Windows系统兼容
                    safe_article_id = (
                        article_id.replace("/", "_")
                        .replace("\\", "_")
                        .replace(":", "_")
                        .replace("*", "_")
                        .replace("?", "_")
                        .replace('"', "_")
                        .replace("<", "_")
                        .replace(">", "_")
                        .replace("|", "_")
                    )
                        
                    # 处理项目标题/远程文件名，移除特殊字符，限制长度
                    base_title = project_title or (remote_name or "")
                    safe_title = base_title
                    for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|", " "]:
                        safe_title = safe_title.replace(char, "_")
                    safe_title = safe_title[:50] if safe_title else safe_article_id
                    filename = f"ZJ_{safe_title}_{safe_article_id}.{file_extension}"
                    
                    filepath = os.path.join(FILES_DIR, filename)
                    
                    # 下载文件（带分块超时处理）
                    log.info(f"开始下载文件: {filename}")
                    # 设置文件下载的超时时间（连接超时和读取超时分开设置）
                    download_timeout = (30, 120)  # (连接超时, 读取超时)
                    file_response = login_session.get(download_link, stream=True, timeout=download_timeout)
                    file_response.raise_for_status()
                    
                    # 获取文件大小
                    content_length = file_response.headers.get("content-length")
                    total_size = int(content_length) if content_length else 0
                    downloaded_size = 0
                    
                    # 创建临时文件路径
                    temp_filepath = f"{filepath}.tmp"
                    
                    # 如果目标文件已存在，先删除（避免重命名失败）
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                            log.debug(f"删除已存在的文件: {filepath}")
                        except Exception as e:
                            log.warning(f"删除已存在文件失败: {filepath}, 错误: {str(e)}")
                            # 如果删除失败，使用带时间戳的文件名
                            timestamp = int(time.time())
                            base_name = os.path.splitext(filename)[0]
                            ext = os.path.splitext(filename)[1]
                            filename = f"{base_name}_{timestamp}{ext}"
                            filepath = os.path.join(FILES_DIR, filename)
                            temp_filepath = f"{filepath}.tmp"
                    
                    # 如果临时文件已存在，先删除
                    if os.path.exists(temp_filepath):
                        try:
                            os.remove(temp_filepath)
                            log.debug(f"删除已存在的临时文件: {temp_filepath}")
                        except Exception as e:
                            log.warning(f"删除临时文件失败: {temp_filepath}, 错误: {str(e)}")
                    
                    # 分块下载文件
                    temp_file = None
                    try:
                        temp_file = open(temp_filepath, "wb")
                        # 设置块超时计时器
                        last_chunk_time = time.time()
                        for chunk in file_response.iter_content(chunk_size=8192):
                            # 检查是否超时（超过60秒未收到数据）
                            current_time = time.time()
                            if current_time - last_chunk_time > 60:
                                raise requests.Timeout("文件下载块超时")
                            
                            if chunk:
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                                last_chunk_time = current_time
                        
                        # 确保文件写入完成
                        temp_file.flush()
                        temp_file.close()
                        temp_file = None
                        
                        # 下载完成后重命名临时文件
                        # 再次检查目标文件是否存在（防止并发下载）
                        if os.path.exists(filepath):
                            try:
                                os.remove(filepath)
                                log.debug(f"重命名前删除已存在的目标文件: {filepath}")
                            except Exception as e:
                                log.warning(f"重命名前删除文件失败: {filepath}, 错误: {str(e)}")
                                # 如果删除失败，使用带时间戳的文件名
                                timestamp = int(time.time())
                                base_name = os.path.splitext(filename)[0]
                                ext = os.path.splitext(filename)[1]
                                filename = f"{base_name}_{timestamp}{ext}"
                                filepath = os.path.join(FILES_DIR, filename)
                        
                        # 重命名临时文件（使用shutil.move作为备选，更可靠）
                        try:
                            os.rename(temp_filepath, filepath)
                        except OSError:
                            # 如果rename失败，尝试使用shutil.move
                            shutil.move(temp_filepath, filepath)
                        
                        log.info(f"文件下载完成: {filepath} (大小: {downloaded_size/1024:.2f}KB)")
                        return filepath, file_extension
                    except Exception as e:
                        # 确保临时文件被关闭
                        if temp_file:
                            try:
                                temp_file.close()
                            except Exception:
                                pass
                        # 清理临时文件
                        if os.path.exists(temp_filepath):
                            try:
                                os.remove(temp_filepath)
                            except Exception:
                                pass
                        raise  # 重新抛出异常以便外层处理
                    else:
                        # 特殊情况：success为True但result为None
                        log.warning(f"API返回success=True但未提供下载链接，响应内容: {result}")
                        # 将这种情况视为需要重试的错误
                        retry_count += 1
                        if retry_count > max_retries:
                            log.error(f"下载文件[{article_id}]达到最大重试次数（{max_retries}次），放弃下载（空下载链接）")
                            break
                        wait_time = 2 * retry_count
                        log.info(f"遇到空下载链接，等待{wait_time}秒后重试（第{retry_count}次）...")
                        time.sleep(wait_time)
                        continue
                else:
                    error_msg = result.get('error', '未知错误')
                    log.error(f"获取下载链接失败: {error_msg}，响应内容: {result}")
                    # 将API错误情况也视为需要重试的错误
                    retry_count += 1
                    if retry_count > max_retries:
                        log.error(f"下载文件[{article_id}]达到最大重试次数（{max_retries}次），放弃下载（API错误）")
                        break
                    wait_time = 3 * retry_count
                    log.info(f"API返回错误，等待{wait_time}秒后重试（第{retry_count}次）...")
                    time.sleep(wait_time)
                    continue
                    
            except requests.ConnectionError as e:
                log.error(f"下载文件[{article_id}]连接错误: {str(e)}")
                # 连接错误时增加等待时间
                wait_time = 5 * (retry_count + 1)
                log.info(f"遇到连接错误，等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            except requests.Timeout as e:
                log.error(f"下载文件[{article_id}]超时: {str(e)}")
                wait_time = 3 * (retry_count + 1)
                log.info(f"遇到超时错误，等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            except Exception as e:
                log.error(f"下载文件失败[{article_id}]: {str(e)}")
                # 其他错误也进行重试
                wait_time = 2 * (retry_count + 1)
                log.info(f"遇到错误，等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            
            retry_count += 1
            
            if retry_count > max_retries:
                log.error(f"下载文件[{article_id}]达到最大重试次数（{max_retries}次），放弃下载")
                break
        
        return None, None

    # 注意：_is_duplicate 方法已在父类 BaseSpider 中实现，此处可以删除或保留作为覆盖
    
    def _extract_publish_date(self, item, category_name, district_name):
        """从API返回的item中提取发布时间
        
        根据测试脚本验证，API返回的publishDate字段是int类型的毫秒时间戳
        
        Args:
            item: API返回的项目数据字典
            category_name: 分类名称（用于日志）
            district_name: 区域名称（用于日志）
        
        Returns:
            tuple: (publish_date, publish_date_source) 或 (None, None)
            publish_date: 发布时间值（可能是时间戳或字符串）
            publish_date_source: 字段名
        """
        # 确保item是字典类型
        if not isinstance(item, dict):
            log.error(
                f"[{category_name}-{district_name}]无法提取发布时间：item不是字典类型，类型={type(item).__name__}"
            )
            return None, None
        
        # 按优先级尝试不同的字段名（根据测试，publishDate是最常见的）
        # 注意：只提取发布/公开相关字段，确保不会误提取创建时间（createTime/createDate）
        possible_fields = [
            ("publishDate", "publishDate"),  # 优先使用publishDate，这是API的标准字段
            ("pubDate", "pubDate"),
            ("publish_time", "publish_time"),
            ("publishTime", "publishTime"),
            ("releaseDate", "releaseDate"),
            ("release_date", "release_date"),
        ]
        
        for field_name, source_name in possible_fields:
            # 使用get方法安全获取字段值
            field_value = item.get(field_name)
            
            # 检查值是否存在且不为None
            if field_value is not None:
                # 检查值是否有效（不是空字符串、0等）
                if isinstance(field_value, (int, float)):
                    if field_value > 0:
                        # 验证时间戳合理性（13位毫秒时间戳应该在合理范围内）
                        # 检查是否为13位毫秒时间戳（大约在2000年到2200年之间）
                        timestamp_ms = int(field_value)
                        if 946684800000 <= timestamp_ms <= 7258089600000:  # 2000-01-01 到 2200-01-01
                            log.debug(
                                f"[{category_name}-{district_name}]成功提取发布时间: "
                                f"字段={source_name}, 值={timestamp_ms} "
                                f"(类型={type(field_value).__name__}), "
                                f"项目: {item.get('title', '未命名项目')[:50]}"
                            )
                            return field_value, source_name
                        else:
                            log.warning(
                                f"[{category_name}-{district_name}]字段{source_name}值超出合理范围，跳过: "
                                f"值={timestamp_ms}, 项目: {item.get('title', '未命名项目')[:50]}"
                            )
                    else:
                        log.warning(
                            f"[{category_name}-{district_name}]字段{source_name}值为0或负数，跳过: "
                            f"值={field_value}, 项目: {item.get('title', '未命名项目')[:50]}"
                        )
                elif isinstance(field_value, str) and field_value.strip():
                    # 尝试解析为数字字符串
                    try:
                        num_value = int(field_value.strip())
                        if num_value > 0:
                            # 验证时间戳合理性（13位毫秒时间戳应该在合理范围内）
                            if 946684800000 <= num_value <= 7258089600000:  # 2000-01-01 到 2200-01-01
                                log.debug(
                                    f"[{category_name}-{district_name}]成功提取发布时间: "
                                    f"字段={source_name}, 值={num_value} "
                                    f"(类型=数字字符串), "
                                    f"项目: {item.get('title', '未命名项目')[:50]}"
                                )
                                return num_value, source_name
                            else:
                                log.warning(
                                    f"[{category_name}-{district_name}]字段{source_name}值超出合理范围，跳过: "
                                    f"值={num_value}, 项目: {item.get('title', '未命名项目')[:50]}"
                                )
                    except ValueError:
                        # 可能是日期字符串，返回原值
                        log.debug(
                            f"[{category_name}-{district_name}]提取到字符串格式发布时间: "
                            f"字段={source_name}, 值={field_value}, "
                            f"项目: {item.get('title', '未命名项目')[:50]}"
                        )
                        return field_value, source_name
                else:
                    # 字段存在但值为空字符串或其他无效值
                    log.debug(
                        f"[{category_name}-{district_name}]字段{source_name}存在但值无效: "
                        f"值={field_value} (类型={type(field_value).__name__}), "
                        f"项目: {item.get('title', '未命名项目')[:50]}"
                    )
        
        # 如果所有字段都不存在，记录错误（包含所有可用字段信息）
        available_fields = list(item.keys()) if item else []
        # 列出所有时间相关字段（包括可能存在的createTime等，用于调试）
        time_related_fields = [k for k in available_fields if any(
            keyword in k.lower() for keyword in ['time', 'date', 'publish', 'release', 'create', 'update']
        )]
        
        # 检查是否存在创建时间字段（用于警告，防止误提取）
        create_time_fields = [k for k in available_fields if any(
            keyword in k.lower() for keyword in ['createtime', 'createdate', 'create_time', 'create_date']
        )]
        if create_time_fields:
            log.warning(
                f"[{category_name}-{district_name}]检测到创建时间字段: {create_time_fields}，"
                f"但不会提取它们（仅提取发布相关字段）。"
            )
        
        # 记录详细的错误信息
        log.error(
            f"[{category_name}-{district_name}]无法提取发布时间！"
            f"项目标题: {item.get('title', '未命名项目')[:50]}, "
            f"articleId: {item.get('articleId', 'N/A')}, "
            f"所有字段数量: {len(available_fields)}, "
            f"时间相关字段: {time_related_fields if time_related_fields else '无'}"
        )
        
        # 只在调试模式下输出完整item数据（避免日志过大）
        if log.level <= 10:  # DEBUG级别
            try:
                item_str = json.dumps(item, ensure_ascii=False, default=str)
                log.debug(f"完整item数据: {item_str[:1000]}")  # 限制长度
            except Exception as e:
                log.debug(f"无法序列化item数据: {str(e)}")
        
        return None, None

    def run(self):
        """
        执行爬虫（优先爬取当日文件，按顺序完成每个区域/分类）
        
        爬取顺序：
        1. 政府类 -> 浙江省本级当日文件（完毕）-> 杭州市当日文件（完毕）-> ... -> 所有区域完毕
        2. 非政府类 -> 浙江省本级当日文件（完毕）-> 杭州市当日文件（完毕）-> ... -> 所有区域完毕
        3. 达到配额即停止，不再爬取历史文件
        
        重要说明：
        - 发布时间必须从API返回的publishDate字段解析（时间戳格式，需去掉后三位），如果不存在或解析失败则跳过该项目
        - 区域名称优先使用API返回的districtName字段，如果没有则使用district_codes映射
        """
        log.info(f"开始爬取浙江省招标网，总配额: {self.daily_limit}")
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        
        total_count = 0
        projects = []
        today = datetime.now().date()  # 获取当日日期（仅日期部分）
        
        # 性能优化：批量查询所有已存在的project_id，避免每次单独查询数据库
        existing_project_ids = set(
            row[0] for row in self.db.query(TenderProject.project_id)
            .filter(TenderProject.project_id.isnot(None))
            .all()
        )
        processed_project_ids = set(existing_project_ids)  # 本地缓存已处理的project_id，避免重复处理
        log.info(f"已加载 {len(existing_project_ids)} 个已存在的项目ID到内存缓存")
        
        # 计算最早允许的发布日期（如果设置了days_before）
        # days_before表示爬取最近N天内的文件（从今天往前N天）
        earliest_date = None
        if self.days_before is not None and self.days_before > 0:
            from datetime import timedelta
            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")

        session = requests.Session()  # 创建一个持久化的会话对象，提高连接效率
        session.headers.update(self.headers)
        session.cookies.update(self.cookies)
        
        # 遍历分类：政府类 -> 非政府类
        for category in self.category_codes:
            # 检查是否已达到配额
            if total_count >= self.daily_limit:
                log.info(f"已达到爬取配额（{self.daily_limit}），停止爬取")
                break
            
            code = category["code"]
            name = category["name"]
            category_count = 0
            is_gov = name == "政府类"  # 根据分类名称判断是否为政府类

            log.info(f"开始爬取[{name}]分类（{code}）")

            # 政府类：依次爬取每个区域的当日文件
            if is_gov:
                log.info(f"[{name}]依次爬取各区域当日文件")
                
                for district_code, district_name in self.district_codes.items():
                    # 检查是否已达到配额
                    if total_count >= self.daily_limit:
                        log.info(f"已达到爬取配额（{self.daily_limit}），停止爬取")
                        break
                        
                    district_count = 0
                    page_no = 1
                    found_non_today = False  # 标记是否遇到非当日项目

                    log.info(f"  开始爬取区域: {district_name}（{district_code}）的当日文件")

                    # 爬取该区域的所有当日文件，直到遇到非当日项目或达到配额
                    while page_no <= SPIDER_CONFIG["zhejiang_max_pages"] and not found_non_today and total_count < self.daily_limit:
                        # 反爬控制
                        if page_no > 1:  # 第一页不等待，提高效率
                            time.sleep(SPIDER_CONFIG["anti_crawl"]["request_interval"])

                        # 获取页面数据（带区域参数和分类类型）
                        log.debug(f"[{name}-{district_name}]正在请求第{page_no}页当日数据")
                        result = self._fetch_page(session, code, page_no, district_code, is_gov)
                        
                        # 检查响应是否有效
                        if not result:
                            log.warning(f"[{name}-{district_name}]第{page_no}页请求失败，停止爬取该区域")
                            break
                        
                        # 检查响应结构
                        if not isinstance(result, dict):
                            log.warning(f"[{name}-{district_name}]第{page_no}页响应格式错误，类型={type(result).__name__}")
                            break
                        
                        if not result.get('result') or not result['result'].get('data'):
                            log.warning(f"[{name}-{district_name}]第{page_no}页无有效数据，停止爬取该区域")
                            log.debug(f"响应结构: result字段存在={bool(result.get('result'))}, data字段存在={bool(result.get('result', {}).get('data'))}")
                            break
                        
                        # 获取数据列表
                        data_obj = result['result']['data']
                        if not isinstance(data_obj, dict):
                            log.warning(f"[{name}-{district_name}]第{page_no}页data字段格式错误，类型={type(data_obj).__name__}")
                            break
                        
                        items = data_obj.get('data', [])
                        if not items:
                            log.warning(f"[{name}-{district_name}]第{page_no}页无项目数据，停止爬取该区域")
                            break
                        
                        log.debug(f"[{name}-{district_name}]第{page_no}页获取到{len(items)}个项目")

                        # 处理项目数据
                        for item in items:
                            if total_count >= self.daily_limit:
                                break

                            project_id = item.get("articleId")
                            
                            # 增强project_id验证
                            if not project_id:
                                log.warning(f"[{name}-{district_name}]发现无project_id的项目，跳过处理")
                                continue
                            
                            # 提取发布时间
                            publish_date, publish_date_source = self._extract_publish_date(item, name, district_name)
                            
                            # 如果没有发布时间，跳过该项目（不使用当前时间作为后备）
                            if publish_date is None:
                                log.warning(
                                    f"[{name}-{district_name}]跳过无发布时间的项目: {item.get('title', '未命名项目')[:50]}"
                                )
                                continue
                            
                            # 解析发布时间：publishDate是13位毫秒时间戳，去掉后3位得到10位秒级时间戳
                            project_date = None
                            publish_time = None
                            try:
                                # 统一处理：将publishDate转换为整数，然后去掉后3位
                                if isinstance(publish_date, (int, float)):
                                    timestamp_ms = int(publish_date)
                                elif isinstance(publish_date, str) and publish_date.strip() and publish_date.strip().isdigit():
                                    timestamp_ms = int(publish_date.strip())
                                else:
                                    log.error(
                                        f"[{name}-{district_name}]❌ publishDate格式错误: {publish_date} "
                                        f"(类型: {type(publish_date).__name__})，跳过该项目"
                                    )
                                    continue
                                
                                # 去掉后3位，转换为10位秒级时间戳
                                timestamp = timestamp_ms // 1000
                                publish_time = datetime.fromtimestamp(timestamp)
                                project_date = publish_time.date()
                                
                                log.debug(
                                    f"[{name}-{district_name}]时间戳转换: "
                                    f"{timestamp_ms} -> {timestamp}, "
                                    f"发布时间={publish_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                
                                # 如果设置了时间间隔限制
                                if self.days_before is not None:
                                    # 爬取最近N天内的文件：earliest_date <= project_date <= today
                                    # 如果项目日期早于最早允许日期（太旧），停止该区域爬取
                                    if project_date < earliest_date:
                                        log.info(f"[{name}-{district_name}]发现项目日期（{project_date}）早于时间范围（{earliest_date}），停止该区域爬取")
                                        found_non_today = True
                                        break
                                    # 如果项目日期晚于今天（未来日期，不应该存在），跳过
                                    elif project_date > today:
                                        log.debug(f"[{name}-{district_name}]发现未来日期项目（{project_date}），跳过")
                                        continue
                                else:
                                    # 未设置时间间隔时，只爬取当日文件
                                    # 如果项目日期不是当日，标记并跳过
                                    if project_date < today:
                                        log.info(f"[{name}-{district_name}]发现非当日项目（{project_date}），停止该区域当日爬取")
                                        found_non_today = True
                                        break
                            except (ValueError, OverflowError) as e:
                                log.warning(f"[{name}-{district_name}]项目日期格式错误: {publish_date}, 错误: {str(e)}，跳过该项目")
                                continue
                            
                            # 如果发布时间解析失败，跳过该项目
                            if not publish_time:
                                log.warning(f"[{name}-{district_name}]无法解析发布时间: {publish_date}，跳过该项目")
                                continue
                            
                            # 性能优化：只检查本地缓存，已批量加载所有已存在的project_id
                            if project_id in processed_project_ids:
                                log.debug(f"[{name}-{district_name}]项目已存在，跳过处理: {item.get('title', '未命名项目')}")
                                continue
                            
                            # 添加到本地已处理集合
                            processed_project_ids.add(project_id)
                            
                            # 获取区域名称（优先使用API返回的districtName，根据aaaa.py）
                            api_district_name = item.get("districtName")
                            if api_district_name:
                                region_name = api_district_name
                            else:
                                # 如果没有districtName，使用district_codes映射（兼容旧数据）
                                region_name = district_name
                            
                            # 保存原始时间戳（毫秒）
                            publish_timestamp = timestamp_ms
                            
                            project_data = {
                                "project_name": item.get("title", ""),
                                "site_name": f"浙江省政府采购网-{region_name}",
                                "publish_time": publish_time,  # 使用从API时间戳转换的发布时间
                                "publish_timestamp": publish_timestamp,  # 保存原始时间戳（毫秒）
                                "download_url": f"{self.BASE_URL}/site/detail?parentId=600007&articleId={project_id}",
                                "project_id": project_id,
                                "region": region_name,  # 使用API返回的districtName
                                "status": ProjectStatus.DOWNLOADED  # 使用枚举类型确保数据一致性
                            }
                            
                            # 下载文件
                            file_path, file_format = self._download_document(project_id, project_data["project_name"], session)
                            if file_path:
                                project_data["file_path"] = file_path
                                project_data["file_format"] = file_format

                            try:
                                # 保存项目
                                saved_project = save_project(self.db, project_data)
                                projects.append(saved_project)
                                district_count += 1
                                category_count += 1
                                total_count += 1
                                self.crawled_count += 1
                                log.debug(
                                    f"已爬取[{name}-{district_name}]当日项目: {project_data['project_name']}（总进度: {total_count}/{self.daily_limit}）")
                            except Exception as e:
                                log.error(f"保存项目失败[{project_id}]: {str(e)}。项目已标记为已处理，不会重复爬取。")
                                # 不从这里移除，保持已处理状态，避免无限循环
                                # 项目已经在 processed_project_ids 中，即使保存失败也不移除
                                pass

                        page_no += 1

                    log.info(f"  [{name}-{district_name}]区域当日文件爬取完成，实际获取: {district_count}个")
                
                # 政府类所有区域爬取完毕
                log.info(f"[{name}]所有区域当日文件爬取完成，共获取: {category_count}个")
            
            # 非政府类：依次爬取每个区域的当日文件（与政府类逻辑一致）
            else:
                log.info(f"[{name}]依次爬取各区域当日文件")
                
                for district_code, district_name in self.district_codes.items():
                    # 检查是否已达到配额
                    if total_count >= self.daily_limit:
                        log.info(f"已达到爬取配额（{self.daily_limit}），停止爬取")
                        break
                        
                    district_count = 0
                    page_no = 1
                    found_non_today = False  # 标记是否遇到非当日项目

                    log.info(f"  开始爬取区域: {district_name}（{district_code}）的当日文件")

                    # 爬取该区域的所有当日文件，直到遇到非当日项目或达到配额
                    while page_no <= SPIDER_CONFIG["zhejiang_max_pages"] and not found_non_today and total_count < self.daily_limit:
                        # 反爬控制
                        if page_no > 1:  # 第一页不等待，提高效率
                            time.sleep(SPIDER_CONFIG["anti_crawl"]["request_interval"])

                        # 获取页面数据（带区域参数和分类类型）
                        log.debug(f"[{name}-{district_name}]正在请求第{page_no}页当日数据")
                        result = self._fetch_page(session, code, page_no, district_code, is_gov)
                        
                        # 检查响应是否有效
                        if not result:
                            log.warning(f"[{name}-{district_name}]第{page_no}页请求失败，停止爬取该区域")
                            break
                        
                        # 检查响应结构
                        if not isinstance(result, dict):
                            log.warning(f"[{name}-{district_name}]第{page_no}页响应格式错误，类型={type(result).__name__}")
                            break
                        
                        if not result.get('result') or not result['result'].get('data'):
                            log.warning(f"[{name}-{district_name}]第{page_no}页无有效数据，停止爬取该区域")
                            log.debug(f"响应结构: result字段存在={bool(result.get('result'))}, data字段存在={bool(result.get('result', {}).get('data'))}")
                            break
                        
                        # 获取数据列表
                        data_obj = result['result']['data']
                        if not isinstance(data_obj, dict):
                            log.warning(f"[{name}-{district_name}]第{page_no}页data字段格式错误，类型={type(data_obj).__name__}")
                            break
                        
                        items = data_obj.get('data', [])
                        if not items:
                            log.warning(f"[{name}-{district_name}]第{page_no}页无项目数据，停止爬取该区域")
                            break
                        
                        log.debug(f"[{name}-{district_name}]第{page_no}页获取到{len(items)}个项目")

                        # 处理项目数据
                        for item in items:
                            if total_count >= self.daily_limit:
                                break

                            project_id = item.get("articleId")
                            
                            # 增强project_id验证
                            if not project_id:
                                log.warning(f"[{name}-{district_name}]发现无project_id的项目，跳过处理")
                                continue
                            
                            # 提取发布时间
                            publish_date, publish_date_source = self._extract_publish_date(item, name, district_name)
                            
                            # 如果没有发布时间，跳过该项目（不使用当前时间作为后备）
                            if publish_date is None:
                                log.warning(
                                    f"[{name}-{district_name}]跳过无发布时间的项目: {item.get('title', '未命名项目')[:50]}"
                                )
                                continue
                            
                            # 解析发布时间：publishDate是13位毫秒时间戳，去掉后3位得到10位秒级时间戳
                            project_date = None
                            publish_time = None
                            try:
                                # 统一处理：将publishDate转换为整数，然后去掉后3位
                                if isinstance(publish_date, (int, float)):
                                    timestamp_ms = int(publish_date)
                                elif isinstance(publish_date, str) and publish_date.strip() and publish_date.strip().isdigit():
                                    timestamp_ms = int(publish_date.strip())
                                else:
                                    log.error(
                                        f"[{name}-{district_name}]❌ publishDate格式错误: {publish_date} "
                                        f"(类型: {type(publish_date).__name__})，跳过该项目"
                                    )
                                    continue
                                
                                # 去掉后3位，转换为10位秒级时间戳
                                timestamp = timestamp_ms // 1000
                                publish_time = datetime.fromtimestamp(timestamp)
                                project_date = publish_time.date()
                                
                                log.debug(
                                    f"[{name}-{district_name}]时间戳转换: "
                                    f"{timestamp_ms} -> {timestamp}, "
                                    f"发布时间={publish_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                
                                # 如果设置了时间间隔限制
                                if self.days_before is not None:
                                    # 爬取最近N天内的文件：earliest_date <= project_date <= today
                                    # 如果项目日期早于最早允许日期（太旧），停止该区域爬取
                                    if project_date < earliest_date:
                                        log.info(f"[{name}-{district_name}]发现项目日期（{project_date}）早于时间范围（{earliest_date}），停止该区域爬取")
                                        found_non_today = True
                                        break
                                    # 如果项目日期晚于今天（未来日期，不应该存在），跳过
                                    elif project_date > today:
                                        log.debug(f"[{name}-{district_name}]发现未来日期项目（{project_date}），跳过")
                                        continue
                                else:
                                    # 未设置时间间隔时，只爬取当日文件
                                    # 如果项目日期不是当日，标记并跳过
                                    if project_date < today:
                                        log.info(f"[{name}-{district_name}]发现非当日项目（{project_date}），停止该区域当日爬取")
                                        found_non_today = True
                                        break
                            except (ValueError, OverflowError) as e:
                                log.warning(f"[{name}-{district_name}]项目日期格式错误: {publish_date}, 错误: {str(e)}，跳过该项目")
                                continue
                            
                            # 如果发布时间解析失败，跳过该项目
                            if not publish_time:
                                log.warning(f"[{name}-{district_name}]无法解析发布时间: {publish_date}，跳过该项目")
                                continue
                            
                            # 性能优化：只检查本地缓存，已批量加载所有已存在的project_id
                            if project_id in processed_project_ids:
                                log.debug(f"[{name}-{district_name}]项目已存在，跳过处理: {item.get('title', '未命名项目')}")
                                continue
                            
                            # 添加到本地已处理集合
                            processed_project_ids.add(project_id)
                            
                            # 获取区域名称（优先使用API返回的districtName，根据aaaa.py）
                            api_district_name = item.get("districtName")
                            if api_district_name:
                                region_name = api_district_name
                            else:
                                # 如果没有districtName，使用district_codes映射（兼容旧数据）
                                region_name = district_name
                            
                            # 保存原始时间戳（毫秒）
                            publish_timestamp = timestamp_ms
                            
                            project_data = {
                                "project_name": item.get("title", ""),
                                "site_name": f"浙江省政府采购网-{region_name}",
                                "publish_time": publish_time,  # 使用从API时间戳转换的发布时间
                                "publish_timestamp": publish_timestamp,  # 保存原始时间戳（毫秒）
                                "download_url": f"{self.BASE_URL}/site/detail?parentId=600007&articleId={project_id}",
                                "project_id": project_id,
                                "region": region_name,  # 使用API返回的districtName
                                "status": ProjectStatus.DOWNLOADED  # 使用枚举类型确保数据一致性
                            }
                            
                            # 下载文件
                            file_path, file_format = self._download_document(project_id, project_data["project_name"], session)
                            if file_path:
                                project_data["file_path"] = file_path
                                project_data["file_format"] = file_format

                            try:
                                # 保存项目
                                saved_project = save_project(self.db, project_data)
                                projects.append(saved_project)
                                district_count += 1
                                category_count += 1
                                total_count += 1
                                self.crawled_count += 1
                                log.debug(
                                    f"已爬取[{name}-{district_name}]当日项目: {project_data['project_name']}（总进度: {total_count}/{self.daily_limit}）")
                            except Exception as e:
                                log.error(f"保存项目失败[{project_id}]: {str(e)}。项目已标记为已处理，不会重复爬取。")
                                # 不从这里移除，保持已处理状态，避免无限循环
                                # 项目已经在 processed_project_ids 中，即使保存失败也不移除
                                pass

                        page_no += 1

                    log.info(f"  [{name}-{district_name}]区域当日文件爬取完成，实际获取: {district_count}个")
                
                # 非政府类所有区域爬取完毕
                log.info(f"[{name}]所有区域当日文件爬取完成，共获取: {category_count}个")

            log.info(f"[{name}]分类爬取完成，实际获取: {category_count}个")

        # 关闭会话和数据库连接
        session.close()
        self.db.close()
        log.info(f"浙江省招标网爬取完成，总获取: {total_count}个项目")
        # 确保crawled_count与total_count一致
        self.crawled_count = total_count
        return projects


def run_all_spiders(days_before=None, enabled_platforms=None):
    """运行所有爬虫（保持向后兼容）
    
    Args:
        days_before: 时间间隔，爬取最近N天内的文件（如10表示爬取最近10天内的文件，从今天往前10天），None表示只爬取当日文件
        enabled_platforms: 启用的平台列表（None表示全部启用）
    
    Returns:
        list: 所有爬虫返回的项目列表（合并后）
    """
    # 使用新的 SpiderManager 统一管理
    return SpiderManager.run_all_spiders(days_before=days_before, enabled_platforms=enabled_platforms)


# 自动注册浙江省爬虫
SpiderManager.register(ZheJiangTenderSpider)