"""湖州市招标平台请求处理函数

封装了可执行的HTTP请求函数
"""

import os
import requests
import time
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from utils.log import log
from spider.platforms.huzhou.config import (
    BASE_URL, LIST_URL_TEMPLATE, API_DOWNLOAD_URL,
    HEADERS_LIST, HEADERS_DETAIL, HEADERS_DOWNLOAD, COOKIES, PLATFORM_CONFIG
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


def download_file(session: requests.Session, attach_guid: str, save_path: str,
                  verification_code: Optional[str] = None,
                  verification_guid: Optional[str] = None,
                  sid: Optional[str] = None,
                  headers: Optional[Dict] = None, cookies: Optional[Dict] = None,
                  timeout: int = 120, retry_times: int = 2) -> Dict[str, Any]:
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
        retry_times: 网络错误重试次数（验证码错误不重试，由上层处理）
    
    Returns:
        dict: {"success": bool, "is_captcha_error": bool, "error_msg": str}
    """
    last_error_msg = ""
    is_captcha_error = False

    if not (sid and verification_code and verification_guid):
        return {"success": False, "is_captcha_error": False, "error_msg": "缺少 sid/验证码/guid，无法下载"}

    for attempt in range(retry_times + 1):
        try:
            request_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
            
            request_cookies = {
                "sid": sid,
                "oauthClientId": COOKIES.get("oauthClientId", "admin"),
                "oauthPath": COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder"),
                "oauthLoginUrl": COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri="),
                "oauthLogoutUrl": COOKIES.get("oauthLogoutUrl", "")
            }
            
            log.debug(f"下载请求cookies - sid: {request_cookies.get('sid', 'None')[:20]}...")
            
            params = {
                "cmd": "getContent",
                "attachGuid": attach_guid,
                "appUrlFlag": "ztb001",
                "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
                "verificationCode": verification_code,
                "verificationGuid": verification_guid
            }
            
            log.debug(f"下载请求参数 - verificationCode: {verification_code}, verificationGuid: {verification_guid[:30] if verification_guid else 'None'}...")
            
            data = '------WebKitFormBoundaryZBgd51WalrM7i5YR--\\r\\n'.encode('unicode_escape')

            # 关键：使用裸 requests.post 而非 session.post。
            # 验证码是用只含 {sid, oauth*} 的干净 cookie 上下文获取的（见 get_verification_code_with_ocr），
            # 若这里走 session，session.cookies 里被 run() 注入的过期 WAF/oauth cookie
            # （HWWAFSESID/noOauthAccessToken 等）会一起发出，服务端认为验证码与会话不匹配，
            # 100% 返回"验证码验证失败"。demo 能成功正是因为下载与取验证码用的是同一套裸 cookie。
            response = requests.post(
                API_DOWNLOAD_URL,
                headers=request_headers,
                cookies=request_cookies,
                params=params,
                data=data,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            content = response.content
            
            is_pdf_by_content_type = "application/pdf" in content_type or "application/octet-stream" in content_type
            is_pdf_by_content = len(content) > 10 and content[:4] == b'%PDF'
            
            if is_pdf_by_content_type or is_pdf_by_content:
                if len(content) < 1000:
                    error_text = content[:500].decode('utf-8', errors='ignore') if content else ""
                    last_error_msg = f"文件太小（{len(content)}字节），可能是错误响应: {error_text[:200]}"
                    log.warning(f"文件下载失败: {last_error_msg}")
                    if attempt < retry_times:
                        time.sleep(3 * (attempt + 1))
                        continue
                    return {"success": False, "is_captcha_error": False, "error_msg": last_error_msg}
                
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(content)
                
                file_size_kb = len(content) / 1024
                log.info(f"文件下载成功: {save_path} (大小: {file_size_kb:.2f} KB)")
                return {"success": True, "is_captcha_error": False, "error_msg": ""}
            else:
                try:
                    error_text = content[:500].decode('utf-8', errors='ignore') if content else ""
                    is_captcha_error = "验证码验证失败" in error_text or "验证码错误" in error_text or "validateVerificationCode" in error_text
                    if is_captcha_error:
                        last_error_msg = f"验证码验证失败: {error_text[:200]}"
                        log.warning(f"验证码验证失败，验证码: {verification_code}, guid: {verification_guid[:30] if verification_guid else 'None'}...")
                        return {"success": False, "is_captcha_error": True, "error_msg": last_error_msg}
                    else:
                        last_error_msg = f"响应类型: {content_type or '(空)'}, 内容: {error_text[:200]}"
                        log.warning(f"文件下载失败: {last_error_msg}")
                except:
                    last_error_msg = f"二进制内容，长度: {len(content)}字节"
                    log.warning(f"文件下载失败: {last_error_msg}")
                
                if attempt < retry_times:
                    time.sleep(3 * (attempt + 1))
                    continue
                return {"success": False, "is_captcha_error": False, "error_msg": last_error_msg}
            
        except requests.exceptions.Timeout as e:
            last_error_msg = f"下载超时: {str(e)}"
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"文件下载超时（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载超时，已达最大重试次数")
                return {"success": False, "is_captcha_error": False, "error_msg": last_error_msg}
                
        except requests.exceptions.ConnectionError as e:
            last_error_msg = f"连接错误: {str(e)}"
            if attempt < retry_times:
                wait_time = 10 * (attempt + 1)
                log.warning(f"文件下载连接错误（第{attempt+1}次），{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载连接错误，已达最大重试次数")
                return {"success": False, "is_captcha_error": False, "error_msg": last_error_msg}
                
        except Exception as e:
            last_error_msg = f"下载异常: {str(e)}"
            if attempt < retry_times:
                wait_time = 3 * (attempt + 1)
                log.warning(f"文件下载异常（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"文件下载异常，已达最大重试次数: {str(e)}")
                return {"success": False, "is_captcha_error": False, "error_msg": last_error_msg}
    
    return {"success": False, "is_captcha_error": is_captcha_error, "error_msg": last_error_msg}