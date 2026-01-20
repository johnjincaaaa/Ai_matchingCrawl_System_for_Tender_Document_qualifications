"""绍兴市阳光采购服务平台请求封装"""

import time
from typing import Dict, Optional

import requests
from utils.log import log
from spider.platforms.shaoxing.config import (
    API_LIST_URL,
    API_DOWNLOAD_URL,
    HEADERS_LIST,
    HEADERS_DOWNLOAD,
    COOKIES,
)


def get_bulletin_list(
    session: requests.Session,
    page_index: int = 1,
    page_size: int = 8,
    info_type_id: str = "D01",
    class_id: str = "21",
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[Dict]:
    """获取公告列表"""
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_LIST.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()

            payload = {
                "InfoTypeId": info_type_id,
                "classID": class_id,
                "pageIndex": page_index,
                "pageSize": page_size,
            }

            response = session.post(
                API_LIST_URL,
                headers=req_headers,
                cookies=req_cookies,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"列表请求超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("列表请求失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"列表请求异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"列表请求异常，已达最大重试次数: {str(e)}")
                return None
    return None


def download_file(
    session: requests.Session,
    bulletin_id: str,
    save_path: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 120,
    retry_times: int = 3,
) -> Optional[str]:
    """下载公告附件，返回文件扩展名"""
    download_url = f"{API_DOWNLOAD_URL}/{bulletin_id}"

    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()

            response = session.get(
                download_url,
                headers=req_headers,
                cookies=req_cookies,
                timeout=timeout,
                stream=True,
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            disposition = response.headers.get("Content-Disposition", "")
            file_ext = "pdf"
            if "pdf" in content_type:
                file_ext = "pdf"
            elif "zip" in content_type:
                file_ext = "zip"
            elif "word" in content_type or "msword" in content_type:
                file_ext = "doc"
            elif "octet-stream" in content_type and ".rar" in disposition.lower():
                file_ext = "rar"

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            log.info(f"文件下载成功: {save_path}")
            return file_ext
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"文件下载超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("文件下载失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"文件下载异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"文件下载异常，已达最大重试次数: {str(e)}")
                return None
    return None

