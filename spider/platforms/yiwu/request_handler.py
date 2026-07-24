"""义乌市阳光招标采购平台请求封装"""

import io
import json
import os
import time
import zipfile
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from utils.log import log
from spider.platforms.yiwu.config import (
    BASE_URL,
    API_LIST_URL,
    HEADERS_LIST,
    HEADERS_DETAIL,
    HEADERS_DOWNLOAD,
    COOKIES,
    DEFAULT_LIST_PARAMS,
)

# get_doc_detail 的专属返回值：页面成功打开但确实无附件（纯正文公告）。
# 统一复用 base_spider 的哨兵，保证全平台一致（区分"无附件"应抓正文排除、不重试）。
from spider.base_spider import NO_ATTACHMENT


def get_project_list(
    session: requests.Session,
    page: int = 1,
    page_size: int = 10,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    sdt: Optional[str] = None,
    edt: Optional[str] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[Dict]:
    """
    获取项目列表
    
    Args:
        session: requests.Session对象
        page: 页码（从1开始）
        page_size: 每页数量
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        dict: API返回的JSON数据，失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_LIST.copy()
            # demo文件中没有使用cookies，所以这里也不使用cookies
            # req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 构建请求参数
            # pn: 第一页为0，第二页为10，第三页为20，以此类推
            params = DEFAULT_LIST_PARAMS.copy()
            params["pn"] = (page - 1) * page_size
            params["rn"] = page_size
            
            # 如果提供了时间范围参数，则设置sdt和edt（否则保持为空字符串，与demo一致）
            # 注意：params中sdt和edt默认是空字符串，如果sdt/edt是None，则保持为空字符串
            if sdt is not None:
                params["sdt"] = sdt
            else:
                params["sdt"] = ""  # 确保是空字符串，不是None
            if edt is not None:
                params["edt"] = edt
            else:
                params["edt"] = ""  # 确保是空字符串，不是None
            
            # 将参数转换为JSON字符串（与demo文件完全一致：separators=(',', ':')）
            data = json.dumps(params, separators=(',', ':'))
            
            # 调试日志：记录请求参数
            log.debug(f"请求第{page}页数据: pn={params['pn']}, rn={params['rn']}, URL={API_LIST_URL}")
            log.debug(f"请求数据长度: {len(data)} 字节")
            log.debug(f"请求数据内容: {data[:300]}...")  # 记录前300字符
            
            # 与demo文件完全一致：直接使用requests.post（不使用session）
            # demo文件中使用的是 requests.post(url, headers=headers, data=data)
            response = requests.post(
                API_LIST_URL,
                headers=req_headers,
                data=data,
                timeout=timeout,
            )
            
            # 调试日志：记录响应内容（前500字符）
            log.debug(f"响应内容前500字符: {response.text[:500]}")
            response.raise_for_status()
            
            # 调试日志：记录响应状态
            log.debug(f"API响应状态: {response.status_code}, Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            result = response.json()
            # 调试日志：记录返回的数据结构
            if "result" in result:
                result_data = result.get("result", {})
                records_count = len(result_data.get("records", []))
                totalcount = result_data.get("totalcount", "unknown")
                log.debug(f"API返回数据: result键存在=True, totalcount={totalcount}, records数量={records_count}")
            else:
                log.warning(f"API返回数据缺少result键，返回的键: {list(result.keys())}")
                log.debug(f"API返回完整数据: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
            
            return result
            
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


def get_doc_detail(
    session: requests.Session,
    detail_url: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[str]:
    """
    获取详情页并解析下载链接
    
    Args:
        session: requests.Session对象
        detail_url: 详情页URL
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        str: 下载链接URL，失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            response = session.get(
                detail_url,
                headers=req_headers,
                cookies=req_cookies,
                timeout=timeout,
            )
            response.raise_for_status()
            
            # 解析HTML，查找下载链接
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找包含attachGuid的下载链接
            # 格式：<a class="sub-file-item file-docx " data-attachname="..." href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=...&appUrlFlag=ztb002&siteGuid=..." ...>
            download_link = None
            
            # 方法1：查找包含downloadZtbAttach.jspx的链接
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if 'downloadZtbAttach.jspx' in href:
                    download_link = href
                    break
            
            if not download_link:
                # 方法2：查找包含attachGuid的链接
                for link in links:
                    href = link.get('href', '')
                    if 'attachGuid' in href:
                        download_link = href
                        break
            
            if download_link:
                # 如果是相对路径，转换为绝对路径
                if download_link.startswith('/'):
                    download_url = urljoin(BASE_URL, download_link)
                elif download_link.startswith('http'):
                    download_url = download_link
                else:
                    download_url = urljoin(BASE_URL, '/' + download_link)

                log.debug(f"找到下载链接: {download_url}")
                return download_url
            else:
                # 页面成功打开但确实没有附件（如单一来源公示/中标候选公示/劳保采购等
                # 纯正文公告），这属于"本就无附件"，不是"请求失败"。返回专属标记以便上层
                # 正确区分：无附件 → 标记排除并抓正文；请求失败(None) → 保留重试。
                log.info(f"详情页无附件（纯正文公告）: {detail_url}")
                return NO_ATTACHMENT
                
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"详情页请求超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("详情页请求失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"详情页请求异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"详情页请求异常，已达最大重试次数: {str(e)}")
                return None
    return None


def get_detail_body_text(
    session: requests.Session,
    detail_url: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
) -> Optional[str]:
    """抓取详情页正文纯文本（用于无附件的纯正文公告，让AI仍能分析正文）。

    优先取 class 含 'article'/'content'/'detail' 的容器，取不到则退回整页文本。
    失败返回 None。
    """
    try:
        req_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
        req_cookies = cookies.copy() if cookies else COOKIES.copy()
        response = session.get(detail_url, headers=req_headers, cookies=req_cookies, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 优先在常见正文容器里找文本最长的一个
        candidates = []
        for kw in ('article-info', 'article', 'content', 'detail', 'xxnr'):
            for el in soup.find_all(class_=lambda c, k=kw: c and k in c):
                candidates.append(el.get_text(separator="\n", strip=True))
        body = max(candidates, key=len) if candidates else ""

        # 容器都取不到时退回整页
        if len(body) < 30:
            body = soup.get_text(separator="\n", strip=True)

        return body or None
    except Exception as e:
        log.warning(f"抓取详情页正文失败: {str(e)}")
        return None


def _sniff_zip_ext(content: bytes) -> str:
    """PK 开头的包(OOXML)按中央目录判断真实类型。

    义乌平台的 .docx 里 [Content_Types].xml / customXml / docProps 排在最前，
    `word/` 目录可能出现在 1000 字节之后，用「前N字节找 word/」会把 docx 误判成
    zip。这里解析整个 zip 的条目名来准确区分 docx/xlsx/pptx，解析失败才退回 zip。
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
        names = z.namelist()
        if any(n.startswith("word/") for n in names):
            return "docx"
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        if any(n.startswith("ppt/") for n in names):
            return "pptx"
    except Exception:
        pass
    return "zip"


def _detect_file_ext(download_url: str, content: bytes, content_type: str,
                     disposition: str) -> str:
    """综合 magic bytes / Content-Type / Content-Disposition / URL 判断扩展名。

    以文件内容(magic bytes)为最高优先级——义乌平台会把扩展名塞进 Content-Type
    (如 `.docx;charset=UTF-8`)且不带 Content-Disposition，仅靠 header 关键词匹配
    会漏判。返回不含点的扩展名字符串。
    """
    ct = (content_type or "").lower()
    disp = (disposition or "").lower()

    # 1) magic bytes 最可靠
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:2] == b"PK":
        return _sniff_zip_ext(content)
    if content[:4] == b"Rar!":
        return "rar"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # 旧版 OLE 复合文档：doc/xls/ppt，无法仅凭头部细分，取最常见的 doc
        return "doc"

    # 2) Content-Disposition / Content-Type / URL 里出现的扩展名字面量
    for src in (disp, ct, urlparse(download_url).path.lower()):
        for ext in ("docx", "xlsx", "pptx", "pdf", "doc", "xls", "ppt", "zip", "rar"):
            if f".{ext}" in src:
                return ext

    # 3) Content-Type 语义关键词
    if "pdf" in ct:
        return "pdf"
    if "wordprocessingml" in ct:
        return "docx"
    if "spreadsheetml" in ct:
        return "xlsx"
    if "word" in ct or "msword" in ct:
        return "doc"
    if "zip" in ct:
        return "zip"

    return "pdf"


def download_file(
    session: requests.Session,
    download_url: str,
    save_path: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 120,
    retry_times: int = 3,
) -> Optional[str]:
    """
    下载文件
    
    Args:
        session: requests.Session对象
        download_url: 下载链接URL
        save_path: 保存路径
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        str: 文件扩展名（如"pdf"、"docx"等），失败返回None
    """
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
            
            # 读取完整内容（OOXML 需要解析整个 zip 中央目录来准确判断类型）
            content = response.content
            content_type = response.headers.get("Content-Type", "")
            disposition = response.headers.get("Content-Disposition", "")

            # 综合判断文件类型（magic bytes 优先，其次 header/URL）
            file_ext = _detect_file_ext(download_url, content, content_type, disposition)

            # 保存文件
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(content)

            file_size_kb = os.path.getsize(save_path) / 1024
            log.info(f"文件下载成功: {save_path} (大小: {file_size_kb:.2f} KB, 类型: {file_ext})")
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
