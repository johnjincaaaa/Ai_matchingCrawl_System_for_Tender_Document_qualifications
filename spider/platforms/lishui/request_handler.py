"""丽水市平台请求处理函数"""

import os
import re
import time
from typing import Optional, Dict

import requests
from bs4 import BeautifulSoup

from utils.log import log
from spider.platforms.lishui.config import (
    BASE_URL,
    LIST_URL_TEMPLATE,
    API_DOWNLOAD_URL,
    HEADERS_LIST,
    HEADERS_DETAIL,
    HEADERS_DOWNLOAD,
    PLATFORM_CONFIG,
    COOKIES,
)


def get_doc_list(
    session: requests.Session,
    page: int = 1,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[list]:
    """获取项目列表（HTML解析）"""
    for attempt in range(retry_times + 1):
        try:
            request_headers = headers.copy() if headers else HEADERS_LIST.copy()
            request_cookies = cookies.copy() if cookies else COOKIES.copy()

            if page == 1:
                url = f"{LIST_URL_TEMPLATE}/sec.html"
            else:
                url = f"{LIST_URL_TEMPLATE}/{page}.html"

            resp = session.get(url, cookies=request_cookies, headers=request_headers, timeout=timeout)
            # 如果页面不存在（404），视为无更多数据，返回空列表以便上层停止
            if resp.status_code == 404:
                log.info(f"列表页不存在，可能已到末页：{url}")
                return []
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            projects = []

            list_items = soup.find_all("li", class_="wb-data-list")
            for item in list_items:
                try:
                    infor = item.find("div", class_="wb-data-infor")
                    link = infor.find("a") if infor else None
                    if not link:
                        continue

                    title = (link.get("title") or "").strip()
                    if not title:
                        title = link.get_text(strip=True)
                        title = re.sub(r"\[.*?\]", "", title).strip()

                    href = (link.get("href") or "").strip()
                    if not href:
                        continue
                    detail_url = href if href.startswith("http") else BASE_URL + href

                    date_elem = item.find("span", class_="wb-data-date")
                    date_str = date_elem.get_text(strip=True) if date_elem else ""

                    region_match = re.search(r"\[([^\]]+)\]", link.get_text())
                    region = region_match.group(1) if region_match else "丽水市"

                    projects.append({"title": title, "url": detail_url, "date": date_str, "region": region})
                except Exception:
                    continue

            return projects
        except Exception as e:
            if attempt < retry_times:
                time.sleep(2 * (attempt + 1))
                continue
            log.error(f"列表请求失败: {str(e)}")
            return None


def get_doc_detail(
    session: requests.Session,
    detail_url: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[str]:
    """获取详情页并提取 attachGuid（优先招标文件正文.pdf）"""
    for attempt in range(retry_times + 1):
        try:
            request_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
            request_cookies = cookies.copy() if cookies else COOKIES.copy()

            if not detail_url.startswith("http"):
                detail_url = BASE_URL + detail_url

            resp = session.get(detail_url, cookies=request_cookies, headers=request_headers, timeout=timeout)
            resp.raise_for_status()
            html = resp.text

            # 优先匹配 title="招标文件正文.pdf" 附近的 attachGuid
            pattern = r'attachGuid=([0-9a-fA-F-]{36})[^"\']{0,200}title="招标文件正文\.pdf"'
            m = re.search(pattern, html)
            if m:
                return m.group(1)

            # 退化：如果页面里只有一个 attachGuid，就用它
            all_guids = re.findall(r"attachGuid=([0-9a-fA-F-]{36})", html)
            all_guids = list(dict.fromkeys(all_guids))
            if len(all_guids) == 1:
                return all_guids[0]

            # 再退化：找包含“招标文件”的上下文
            for guid in all_guids:
                idx = html.find(guid)
                if idx == -1:
                    continue
                context = html[max(0, idx - 200) : min(len(html), idx + 200)]
                if "招标文件" in context:
                    return guid

            return None
        except Exception as e:
            if attempt < retry_times:
                time.sleep(2 * (attempt + 1))
                continue
            log.debug(f"详情页解析失败: {str(e)}")
            return None


def _build_download_cookies(sid: str, base_cookies: Optional[Dict]) -> Dict:
    """构造下载/验证码一致 cookies"""
    request_cookies = (base_cookies or {}).copy()
    request_cookies["sid"] = sid
    # 必要 oauth
    request_cookies["oauthClientId"] = COOKIES.get("oauthClientId", "demoClient")
    request_cookies["oauthPath"] = COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder")
    request_cookies["oauthLoginUrl"] = COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=")
    request_cookies["oauthLogoutUrl"] = COOKIES.get("oauthLogoutUrl", "")
    # demo token：有就带上
    for k in ("noOauthRefreshToken", "noOauthAccessToken", "_CSRFCOOKIE", "EPTOKEN"):
        v = COOKIES.get(k)
        if v:
            request_cookies[k] = v
    return request_cookies


def download_file(
    session: requests.Session,
    attach_guid: str,
    save_path: str,
    verification_code: str,
    verification_guid: str,
    sid: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 120,
    retry_times: int = 3,
) -> bool:
    """下载文件（PDF为主）"""
    for attempt in range(retry_times + 1):
        try:
            if not (verification_code and verification_guid and sid):
                log.error("缺少 sid/验证码/guid，无法下载")
                return False

            request_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
            request_cookies = _build_download_cookies(sid, cookies)

            params = {
                "cmd": "getContent",
                "attachGuid": attach_guid,
                "appUrlFlag": PLATFORM_CONFIG.get("download_app_url_flag", "ztb001"),
                "siteGuid": PLATFORM_CONFIG.get("download_site_guid", ""),
                "verificationCode": verification_code,
                "verificationGuid": verification_guid,
            }

            boundary = PLATFORM_CONFIG.get("download_boundary") or "----WebKitFormBoundaryXD323ilkjsRlOQc3"
            data = f"{boundary}--\\r\\n".encode("unicode_escape")

            resp = session.post(
                API_DOWNLOAD_URL,
                headers=request_headers,
                cookies=request_cookies,
                params=params,
                data=data,
                timeout=timeout,
            )
            resp.raise_for_status()

            content_type = (resp.headers.get("Content-Type") or "").lower()
            content = resp.content or b""
            is_pdf = content[:4] == b"%PDF" or "application/pdf" in content_type or "octet-stream" in content_type

            if is_pdf and len(content) > 1000:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)
                log.info(f"文件下载成功: {save_path} (大小: {len(content)/1024:.2f} KB)")
                return True

            # 可能是验证码错误
            error_text = content[:500].decode("utf-8", errors="ignore")
            if "验证码" in error_text or "validateVerificationCode" in error_text:
                log.warning(f"验证码验证失败（第{attempt+1}次），响应: {error_text[:200]}")
            else:
                log.warning(f"下载失败，content-type={content_type or '(空)'}，响应: {error_text[:200]}")

            if attempt < retry_times:
                time.sleep(3 * (attempt + 1))
                continue
            return False
        except Exception as e:
            if attempt < retry_times:
                time.sleep(3 * (attempt + 1))
                continue
            log.error(f"下载异常: {str(e)}")
            return False

