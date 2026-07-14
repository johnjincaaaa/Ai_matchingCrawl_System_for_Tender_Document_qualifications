"""湖州市招标平台请求处理函数

基于 HAR 逆向的接口链条（见 spider/crawl_tests/湖州市/hzlscgfw_downloader.py）：
列表 -> 详情(附件) -> 验证码(服务端回传答案) -> 下载。全程无需 cookie / sid / 浏览器。
"""

import base64
import json
import os
import re
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import requests
from utils.log import log
from spider.platforms.huzhou.config import (
    BASE_URL, LIST_CHANNEL, API_VERIFICATION_CODE_URL, API_DOWNLOAD_URL,
    DOWNLOAD_BOUNDARY, HEADERS_LIST, HEADERS_DETAIL,
)

# 列表项：<div class="wb-data-infor"><a href=".." title="..">..</a></div><span class="wb-data-date">2026/01/19</span>
_LIST_RE = re.compile(
    r'<div class="wb-data-infor">\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*</div>'
    r'\s*<span class="wb-data-date">([^<]*)</span>',
    re.S,
)
# 附件：onclick="ztbfjyz('..downloadztbattach?attachGuid=A@B&appUrlFlag=ztb001&siteGuid=S','1','1')" .. title="招标文件正文.pdf"
_ATTACH_RE = re.compile(
    r"ztbfjyz\('([^']*downloadztbattach\?[^']+)'[^)]*\)\"[^>]*title=\"([^\"]*)\"",
    re.S,
)


def get_doc_list(session: requests.Session, page: int = 1,
                 headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                 timeout: int = 30, retry_times: int = 3) -> Optional[list]:
    """获取项目列表。返回 [{"title","url","date","region"}, ...]，失败返回 None。"""
    name = "sec.html" if page == 1 else f"{page}.html"
    url = f"{BASE_URL}{LIST_CHANNEL}/{name}"
    request_headers = (headers or HEADERS_LIST).copy()

    for attempt in range(retry_times + 1):
        try:
            r = session.get(url, headers=request_headers, timeout=timeout)
            r.raise_for_status()
            r.encoding = "utf-8"

            projects = []
            for href, title, date in _LIST_RE.findall(r.text):
                title = title.strip()
                detail_url = urljoin(BASE_URL, href.strip())
                region_match = re.search(r'\[([^\]]+)\]', title)
                region = region_match.group(1) if region_match else "湖州市"
                projects.append({
                    "title": re.sub(r'\[.*?\]', '', title).strip() or title,
                    "url": detail_url,
                    "date": date.strip(),
                    "region": region,
                })

            if projects:
                log.debug(f"第{page}页解析到 {len(projects)} 个项目")
                return projects
            log.warning(f"第{page}页未解析到项目")
            return []

        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"列表请求异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"列表请求失败，已达最大重试次数: {str(e)}")
                return None
    return None


def get_doc_detail(session: requests.Session, detail_url: str,
                   headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                   timeout: int = 30, retry_times: int = 3) -> Optional[List[Dict]]:
    """解析详情页，返回全部附件 [{"name","attach_guid","site_guid","app_url_flag"}, ...]。

    attach_guid 保留完整的 'A@B' 形式（下载时原样传入）。失败返回 None，无附件返回 []。
    """
    if not detail_url.startswith("http"):
        detail_url = urljoin(BASE_URL, detail_url)
    request_headers = (headers or HEADERS_DETAIL).copy()

    for attempt in range(retry_times + 1):
        try:
            r = session.get(detail_url, headers=request_headers, timeout=timeout)
            r.raise_for_status()
            r.encoding = "utf-8"

            attachments = []
            for link, title in _ATTACH_RE.findall(r.text):
                qs = dict(re.findall(r'[?&]([^=]+)=([^&\']+)', link))
                attachments.append({
                    "name": title.strip(),
                    "attach_guid": qs.get("attachGuid", ""),
                    "site_guid": qs.get("siteGuid", ""),
                    "app_url_flag": qs.get("appUrlFlag", "ztb001"),
                })
            return attachments

        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"详情页请求异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"详情页请求失败，已达最大重试次数: {str(e)}")
                return None
    return None


def get_verification_code(session: requests.Session, use_ocr: bool = False,
                          timeout: int = 30) -> Optional[Dict]:
    """获取验证码，返回 {"code","guid"}。

    默认解码服务端回传的 verificationCodeValue(base64) 直接拿答案；
    use_ocr=True 或解码失败时用 ddddocr 识别图片兜底。
    """
    data = {"params": json.dumps(
        {"width": "100", "height": "40", "codeNum": "4", "interferenceLine": "1", "codeGuid": ""})}
    try:
        r = session.post(API_VERIFICATION_CODE_URL, data=data, headers={
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/pageVerify.html",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }, timeout=timeout)
        r.raise_for_status()
        custom = (r.json() or {}).get("custom", {})
        guid = custom.get("verificationCodeGuid")
        img_b64 = custom.get("imgCode", "")

        code = None
        if not use_ocr:
            try:
                code = base64.b64decode(custom.get("verificationCodeValue", "")).decode("utf-8", "ignore").strip()
            except Exception:
                code = None
        if not code:
            code = _ocr(img_b64)
        if not code or not guid:
            log.warning("验证码获取失败（缺 code 或 guid）")
            return None
        return {"code": code, "guid": guid}
    except Exception as e:
        log.error(f"获取验证码失败: {str(e)}")
        return None


def _ocr(img_b64: str) -> Optional[str]:
    """ddddocr 识别 base64 验证码图片（兜底）。未安装则返回 None。"""
    try:
        import ddddocr
    except ImportError:
        log.error("ddddocr 未安装，无法兜底识别验证码: pip install ddddocr")
        return None
    try:
        if "," in img_b64:
            img_b64 = img_b64.split(",", 1)[1]
        img = base64.b64decode(img_b64)
        return ddddocr.DdddOcr(show_ad=False).classification(img).strip()
    except Exception as e:
        log.error(f"OCR 识别失败: {str(e)}")
        return None


def download_file(session: requests.Session, attach: Dict, save_path: str,
                  use_ocr: bool = False, max_retry: int = 3,
                  timeout: int = 60) -> Dict[str, Any]:
    """下载单个附件（自动领验证码并重试）。

    attach: get_doc_detail 返回的附件 dict（需含 attach_guid / site_guid / app_url_flag）。
    返回 {"success": bool, "error_msg": str}。
    """
    if not attach.get("attach_guid") or not attach.get("site_guid"):
        return {"success": False, "error_msg": "附件缺少 attach_guid/site_guid"}

    body = f"--{DOWNLOAD_BOUNDARY}--\r\n".encode()
    last_err = ""

    for attempt in range(1, max_retry + 1):
        vc = get_verification_code(session, use_ocr=use_ocr or attempt > 1)
        if not vc:
            last_err = f"领取验证码失败(第{attempt}次)"
            time.sleep(1)
            continue

        params = {
            "cmd": "getContent",
            "attachGuid": attach["attach_guid"],
            "appUrlFlag": attach.get("app_url_flag", "ztb001"),
            "siteGuid": attach["site_guid"],
            "verificationCode": vc["code"],
            "verificationGuid": vc["guid"],
        }
        try:
            r = session.post(API_DOWNLOAD_URL, params=params, data=body, headers={
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach",
                "Content-Type": f"multipart/form-data; boundary={DOWNLOAD_BOUNDARY}",
            }, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            last_err = f"下载请求异常(第{attempt}次): {str(e)}"
            log.warning(last_err)
            time.sleep(2)
            continue

        content = r.content
        ctype = r.headers.get("Content-Type", "").lower()
        is_pdf = content[:5] == b"%PDF-" or "application/pdf" in ctype or "octet-stream" in ctype

        # 验证码错误时服务端返回 text/html 的 JSON 提示
        if not is_pdf:
            text = content[:300].decode("utf-8", "ignore")
            last_err = f"验证码校验失败(第{attempt}次) code={vc['code']!r}: {text[:150]}"
            log.warning(last_err)
            time.sleep(1)
            continue

        if len(content) < 1000:
            last_err = f"文件过小（{len(content)}字节），疑似错误响应"
            log.warning(last_err)
            time.sleep(1)
            continue

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(content)
        log.info(f"文件下载成功: {save_path} ({len(content)/1024:.1f} KB)")
        return {"success": True, "error_msg": ""}

    return {"success": False, "error_msg": last_err or "下载失败"}
