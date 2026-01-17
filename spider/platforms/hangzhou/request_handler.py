"""杭州市招标平台请求处理函数

封装了可执行的HTTP请求函数
"""

import requests
import time
from utils.log import log
from spider.platforms.hangzhou.config import generate_random_key


def execute_request(session, url, method="GET", params=None, data=None,
                   headers=None, cookies=None, timeout=15, retry_times=3):
    """
    执行HTTP请求（统一接口）
    
    Args:
        session: requests.Session 对象
        url: 请求URL
        method: HTTP方法（GET/POST）
        params: URL参数（字典）
        data: 请求体数据（字典或字符串）
        headers: 请求头（字典）
        cookies: Cookie（字典）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        requests.Response 或 None
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求参数
            kwargs = {
                "timeout": timeout,
            }
            
            # 添加请求头（动态生成jy-random-key）
            request_headers = headers.copy() if headers else {}
            if "jy-random-key" not in request_headers:
                request_headers["jy-random-key"] = generate_random_key()
            kwargs["headers"] = request_headers
            
            # 添加Cookie
            if cookies:
                kwargs["cookies"] = cookies
            
            # 执行请求
            if method.upper() == "GET":
                response = session.get(url, params=params, **kwargs)
            elif method.upper() == "POST":
                if headers and "application/json" in headers.get("Content-Type", ""):
                    response = session.post(url, params=params, json=data, **kwargs)
                else:
                    response = session.post(url, params=params, data=data, **kwargs)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            # 检查响应状态
            response.raise_for_status()
            
            # 检查响应JSON格式
            if response.headers.get("Content-Type", "").startswith("application/json"):
                result = response.json()
                # 检查业务逻辑是否成功
                if isinstance(result, dict) and result.get("code") != 200:
                    error_msg = result.get("msg", "未知错误")
                    log.warning(f"API返回业务错误: code={result.get('code')}, msg={error_msg}")
                    if attempt < retry_times:
                        wait_time = 2 * (attempt + 1)
                        time.sleep(wait_time)
                        continue
                    return None
            
            return response
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"请求超时（第{attempt+1}次），{wait_time}秒后重试: {url}")
                time.sleep(wait_time)
            else:
                log.error(f"请求超时，已达最大重试次数: {url}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"连接错误（第{attempt+1}次），{wait_time}秒后重试: {url}")
                time.sleep(wait_time)
            else:
                log.error(f"连接错误，已达最大重试次数: {url}")
                return None
                
        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP错误 {response.status_code}: {url}, 错误: {str(e)}")
            return None
            
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"请求失败（第{attempt+1}次），{wait_time}秒后重试: {url}, 错误: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"请求失败，已达最大重试次数: {url}, 错误: {str(e)}")
                return None
    
    return None


def get_doc_list(session, current=1, size=10, area=0, tradeType=5, afficheType=21, headers=None, cookies=None):
    """
    获取招标公告列表（对应demo中的get_doc_id函数）
    
    Args:
        session: requests.Session对象
        current: 当前页码
        size: 每页数量
        area: 区域代码（0表示全部）
        tradeType: 交易类型（5表示建设工程）
        afficheType: 公告类型（21表示招标公告）
        headers: 请求头
        cookies: Cookie
    
    Returns:
        dict: API返回的JSON数据，失败返回None
    """
    url = "https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/list"
    params = {
        "size": str(size),
        "current": str(current),
        "area": str(area),
        "tradeType": str(tradeType),
        "afficheType": str(afficheType),
    }
    
    response = execute_request(
        session=session,
        url=url,
        method="GET",
        params=params,
        headers=headers,
        cookies=cookies,
        timeout=15
    )
    
    if response:
        try:
            return response.json()
        except Exception as e:
            log.error(f"解析列表响应JSON失败: {str(e)}")
            return None
    
    return None


def get_doc_detail(session, doc_id, headers=None, cookies=None):
    """
    获取招标公告详情（对应demo中的find_download_id函数）
    
    Args:
        session: requests.Session对象
        doc_id: 公告ID
        headers: 请求头
        cookies: Cookie
    
    Returns:
        dict: API返回的JSON数据，失败返回None
    """
    url = "https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/find"
    params = {
        "id": doc_id
    }
    
    response = execute_request(
        session=session,
        url=url,
        method="GET",
        params=params,
        headers=headers,
        cookies=cookies,
        timeout=15
    )
    
    if response:
        try:
            return response.json()
        except Exception as e:
            log.error(f"解析详情响应JSON失败: {str(e)}")
            return None
    
    return None


def download_file(session, fileServiceId, save_path, headers=None, cookies=None, timeout=120):
    """
    下载文件（对应demo中的download_id函数）
    
    Args:
        session: requests.Session对象
        fileServiceId: 文件服务ID
        save_path: 保存路径
        headers: 请求头
        cookies: Cookie
        timeout: 超时时间（秒，文件下载可能需要更长时间）
    
    Returns:
        bool: True表示下载成功，False表示失败
    """
    url = f"https://ggzy.hzctc.hangzhou.gov.cn/api/file/download/{fileServiceId}"
    
    response = execute_request(
        session=session,
        url=url,
        method="GET",
        headers=headers,
        cookies=cookies,
        timeout=timeout
    )
    
    if response:
        try:
            # 检查是否是文件内容
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                # 可能是错误响应
                result = response.json()
                log.error(f"下载文件失败，API返回错误: {result}")
                return False
            
            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            log.info(f"文件下载成功: {save_path}")
            return True
            
        except Exception as e:
            log.error(f"保存文件失败: {save_path}, 错误: {str(e)}")
            return False
    else:
        log.error(f"文件下载失败: fileServiceId={fileServiceId}")
        return False
