"""衢州市阳光交易服务平台请求封装"""

import json
import os
import re
import time
import base64
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, parse_qs
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from PIL import Image
from utils.log import log
from spider.platforms.quzhou.config import (
    BASE_URL,
    LIST_URL_TEMPLATE,
    CAPTCHA_INIT_URL,
    CAPTCHA_CHECK_URL,
    DOWNLOAD_URL,
    HEADERS_LIST,
    HEADERS_CAPTCHA,
    HEADERS_DETAIL,
    HEADERS_DOWNLOAD,
    COOKIES,
    OCR_API_URL,
    OCR_TOKEN,
    OCR_TYPE,
)


def get_project_list(
    session: requests.Session,
    page: int = 1,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[List[Dict]]:
    """
    获取项目列表
    
    Args:
        session: requests.Session对象
        page: 页码（从1开始，第一页是sec.html，第二页是2.html）
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        list: 项目列表，每个项目包含 {href, title, date, region}，失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_LIST.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 构建URL：第一页是sec.html，第二页是2.html，第三页是3.html，以此类推
            if page == 1:
                url = LIST_URL_TEMPLATE.format(page="sec")
            else:
                url = LIST_URL_TEMPLATE.format(page=str(page))
            
            log.debug(f"请求第{page}页数据: URL={url}")
            
            response = session.get(
                url,
                headers=req_headers,
                cookies=req_cookies,
                timeout=timeout,
            )
            response.encoding = "utf-8"
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有项目项
            items = soup.find_all('li', class_='wb-data-list')
            projects = []
            
            for item in items:
                try:
                    # 提取链接和标题
                    link_elem = item.find('div', class_='wb-data-infor').find('a')
                    if not link_elem:
                        continue
                    
                    href = link_elem.get('href', '')
                    title = link_elem.get('title', '') or link_elem.get_text(strip=True)
                    
                    # 提取日期
                    date_elem = item.find('span', class_='wb-data-date')
                    date_str = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # 提取地区（从链接文本中提取，格式：[地区名]）
                    link_text = link_elem.get_text(strip=True)
                    region = "衢州市"
                    if '[' in link_text and ']' in link_text:
                        # 查找第二个[xxx]作为地区
                        parts = link_text.split(']')
                        if len(parts) >= 2:
                            region_part = parts[1].split('[')
                            if len(region_part) >= 2:
                                region = region_part[1].split(']')[0]
                    
                    if href and title:
                        projects.append({
                            "href": href,
                            "title": title,
                            "date": date_str,
                            "region": region,
                        })
                except Exception as e:
                    log.warning(f"解析项目项失败: {str(e)}")
                    continue
            
            log.debug(f"第{page}页解析到{len(projects)}个项目")
            return projects
            
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


def init_captcha(
    session: requests.Session,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[Dict]:
    """
    初始化验证码
    
    Args:
        session: requests.Session对象
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        dict: {"captchaID": "...", "clickWords": [...]}，失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_CAPTCHA.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            data = {
                "step": "get",
                "captchaType": "textclick"
            }
            
            response = session.post(
                CAPTCHA_INIT_URL,
                headers=req_headers,
                cookies=req_cookies,
                data=data,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
            
            captcha_id = result.get("captchaID")
            click_words = result.get("clickWords", [])
            backpic_image_base64 = result.get("backpicImageBase64", "")
            
            if not captcha_id or not click_words:
                log.warning(f"验证码初始化响应格式异常: {result}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
            log.debug(f"验证码初始化成功: captchaID={captcha_id[:20]}..., clickWords={click_words}")
            
            return {
                "captchaID": captcha_id,
                "clickWords": click_words,
                "backpicImageBase64": backpic_image_base64,
            }
            
        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"验证码初始化异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"验证码初始化异常，已达最大重试次数: {str(e)}")
                return None
    return None


def check_captcha(
    session: requests.Session,
    captcha_id: str,
    click_words: List[str],
    backpic_image_base64: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[str]:
    """
    验证验证码并返回验证码值
    
    Args:
        captcha_id: 验证码ID
        click_words: 需要点击的文字列表
        backpic_image_base64: 验证码图片的Base64字符串
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        str: 验证码值（validateCode），失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            # 使用OCR服务识别验证码
            # 处理Base64图片
            if not backpic_image_base64:
                log.error("验证码图片Base64为空")
                return None
            
            # 如果Base64包含前缀，去掉前缀
            if ',' in backpic_image_base64:
                base64_data = backpic_image_base64.split(',')[1]
            else:
                base64_data = backpic_image_base64
            
            # 调整图片大小（与demo一致）
            try:
                img_data = base64.b64decode(base64_data)
                img = Image.open(BytesIO(img_data))
                original_width, original_height = img.size
                new_width = 310
                new_height = int(original_height * (new_width / original_width))
                img = img.resize((new_width, new_height))
                
                # 将调整后的图片转换为Base64
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
            except Exception as e:
                log.warning(f"图片处理失败，使用原始Base64: {str(e)}")
                img_base64 = base64_data
            
            # 调用OCR API
            ocr_data = {
                "token": OCR_TOKEN,
                "type": OCR_TYPE,
                "image": img_base64,
                "extra": ','.join(click_words)
            }
            ocr_headers = {
                "Content-Type": "application/json"
            }
            
            ocr_response = requests.post(
                OCR_API_URL,
                headers=ocr_headers,
                json=ocr_data,
                timeout=timeout,
            )
            ocr_response.raise_for_status()
            ocr_result = ocr_response.json()
            
            if ocr_result.get('code') != 10000:
                log.error(f"OCR识别失败: {ocr_result}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
            # 解析OCR返回的坐标
            coordinate_str = ocr_result.get('data', {}).get('data', '')
            if not coordinate_str:
                log.error(f"OCR返回数据格式异常: {ocr_result}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
            # 解析坐标字符串，格式：199,49|94,121|99,49
            coordinates = coordinate_str.split('|')
            check_nodes = []
            for coord in coordinates:
                try:
                    x, y = map(int, coord.split(','))
                    check_nodes.append({'x': x, 'y': y})
                except ValueError:
                    log.warning(f"坐标格式错误: {coord}")
                    continue
            
            if len(check_nodes) != len(click_words):
                log.warning(f"坐标数量({len(check_nodes)})与文字数量({len(click_words)})不匹配")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
            # 提交验证码验证
            req_headers = headers.copy() if headers else HEADERS_CAPTCHA.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            check_data = {
                "verifyCodeId": captcha_id,
                "checkNodes": json.dumps(check_nodes),
                "imgWidth": "310",
                "step": "check",
                "captchaType": "textclick"
            }
            
            response = session.post(
                CAPTCHA_CHECK_URL,
                headers=req_headers,
                cookies=req_cookies,
                data=check_data,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
            
            validate_code = result.get("validateCode")
            if not validate_code:
                log.warning(f"验证码验证失败: {result}")
                if attempt < retry_times:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            
            log.debug(f"验证码验证成功: validateCode={validate_code[:30]}...")
            return validate_code
            
        except Exception as e:
            if attempt < retry_times:
                wait = 2 * (attempt + 1)
                log.warning(f"验证码验证异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"验证码验证异常，已达最大重试次数: {str(e)}")
                return None
    return None


def get_doc_detail(
    session: requests.Session,
    detail_url: str,
    headers: Optional[Dict] = None,
    cookies: Optional[Dict] = None,
    timeout: int = 15,
    retry_times: int = 3,
) -> Optional[Dict]:
    """
    获取详情页并解析下载信息
    
    Args:
        session: requests.Session对象
        detail_url: 详情页URL
        headers: 请求头（可选）
        cookies: Cookie（可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        dict: {"attachGuid": "...", "appUrlFlag": "...", "siteGuid": "..."}，失败返回None
    """
    for attempt in range(retry_times + 1):
        try:
            req_headers = headers.copy() if headers else HEADERS_DETAIL.copy()
            req_cookies = cookies.copy() if cookies else COOKIES.copy()
            
            # 如果是相对路径，转换为绝对路径
            if detail_url.startswith('/'):
                full_url = urljoin(BASE_URL, detail_url)
            elif detail_url.startswith('http'):
                full_url = detail_url
            else:
                full_url = urljoin(BASE_URL, '/' + detail_url)
            
            response = session.get(
                full_url,
                headers=req_headers,
                cookies=req_cookies,
                timeout=timeout,
            )
            response.encoding = "utf-8"
            response.raise_for_status()
            
            # 解析HTML，查找下载链接
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 根据demo文件，下载链接在onclick属性中
            # 格式：onclick="ztbfjyztest('/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=...&appUrlFlag=...&siteGuid=...','1','1')"
            # 优先查找标题为"招标文件正文.pdf"的链接
            attach_guid = None
            app_url_flag = None
            site_guid = None
            
            # 查找所有包含onclick属性的a标签
            links = soup.find_all('a', onclick=True)
            
            # 优先查找标题为"招标文件正文.pdf"的链接
            for link in links:
                title = link.get('title', '')
                onclick = link.get('onclick', '')
                
                    # 优先选择"招标文件正文.pdf"
                if '招标文件正文.pdf' in title or '招标文件正文' in title:
                    # 从onclick中提取URL参数
                    if 'downloadztbattach' in onclick and 'attachGuid' in onclick:
                        # 提取onclick中的URL部分
                        url_match = re.search(r"downloadztbattach\?([^']+)", onclick)
                        if url_match:
                            url_params = url_match.group(1)
                            # 解析参数
                            params = parse_qs(url_params)
                            attach_guid = params.get('attachGuid', [None])[0]
                            app_url_flag = params.get('appUrlFlag', [None])[0]
                            site_guid = params.get('siteGuid', [None])[0]
                            if attach_guid:
                                log.debug(f"找到招标文件正文链接: attachGuid={attach_guid[:20]}...")
                                break
            
            # 如果没有找到"招标文件正文.pdf"，则查找第一个包含attachGuid的链接
            if not attach_guid:
                for link in links:
                    onclick = link.get('onclick', '')
                    if 'downloadztbattach' in onclick and 'attachGuid' in onclick:
                        url_match = re.search(r"downloadztbattach\?([^']+)", onclick)
                        if url_match:
                            url_params = url_match.group(1)
                            params = parse_qs(url_params)
                            attach_guid = params.get('attachGuid', [None])[0]
                            app_url_flag = params.get('appUrlFlag', [None])[0]
                            site_guid = params.get('siteGuid', [None])[0]
                            if attach_guid:
                                log.debug(f"找到下载链接: attachGuid={attach_guid[:20]}...")
                                break
            
            if not attach_guid:
                log.warning(f"未找到下载链接: {detail_url}")
                # 调试：输出HTML片段以便排查
                download_div = soup.find('div', class_='download')
                if download_div:
                    log.debug(f"找到download div，内容: {str(download_div)[:500]}")
                if attempt < retry_times:
                    continue
                return None
            
            log.debug(f"找到下载信息: attachGuid={attach_guid[:20]}..., appUrlFlag={app_url_flag}, siteGuid={site_guid[:20] if site_guid else None}...")
            
            return {
                "attachGuid": attach_guid,
                "appUrlFlag": app_url_flag or "ztb001",
                "siteGuid": site_guid or "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",  # 默认值来自demo
            }
            
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
    attach_guid: str,
    app_url_flag: str,
    site_guid: str,
    validate_code: str,
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
        attach_guid: 附件GUID
        app_url_flag: 应用URL标志
        site_guid: 站点GUID
        validate_code: 验证码值
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
            
            params = {
                "cmd": "getContent",
                "attachGuid": attach_guid,
                "appUrlFlag": app_url_flag,
                "siteGuid": site_guid,
                "verificationCode": validate_code,
                "verificationGuid": validate_code,
            }
            
            # 更新Referer头，包含完整的下载URL参数（与demo一致）
            referer_url = f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid={attach_guid}&appUrlFlag={app_url_flag}&siteGuid={site_guid}&verificationCode={validate_code}&verificationGuid={validate_code}"
            req_headers["Referer"] = referer_url
            
            # 构建multipart/form-data数据（与demo一致）
            data = '------WebKitFormBoundaryx17IciPvRg6OIOK9--\\r\\n'.encode('unicode_escape')
            
            response = session.post(
                DOWNLOAD_URL,
                headers=req_headers,
                cookies=req_cookies,
                params=params,
                data=data,
                timeout=timeout,
                stream=True,
            )
            response.raise_for_status()
            
            # 判断文件类型
            content_type = response.headers.get("Content-Type", "").lower()
            disposition = response.headers.get("Content-Disposition", "")
            
            file_ext = "pdf"  # 默认扩展名
            
            # 从Content-Disposition中提取
            if disposition:
                if '.pdf' in disposition.lower():
                    file_ext = "pdf"
                elif '.docx' in disposition.lower():
                    file_ext = "docx"
                elif '.doc' in disposition.lower():
                    file_ext = "doc"
                elif '.zip' in disposition.lower():
                    file_ext = "zip"
            
            # 从Content-Type中判断
            if "pdf" in content_type:
                file_ext = "pdf"
            elif "zip" in content_type:
                file_ext = "zip"
            elif "word" in content_type or "msword" in content_type:
                file_ext = "docx" if "wordprocessingml" in content_type else "doc"
            
            # 从文件内容判断
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
            
        except Exception as e:
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"文件下载异常（第{attempt+1}次），{wait}秒后重试: {str(e)}")
                time.sleep(wait)
            else:
                log.error(f"文件下载异常，已达最大重试次数: {str(e)}")
                return None
    return None
