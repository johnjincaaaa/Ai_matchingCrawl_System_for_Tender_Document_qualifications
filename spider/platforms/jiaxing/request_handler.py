"""嘉兴市招标平台请求处理函数

封装了可执行的HTTP请求函数
"""

import os
import requests
import time
import json
import re
import base64
from typing import Optional, Dict, Any, Tuple
from utils.log import log
from spider.platforms.jiaxing.config import (
    API_LIST_URL, API_DETAIL_URL, API_CAPTCHA_URL, API_DOWNLOAD_URL,
    HEADERS_LIST, HEADERS_DETAIL, COOKIES, BASE_URL, PLATFORM_CONFIG
)


def get_doc_list(session: requests.Session, page: int = 0, page_size: int = 10,
                 headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                 timeout: int = 15, retry_times: int = 3) -> Optional[Dict]:
    """
    获取项目列表
    
    Args:
        session: requests.Session 对象
        page: 页码（从0开始，0表示第一页，10表示第二页，以此类推）
        page_size: 每页数量
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        包含项目列表的字典，格式：{"result": {"records": [...], "totalcount": ...}}
        失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_LIST.copy()
            request_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 准备请求数据
            params_template = PLATFORM_CONFIG["list_params_template"].copy()
            params_template["pn"] = page
            params_template["rn"] = page_size
            
            # 将字典转换为JSON字符串
            data_str = json.dumps(params_template, ensure_ascii=False)
            data_bytes = data_str.encode('utf-8')
            
            # 执行请求
            response = session.post(
                API_LIST_URL,
                cookies=request_cookies,
                headers=request_headers,
                data=data_bytes,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 解析JSON响应
            result = response.json()
            
            # 检查响应结构
            if isinstance(result, dict) and "result" in result:
                return result
            else:
                log.warning(f"列表响应格式异常: {result}")
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


def get_doc_detail(session: requests.Session, detail_url: str,
                   headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                   timeout: int = 15, retry_times: int = 3) -> Optional[str]:
    """
    获取项目详情页HTML，并提取attachGuid
    
    Args:
        session: requests.Session 对象
        detail_url: 详情页URL（完整URL或相对路径）
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        attachGuid字符串，失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
            request_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 构建完整URL
            if not detail_url.startswith("http"):
                detail_url = BASE_URL + detail_url
            
            # 执行请求
            response = session.get(
                detail_url,
                cookies=request_cookies,
                headers=request_headers,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 从HTML中提取attachGuid
            html_content = response.text
            pattern = r'attachGuid=([0-9a-fA-F-]{36})'
            match = re.search(pattern, html_content)
            
            if match:
                attach_guid = match.group(1)
                log.debug(f"成功提取attachGuid: {attach_guid}")
                return attach_guid
            else:
                # 静默处理：找不到attachGuid的项目直接跳过，不显示警告
                log.debug(f"未找到attachGuid: {detail_url}，跳过该项目")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"详情页请求超时（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"详情页请求超时，已达最大重试次数")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"详情页连接错误（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"详情页连接错误，已达最大重试次数")
                return None
                
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"详情页请求异常（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"详情页请求异常，已达最大重试次数: {str(e)}")
                return None
    
    return None


def get_captcha(session: requests.Session,
                headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                timeout: int = 15, retry_times: int = 3) -> Optional[Tuple[str, str]]:
    """
    获取验证码（滑块验证码）
    
    Args:
        session: requests.Session 对象
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        (captcha_id, validate_code) 元组，失败返回 None
        注意：此函数只获取验证码图片，实际验证需要人工处理或第三方服务
    """
    # 注意：滑块验证码需要人工识别或使用第三方服务
    # 这里返回备用验证码（如果配置了的话）
    if PLATFORM_CONFIG.get("validate_code_fallback"):
        log.info("使用备用验证码（滑块验证码需要人工处理）")
        return None, PLATFORM_CONFIG["validate_code_fallback"]
    
    return None, None


def download_file(session: requests.Session, attach_guid: str, save_path: str,
                  validate_code: Optional[str] = None,
                  headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                  timeout: int = 120, retry_times: int = 3) -> bool:
    """
    下载文件
    
    Args:
        session: requests.Session 对象
        attach_guid: 附件GUID
        save_path: 保存路径
        validate_code: 验证码（可选，如果为None则尝试使用备用验证码）
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        成功返回 True，失败返回 False
    """
    for attempt in range(retry_times + 1):
        try:
            # 如果没有提供验证码，尝试获取或使用备用验证码
            if not validate_code:
                if PLATFORM_CONFIG.get("validate_code_fallback"):
                    validate_code = PLATFORM_CONFIG["validate_code_fallback"]
                    log.info(f"使用备用验证码下载文件")
                else:
                    log.error(f"缺少验证码，无法下载文件")
                    return False
            
            # 准备请求头
            request_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundarylVD2CYR0WocyThqX",
                "Origin": "https://hcl.jxcqgs.cn",
                "Pragma": "no-cache",
                "Referer": f"https://hcl.jxcqgs.cn/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid={attach_guid}&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"'
            }
            
            if headers:
                request_headers.update(headers)
            
            request_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 准备请求参数
            params = {
                "cmd": "getContent",
                "attachGuid": attach_guid,
                "appUrlFlag": "ztb001",
                "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
                "verificationCode": validate_code,
                "verificationGuid": validate_code,
            }
            
            # 准备请求体
            data = '------WebKitFormBoundarylVD2CYR0WocyThqX--\\r\\n'.encode('unicode_escape')
            
            # 执行请求
            response = session.post(
                API_DOWNLOAD_URL,
                headers=request_headers,
                cookies=request_cookies,
                params=params,
                data=data,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 检查响应内容
            content_type = response.headers.get("Content-Type", "").lower()
            content = response.content
            
            # 判断是否为PDF文件的多种方式：
            # 1. 检查Content-Type
            # 2. 检查文件内容开头（PDF文件以 %PDF 开头）
            # 3. 检查文件大小（PDF文件通常不会太小）
            is_pdf_by_content_type = "application/pdf" in content_type or "application/octet-stream" in content_type
            is_pdf_by_content = len(content) > 10 and content[:4] == b'%PDF'
            
            if is_pdf_by_content_type or is_pdf_by_content:
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
