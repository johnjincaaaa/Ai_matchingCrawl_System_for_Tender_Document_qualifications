"""湖州市招标平台请求处理函数

封装了可执行的HTTP请求函数
"""

import os
import requests
import time
import re
import base64
from typing import Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from utils.log import log
from spider.platforms.huzhou.config import (
    BASE_URL, LIST_URL_TEMPLATE, API_VERIFICATION_CODE_URL, API_DOWNLOAD_URL,
    HEADERS_LIST, HEADERS_DETAIL, HEADERS_CAPTCHA, HEADERS_DOWNLOAD, COOKIES, PLATFORM_CONFIG
)


def get_doc_list(session: requests.Session, page: int = 1,
                 headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                 timeout: int = 15, retry_times: int = 3) -> Optional[list]:
    """
    获取项目列表（HTML解析）
    
    Args:
        session: requests.Session 对象
        page: 页码（1表示第一页，2表示第二页，以此类推）
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        项目列表，格式：[{"title": "...", "url": "...", "date": "...", "region": "..."}, ...]
        失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_LIST.copy()
            request_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 构建URL：第一页是sec.html，第二页是2.html，以此类推
            if page == 1:
                url = f"{LIST_URL_TEMPLATE}/sec.html"
            else:
                url = f"{LIST_URL_TEMPLATE}/{page}.html"
            
            # 执行请求
            response = session.get(
                url,
                cookies=request_cookies,
                headers=request_headers,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            projects = []
            
            # 查找所有项目项
            list_items = soup.find_all('li', class_='wb-data-list')
            
            for item in list_items:
                try:
                    # 提取标题和URL
                    link_elem = item.find('div', class_='wb-data-infor').find('a')
                    if not link_elem:
                        continue
                    
                    title = link_elem.get('title', '').strip()
                    href = link_elem.get('href', '').strip()
                    
                    # 清理标题（移除HTML标签）
                    if not title:
                        title = link_elem.get_text(strip=True)
                        # 移除区域和状态标签
                        title = re.sub(r'\[.*?\]', '', title).strip()
                    
                    # 构建完整URL
                    if href and not href.startswith('http'):
                        detail_url = BASE_URL + href
                    else:
                        detail_url = href
                    
                    # 提取日期
                    date_elem = item.find('span', class_='wb-data-date')
                    date_str = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # 提取区域（从标题中提取，如[安吉县]）
                    region_match = re.search(r'\[([^\]]+)\]', link_elem.get_text())
                    region = region_match.group(1) if region_match else "湖州市"
                    
                    if title and detail_url:
                        projects.append({
                            "title": title,
                            "url": detail_url,
                            "date": date_str,
                            "region": region
                        })
                except Exception as e:
                    log.debug(f"解析项目项失败: {str(e)}")
                    continue
            
            if projects:
                log.debug(f"成功解析 {len(projects)} 个项目")
                return projects
            else:
                log.warning(f"第{page}页未找到项目")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return []
            
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
    获取项目详情页HTML，并提取attachGuid（招标文件正文.pdf）
    
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
            
            # 从HTML中提取attachGuid（查找"招标文件正文.pdf"的attachGuid）
            html_content = response.text
            
            # 方法1：使用正则表达式查找"招标文件正文.pdf"对应的attachGuid
            pattern = r'ztbfjyz\([^)]*attachGuid=([0-9a-fA-F-]{36})[^)]*title="招标文件正文\.pdf"'
            match = re.search(pattern, html_content)
            
            if not match:
                # 方法2：查找所有attachGuid，然后查找对应的标题
                pattern_all = r'attachGuid=([0-9a-fA-F-]{36})'
                matches = re.finditer(pattern_all, html_content)
                for m in matches:
                    # 查找这个attachGuid附近的标题
                    start_pos = max(0, m.start() - 200)
                    end_pos = min(len(html_content), m.end() + 200)
                    context = html_content[start_pos:end_pos]
                    if '招标文件正文.pdf' in context or 'title="招标文件正文.pdf"' in context:
                        attach_guid = m.group(1)
                        log.debug(f"成功提取attachGuid: {attach_guid}")
                        return attach_guid
            
            if match:
                attach_guid = match.group(1)
                log.debug(f"成功提取attachGuid: {attach_guid}")
                return attach_guid
            else:
                # 静默处理：找不到attachGuid的项目直接跳过
                log.debug(f"未找到招标文件正文.pdf的attachGuid: {detail_url}，跳过该项目")
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


def get_verification_code(session: requests.Session, sid: str,
                          headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                          timeout: int = 15, retry_times: int = 3) -> Optional[Dict]:
    """
    获取验证码
    
    Args:
        session: requests.Session 对象
        sid: 会话ID（需要从浏览器自动化获取）
        headers: 请求头（可选）
        cookies: Cookie（可选，需要包含sid）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        dict: {"imgCode": "...", "verificationCodeGuid": "...", "verificationCodeValue": "..."}
        失败返回 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_CAPTCHA.copy()
            request_cookies = cookies.copy() if cookies else {}
            request_cookies["sid"] = sid
            
            # 准备请求数据
            data = {
                "params": '{"width":"100","height":"40","codeNum":"4","interferenceLine":"1","codeGuid":""}'
            }
            
            # 执行请求
            response = session.post(
                API_VERIFICATION_CODE_URL,
                headers=request_headers,
                cookies=request_cookies,
                data=data,
                timeout=timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("custom"):
                return result["custom"]
            else:
                log.warning(f"验证码响应格式异常: {result}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"获取验证码失败（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"获取验证码失败，已达最大重试次数: {str(e)}")
                return None
    
    return None


def download_file(session: requests.Session, attach_guid: str, save_path: str,
                  verification_code: Optional[str] = None,
                  verification_guid: Optional[str] = None,
                  sid: Optional[str] = None,
                  headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                  timeout: int = 120, retry_times: int = 3) -> bool:
    """
    下载文件
    
    Args:
        session: requests.Session 对象
        attach_guid: 附件GUID
        save_path: 保存路径
        verification_code: 验证码（可选，如果为None则尝试使用备用验证码）
        verification_guid: 验证码GUID（可选）
        sid: 会话ID（可选，如果为None则尝试使用备用sid）
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        成功返回 True，失败返回 False
    """
    for attempt in range(retry_times + 1):
        try:
            # 如果没有提供验证码，尝试使用备用验证码
            if not verification_code:
                if PLATFORM_CONFIG.get("verification_code_fallback"):
                    verification_code = PLATFORM_CONFIG["verification_code_fallback"]
                    log.info(f"使用备用验证码下载文件")
                else:
                    log.error(f"缺少验证码，无法下载文件")
                    return False
            
            # 如果没有提供verification_guid，这是一个严重问题，因为guid必须从API获取
            if not verification_guid:
                log.error(f"⚠️ verification_guid未提供！验证码验证可能失败。verification_guid必须从getVerificationCode API获取，不能使用verification_code作为guid。")
                # 仍然尝试使用verification_code作为guid（虽然可能失败）
                verification_guid = verification_code
                log.warning(f"使用verification_code作为verification_guid（可能失败）: {verification_guid}")
            
            # 如果没有提供sid，尝试使用备用sid
            if not sid:
                if PLATFORM_CONFIG.get("sid_fallback"):
                    sid = PLATFORM_CONFIG["sid_fallback"]
                    log.info(f"使用备用sid下载文件")
                else:
                    log.error(f"缺少sid，无法下载文件")
                    return False
            
            # 准备请求头
            request_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
            
            # 重要：cookies必须和获取验证码时保持一致，只使用sid和oauth相关的cookies
            # 不能使用其他cookies（如HWWAFSESID等），否则验证码验证会失败
            request_cookies = cookies.copy() if cookies else {}
            request_cookies["sid"] = sid
            # 只添加oauth相关的cookies，确保和获取验证码时一致
            request_cookies["oauthClientId"] = COOKIES.get("oauthClientId", "admin")
            request_cookies["oauthPath"] = COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder")
            request_cookies["oauthLoginUrl"] = COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=")
            request_cookies["oauthLogoutUrl"] = COOKIES.get("oauthLogoutUrl", "")
            
            # 调试日志：确保sid一致
            log.debug(f"下载请求cookies - sid: {request_cookies.get('sid', 'None')[:20]}..., cookies keys: {list(request_cookies.keys())}")
            
            # 准备请求参数
            params = {
                "cmd": "getContent",
                "attachGuid": attach_guid,
                "appUrlFlag": "ztb001",
                "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
                "verificationCode": verification_code,
                "verificationGuid": verification_guid
            }
            
            # 调试日志：输出请求参数（隐藏敏感信息）
            log.debug(f"下载请求参数 - attachGuid: {attach_guid[:20]}..., verificationCode: {verification_code}, verificationGuid: {verification_guid[:30] if verification_guid else 'None'}..., sid: {sid[:20] if sid else 'None'}...")
            
            # 准备请求体
            data = '------WebKitFormBoundaryZBgd51WalrM7i5YR--\\r\\n'.encode('unicode_escape')
            
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
            
            # 判断是否为PDF文件
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
                try:
                    error_text = content[:500].decode('utf-8', errors='ignore') if content else ""
                    # 检查是否是验证码错误
                    is_captcha_error = "验证码验证失败" in error_text or "validateVerificationCode" in error_text
                    if is_captcha_error:
                        log.warning(f"验证码验证失败（第{attempt+1}次尝试），响应: {error_text[:200]}")
                        log.info(f"当前使用的验证码: {verification_code}, guid: {verification_guid[:30] if verification_guid else 'None'}...")
                except:
                    error_text = f"二进制内容，长度: {len(content)}字节"
                    is_captcha_error = False
                
                if not is_captcha_error:
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