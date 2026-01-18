"""宁波市招标平台请求处理函数

封装了可执行的HTTP请求函数
"""

import os
import requests
import time
from typing import Optional, Dict, Any
from urllib.parse import quote
from utils.log import log
from spider.platforms.ningbo.config import (
    API_LIST_URL, API_FILE_URL, API_DOWNLOAD_BASE_URL,
    HEADERS_LIST, HEADERS_DOWNLOAD, COOKIES, get_access_token
)


def get_doc_list(session: requests.Session, page_index: int = 1, page_size: int = 10,
                 headers: Optional[Dict] = None, timeout: int = 15, retry_times: int = 3) -> Optional[Dict]:
    """
    获取项目列表
    
    Args:
        session: requests.Session 对象
        page_index: 页码（从1开始）
        page_size: 每页数量
        headers: 请求头（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        包含项目列表的字典，格式：{"data": {"total": ..., "rows": [...]}, "code": 1}
        失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_LIST.copy()
            
            # 准备请求参数
            params = {
                'pageIndex': str(page_index),
                'pageSize': str(page_size),
                '_v': str(int(time.time() * 1000)),
            }
            
            # 执行请求
            response = session.get(
                API_LIST_URL,
                headers=request_headers,
                params=params,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 解析JSON响应
            result = response.json()
            
            # 检查响应结构
            if isinstance(result, dict) and result.get("code") == 1 and "data" in result:
                return result
            else:
                error_msg = result.get("msg", "未知错误")
                error_code = result.get("code", 0)
                
                # 如果是"请先登录"错误，尝试重新获取 access_token
                if error_code == -1 and "请先登录" in error_msg:
                    log.warning(f"检测到登录失效（code={error_code}, msg={error_msg}），尝试重新获取 access_token")
                    # 重新获取 access_token
                    new_access_token = get_access_token()
                    if new_access_token:
                        # 更新请求头中的 access_token
                        request_headers['access_token'] = new_access_token
                        # 更新 session 的 headers
                        session.headers.update({'access_token': new_access_token})
                        log.info(f"成功更新 access_token（长度: {len(new_access_token)}），将重试请求")
                        if attempt < retry_times:
                            time.sleep(1)  # 短暂等待后重试
                            continue
                    else:
                        log.error("重新获取 access_token 失败")
                        if attempt < retry_times:
                            time.sleep(2 * (attempt + 1))
                            continue
                        return None
                
                log.warning(f"列表响应格式异常或业务错误: code={error_code}, msg={error_msg}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"列表请求超时（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"列表请求超时，已达最大重试次数")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"列表连接错误（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"列表连接错误，已达最大重试次数")
                return None
                
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"列表请求异常（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"列表请求异常，已达最大重试次数: {str(e)}")
                return None
    
    return None


def get_file_url(session: requests.Session, prj_id: str,
                 headers: Optional[Dict] = None, timeout: int = 15, retry_times: int = 3) -> Optional[str]:
    """
    获取文件下载URL
    
    Args:
        session: requests.Session 对象
        prj_id: 项目ID
        headers: 请求头（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        文件URL（FileUrl），失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_LIST.copy()
            
            # 准备请求参数
            params = {
                'TypeId': '020101,030101',  # 文件类型ID
                'SectId': '',
                'PrjId': prj_id,
                'isPub': '1',
                'pageIndex': '1',
                'pageSize': '10',
                '_v': str(int(time.time() * 1000)),
            }
            
            # 执行请求
            response = session.get(
                API_FILE_URL,
                headers=request_headers,
                params=params,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 解析JSON响应
            result = response.json()
            
            # 检查响应结构
            if isinstance(result, dict) and result.get("code") == 1 and "data" in result:
                data = result.get("data", {})
                rows = data.get("rows", [])
                
                if rows and len(rows) > 0:
                    # 取第一个文件的URL
                    file_url = rows[0].get("FileUrl")
                    if file_url:
                        return file_url
                    else:
                        log.warning(f"项目 {prj_id} 的文件列表中没有找到FileUrl")
                else:
                    log.warning(f"项目 {prj_id} 的文件列表为空")
                
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            else:
                error_msg = result.get("msg", "未知错误")
                error_code = result.get("code", 0)
                
                # 如果是"请先登录"错误，尝试重新获取 access_token
                if error_code == -1 and "请先登录" in error_msg:
                    log.warning(f"检测到登录失效（code={error_code}, msg={error_msg}），尝试重新获取 access_token")
                    # 重新获取 access_token
                    new_access_token = get_access_token()
                    if new_access_token:
                        # 更新请求头中的 access_token
                        request_headers['access_token'] = new_access_token
                        # 更新 session 的 headers
                        session.headers.update({'access_token': new_access_token})
                        log.info(f"成功更新 access_token（长度: {len(new_access_token)}），将重试请求")
                        if attempt < retry_times:
                            time.sleep(1)  # 短暂等待后重试
                            continue
                    else:
                        log.error("重新获取 access_token 失败")
                        if attempt < retry_times:
                            time.sleep(2 * (attempt + 1))
                            continue
                        return None
                
                log.warning(f"文件URL响应格式异常或业务错误: code={error_code}, msg={error_msg}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"文件URL请求超时（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件URL请求超时，已达最大重试次数")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"文件URL连接错误（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件URL连接错误，已达最大重试次数")
                return None
                
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"文件URL请求异常（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"文件URL请求异常，已达最大重试次数: {str(e)}")
                return None
    
    return None


def download_file(session: requests.Session, file_url: str, save_path: str,
                  headers: Optional[Dict] = None, timeout: int = 120, retry_times: int = 3) -> bool:
    """
    下载文件
    
    Args:
        session: requests.Session 对象
        file_url: 文件URL（FileUrl，相对路径，如 /MyUpfiles/2026/01/16/xxx.pdf）
        save_path: 保存路径
        headers: 请求头（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        成功返回 True，失败返回 False
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
            
            # 构建完整下载URL
            # file_url 已经是相对路径，直接拼接
            # 需要对 file_url 中的中文进行URL编码
            # 例如: /MyUpfiles/2026/01/16/xxx_文件名.pdf -> /MyUpfiles/2026/01/16/xxx_%E6%96%87%E4%BB%B6%E5%90%8D.pdf
            # 但是 file_url 的路径部分不需要编码，只有文件名部分需要编码
            # 简单做法：对整个 file_url 进行编码处理
            encoded_file_url = quote(file_url, safe='/')
            
            download_url = f"{API_DOWNLOAD_BASE_URL}{encoded_file_url}"
            
            # 准备请求参数
            params = {
                'v': str(int(time.time() * 1000)),
            }
            
            # 执行请求
            response = session.get(
                download_url,
                headers=request_headers,
                params=params,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 检查响应内容
            content_type = response.headers.get("Content-Type", "").lower()
            content = response.content
            
            # 判断是否为PDF文件或其他文档文件的多种方式：
            # 1. 检查Content-Type
            # 2. 检查文件内容开头（PDF文件以 %PDF 开头，DOC文件可能以其他开头）
            # 3. 检查文件大小（文档文件通常不会太小）
            is_valid_file = (
                "application/pdf" in content_type or 
                "application/octet-stream" in content_type or
                "application/msword" in content_type or
                "application/vnd.openxmlformats-officedocument" in content_type or
                (len(content) > 10 and content[:4] == b'%PDF') or
                (len(content) > 10 and content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')  # DOC文件标识
            )
            
            if is_valid_file:
                # 如果文件太小，可能是错误页面
                if len(content) < 1000:
                    error_text = content[:500].decode('utf-8', errors='ignore') if content else ""
                    log.warning(f"文件下载失败，文件太小（{len(content)}字节），可能是错误响应: {error_text[:200]}")
                    if attempt < retry_times:
                        time.sleep(3 * (attempt + 1))
                        continue
                    return False
                
                # 保存文件
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(content)
                
                file_size_kb = len(content) / 1024
                log.info(f"文件下载成功: {save_path} (大小: {file_size_kb:.2f} KB)")
                return True
            else:
                # 可能是验证码错误或其他错误
                # 尝试解码为文本查看错误信息
                try:
                    error_text = content[:500].decode('utf-8', errors='ignore') if content else ""
                except:
                    error_text = f"二进制内容，长度: {len(content)}字节"
                
                log.warning(f"文件下载失败，响应类型: {content_type or '(空)'}, 内容: {error_text[:200]}")
                if attempt < retry_times:
                    time.sleep(3 * (attempt + 1))
                    continue
                return False
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"文件下载超时（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载超时，已达最大重试次数")
                return False
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 10 * (attempt + 1)
                log.warning(f"文件下载连接错误（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载连接错误，已达最大重试次数")
                return False
                
        except Exception as e:
            if attempt < retry_times:
                wait_time = 3 * (attempt + 1)
                log.warning(f"文件下载异常（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载异常，已达最大重试次数: {str(e)}")
                return False
    
    return False
