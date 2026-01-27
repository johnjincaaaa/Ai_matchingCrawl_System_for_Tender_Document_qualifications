"""义乌市阳光招标采购平台请求封装"""

import json
import os
import time
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
                log.warning(f"未找到下载链接: {detail_url}")
                if attempt < retry_times:
                    continue
                return None
                
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
            
            # 判断文件类型
            content_type = response.headers.get("Content-Type", "").lower()
            disposition = response.headers.get("Content-Disposition", "")
            
            # 从Content-Disposition或URL中提取文件扩展名
            file_ext = "pdf"  # 默认扩展名
            
            # 方法1：从Content-Disposition中提取
            if disposition:
                if '.pdf' in disposition.lower():
                    file_ext = "pdf"
                elif '.docx' in disposition.lower() or '.doc' in disposition.lower():
                    file_ext = "docx" if '.docx' in disposition.lower() else "doc"
                elif '.zip' in disposition.lower():
                    file_ext = "zip"
                elif '.rar' in disposition.lower():
                    file_ext = "rar"
            
            # 方法2：从Content-Type中判断
            if "pdf" in content_type:
                file_ext = "pdf"
            elif "zip" in content_type:
                file_ext = "zip"
            elif "word" in content_type or "msword" in content_type:
                file_ext = "docx" if "wordprocessingml" in content_type else "doc"
            elif "octet-stream" in content_type:
                # 尝试从URL中提取扩展名
                parsed_url = urlparse(download_url)
                path = parsed_url.path.lower()
                if '.pdf' in path:
                    file_ext = "pdf"
                elif '.docx' in path:
                    file_ext = "docx"
                elif '.doc' in path:
                    file_ext = "doc"
                elif '.zip' in path:
                    file_ext = "zip"
                elif '.rar' in path:
                    file_ext = "rar"
            
            # 方法3：从文件内容判断（检查前几个字节）
            content = response.content[:10]
            if content.startswith(b'%PDF'):
                file_ext = "pdf"
            elif content.startswith(b'PK') and b'word/' in response.content[:1000]:
                file_ext = "docx"
            elif content.startswith(b'PK'):
                file_ext = "zip"
            
            # 保存文件
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
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
