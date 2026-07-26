"""浙江企业采购信息网（b.zhengcaiyun.cn）请求封装

站点位于阿里云 WAF（acw_sc__v2 JS 挑战）之后：
- 首次请求接口返回一个 HTML 挑战页（内含 <textarea id="renderData"> 与两段 <script>）；
- 需执行页面里的混淆 JS，它会调用 setCookie("acw_sc__v2", <value>) 得到 cookie；
- 带上该 cookie 重发同一请求即可拿到真实 JSON。

本模块用本机 Node 执行挑战页 JS（提供最小 DOM 桩捕获 setCookie 的值）解出 cookie，
运行时其余部分仍是纯 requests。solve 结果缓存在 session.cookies，仅在再次被挑战时重算。
"""

import json
import os
import re
import subprocess
import tempfile
import time
from typing import Dict, Optional

import requests
from utils.log import log
from spider.platforms.zcyxxw.config import (
    BASE_URL,
    API_LIST_URL,
    API_DETAIL_URL,
    LIST_CATEGORY_CODE,
    DETAIL_PARENT_ID,
    HEADERS_LIST,
    HEADERS_DETAIL,
    HEADERS_DOWNLOAD,
    COOKIES,
    USER_AGENT,
)

# 复用全平台统一的“无附件”哨兵
from spider.base_spider import NO_ATTACHMENT

# 挑战页特征：命中即说明被 WAF 拦截，需要解 acw_sc__v2
_CHALLENGE_MARKERS = ("renderData", "acw_sc__v2", "aliyunwaf")


def _looks_like_challenge(text: str) -> bool:
    if not text:
        return False
    head = text[:2000]
    return ("arg1=" in head or "renderData" in head) and "<textarea" in head


def solve_waf_cookie(challenge_html: str, timeout: int = 20) -> Optional[str]:
    """执行挑战页里的混淆 JS，返回 acw_sc__v2 cookie 值（失败返回 None）。

    做法：抽出 <textarea id="renderData"> 内容与两段 <script>，在 Node 里用最小 DOM
    桩运行；桩把 document.cookie 的写入捕获到变量，脚本调用 setCookie 后即可取到完整
    cookie（值含连字符，形如 1234abcd-长串16进制）。location.reload 被置为 noop。
    """
    try:
        m_render = re.search(
            r'<textarea id="renderData"[^>]*>(.*?)</textarea>', challenge_html, re.S
        )
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', challenge_html, re.S)
        if not m_render or len(scripts) < 2:
            log.warning("zcyxxw WAF：挑战页结构不符合预期，无法解算")
            return None
        render = m_render.group(1)
        js0, js1 = scripts[0], scripts[1]

        harness = (
            'var __cookie="";\n'
            'var navigator={userAgent:%s,platform:"Win32"};\n'
            'var location={href:"https://b.zhengcaiyun.cn/portal/category",'
            'protocol:"https:",host:"b.zhengcaiyun.cn",pathname:"/portal/category",'
            'search:"",hash:"",reload:function(){},replace:function(){},assign:function(){}};\n'
            'var document={getElementById:function(id){return {innerHTML: %s};},'
            'set cookie(v){__cookie=v;},get cookie(){return __cookie;},'
            'referrer:"",location:location,'
            'createElement:function(){return {style:{},setAttribute:function(){},appendChild:function(){}};},'
            'head:{appendChild:function(){}},body:{appendChild:function(){}},documentElement:{}};\n'
            'var window=this;window.document=document;window.location=location;window.navigator=navigator;\n'
            'try{%s}catch(e){}\n'
            'try{%s}catch(e){}\n'
            'var m=/acw_sc__v2=([0-9a-fA-F-]+)/.exec(__cookie);\n'
            'console.log("ACW="+(m?m[1]:"NONE"));\n'
        ) % (json.dumps(USER_AGENT), json.dumps(render), js0, js1)

        # 中文路径下 node 直接跑文件名会 MODULE_NOT_FOUND，改用 stdin 传入
        proc = subprocess.run(
            ["node"],
            input=harness,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        m = re.search(r"ACW=([0-9a-fA-F-]+)", proc.stdout or "")
        if m:
            return m.group(1)
        log.warning(f"zcyxxw WAF：Node 解算未产出 cookie（stderr: {(proc.stderr or '')[:200]}）")
        return None
    except FileNotFoundError:
        log.error("zcyxxw WAF：未找到 node，可执行文件缺失，无法解算 acw_sc__v2")
        return None
    except Exception as e:
        log.warning(f"zcyxxw WAF：解算异常：{str(e)}")
        return None


def _request_with_waf(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: Dict,
    json_body: Optional[Dict] = None,
    params: Optional[Dict] = None,
    timeout: int = 20,
    retry_times: int = 3,
) -> Optional[requests.Response]:
    """带 WAF 自动解算的请求：命中挑战页则解 cookie 后重发。"""
    for attempt in range(retry_times + 1):
        try:
            if method == "POST":
                resp = session.post(url, headers=headers, json=json_body, timeout=timeout)
            else:
                resp = session.get(url, headers=headers, params=params, timeout=timeout)

            # 命中 WAF 挑战：解 cookie 后立即重发一次
            if _looks_like_challenge(resp.text):
                acw = solve_waf_cookie(resp.text)
                if not acw:
                    log.warning(f"zcyxxw：WAF 挑战解算失败（第{attempt+1}次）")
                    time.sleep(2)
                    continue
                session.cookies.set("acw_sc__v2", acw, domain="b.zhengcaiyun.cn")
                if method == "POST":
                    resp = session.post(url, headers=headers, json=json_body, timeout=timeout)
                else:
                    resp = session.get(url, headers=headers, params=params, timeout=timeout)

            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"zcyxxw 请求超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("zcyxxw 请求失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"zcyxxw 请求异常（第{attempt+1}次），{wait}秒后重试：{str(e)}")
                time.sleep(wait)
            else:
                log.error(f"zcyxxw 请求异常，已达最大重试次数：{str(e)}")
                return None
    return None


def get_project_list(
    session: requests.Session,
    page: int = 1,
    page_size: int = 15,
    headers: Optional[Dict] = None,
    timeout: int = 20,
    retry_times: int = 3,
) -> Optional[Dict]:
    """获取「公开招标公告」列表。返回 API JSON（含 result.data.data[]），失败返回 None。"""
    req_headers = headers.copy() if headers else HEADERS_LIST.copy()
    payload = {
        "pageNo": page,
        "pageSize": page_size,
        "categoryCode": LIST_CATEGORY_CODE,
        "_t": int(time.time() * 1000),
    }
    resp = _request_with_waf(
        session, "POST", API_LIST_URL,
        headers=req_headers, json_body=payload, timeout=timeout, retry_times=retry_times,
    )
    if not resp:
        return None
    try:
        return resp.json()
    except Exception as e:
        log.error(f"zcyxxw 列表响应非 JSON：{str(e)}；前200字符：{resp.text[:200]}")
        return None


def get_doc_detail(
    session: requests.Session,
    article_id: str,
    headers: Optional[Dict] = None,
    timeout: int = 20,
    retry_times: int = 3,
) -> Optional[Dict]:
    """获取详情页数据（result.data，含 content 正文与 attachmentVO 附件）。失败返回 None。"""
    req_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
    params = {"articleId": article_id, "parentId": DETAIL_PARENT_ID, "timestamp": int(time.time() * 1000)}
    resp = _request_with_waf(
        session, "GET", API_DETAIL_URL,
        headers=req_headers, params=params, timeout=timeout, retry_times=retry_times,
    )
    if not resp:
        return None
    try:
        data = resp.json()
        return (data or {}).get("result", {}).get("data")
    except Exception as e:
        log.error(f"zcyxxw 详情响应非 JSON：{str(e)}；前200字符：{resp.text[:200]}")
        return None


def parse_attachments(detail_data: Dict) -> list:
    """从详情数据解析附件列表，返回 [{"url","name","fileId"}...]。无附件返回 []。"""
    if not detail_data:
        return []
    av = detail_data.get("attachmentVO")
    if not av or not isinstance(av, dict):
        return []
    domain = (av.get("domain") or "").rstrip("/")
    result = []
    for a in (av.get("attachments") or []):
        file_id = a.get("fileId")
        if not file_id:
            continue
        if a.get("isShow") is False:
            continue
        url = f"{domain}/{file_id.lstrip('/')}" if domain else file_id
        result.append({"url": url, "name": a.get("name") or "", "fileId": file_id})
    return result


def download_file(
    url: str,
    save_path: str,
    headers: Optional[Dict] = None,
    timeout: int = 120,
    retry_times: int = 3,
) -> Optional[str]:
    """下载附件（OSS 直链，无需 WAF/鉴权）。返回文件扩展名（不含点），失败返回 None。

    扩展名优先取 URL/fileId 中的后缀，其次 magic bytes 兜底。
    """
    req_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
    # OSS 直链为国内地址，不走系统/科学上网代理（避免本机代理未开时 ProxyError）
    dl_session = requests.Session()
    dl_session.trust_env = False
    for attempt in range(retry_times + 1):
        try:
            resp = dl_session.get(url, headers=req_headers, timeout=timeout, stream=True)
            resp.raise_for_status()
            content = resp.content

            # 1) 从 URL 路径取后缀（fileId 通常自带正确后缀，如 .doc/.docx/.pdf/.xlsx/.zip）
            file_ext = ""
            path = url.split("?", 1)[0].lower()
            m = re.search(r"\.([a-z0-9]{2,5})$", path)
            if m and m.group(1) in ("pdf", "doc", "docx", "xls", "xlsx", "zip", "rar", "ppt", "pptx"):
                file_ext = m.group(1)

            # 2) magic bytes 兜底/校正
            if not file_ext:
                if content[:4] == b"%PDF":
                    file_ext = "pdf"
                elif content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                    file_ext = "doc"  # OLE 复合文档
                elif content[:2] == b"PK":
                    file_ext = "docx" if b"word/" in content[:4000] else "zip"
                elif content[:4] == b"Rar!":
                    file_ext = "rar"
                else:
                    file_ext = "pdf"

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(content)

            size_kb = os.path.getsize(save_path) / 1024
            log.info(f"zcyxxw 文件下载成功：{save_path}（大小：{size_kb:.2f} KB，类型：{file_ext}）")
            return file_ext
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"zcyxxw 文件下载超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("zcyxxw 文件下载失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"zcyxxw 文件下载异常（第{attempt+1}次），{wait}秒后重试：{str(e)}")
                time.sleep(wait)
            else:
                log.error(f"zcyxxw 文件下载异常，已达最大重试次数：{str(e)}")
                return None
    return None


def extract_body_text(detail_data: Dict) -> Optional[str]:
    """从详情数据的 content（HTML）提取正文纯文本，用于无附件的纯正文公告。"""
    if not detail_data:
        return None
    html = detail_data.get("content")
    if not html:
        return None
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
        return text or None
    except Exception as e:
        log.warning(f"zcyxxw 正文提取失败：{str(e)}")
        return None
