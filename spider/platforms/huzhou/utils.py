"""湖州市平台辅助工具函数

用于获取sid和验证码的辅助函数
"""

import base64
import requests
from typing import Optional, Dict
from utils.log import log
from spider.platforms.huzhou.config import (
    API_VERIFICATION_CODE_URL, HEADERS_CAPTCHA, COOKIES
)

try:
    import ddddocr
    DDDDOCR_AVAILABLE = True
except ImportError:
    DDDDOCR_AVAILABLE = False
    # 只在需要时输出警告，避免每次导入都输出

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSIONPAGE_AVAILABLE = True
except ImportError:
    DRISSIONPAGE_AVAILABLE = False
    # 只在需要时输出警告，避免每次导入都输出

# 导出可用性标志，供外部检查
# 导出可用性标志，供外部检查
__all__ = [
    "get_sid_from_cookies",
    "get_verification_code_with_ocr",
    "auto_get_sid",
    "auto_get_sid_and_verification_code",
    "DDDDOCR_AVAILABLE",
    "DRISSIONPAGE_AVAILABLE",
]


def get_sid_from_cookies(cookies: Dict) -> Optional[str]:
    """
    从Cookie字典中提取sid
    
    Args:
        cookies: Cookie字典
    
    Returns:
        sid字符串，失败返回None
    """
    if isinstance(cookies, dict):
        return cookies.get("sid")
    return None


def get_verification_code_with_ocr(sid: str) -> Optional[Dict]:
    """
    获取验证码并使用OCR识别
    
    Args:
        sid: 会话ID
    
    Returns:
        dict: {"code": "...", "guid": "..."} 或 None
    """
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr未安装，无法自动识别验证码")
        return None
    
    try:
        # 获取验证码图片
        # 重要：cookies必须和下载时保持一致，只使用sid和oauth相关的cookies
        headers = HEADERS_CAPTCHA.copy()
        cookies = {
            "sid": sid,
            "oauthClientId": COOKIES.get("oauthClientId", "admin"),
            "oauthPath": COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder"),
            "oauthLoginUrl": COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri="),
            "oauthLogoutUrl": COOKIES.get("oauthLogoutUrl", "")
        }
        
        # 调试日志
        log.debug(f"获取验证码请求 - sid: {sid[:20] if sid else 'None'}..., cookies keys: {list(cookies.keys())}")
        
        data = {
            "params": '{"width":"100","height":"40","codeNum":"4","interferenceLine":"1","codeGuid":""}'
        }
        
        response = requests.post(
            API_VERIFICATION_CODE_URL,
            headers=headers,
            cookies=cookies,
            data=data,
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("custom"):
            log.error(f"获取验证码失败: {result}")
            return None
        
        custom = result["custom"]
        img_code_base64 = custom.get("imgCode", "")
        verification_code_guid = custom.get("verificationCodeGuid", "")
        verification_code_value = custom.get("verificationCodeValue", "")
        
        # 调试日志
        log.debug(f"验证码API响应 - guid: {verification_code_guid[:30] if verification_code_guid else 'None'}..., value: {verification_code_value[:20] if verification_code_value else 'None'}...")
        
        # 使用OCR识别验证码
        try:
            if "," in img_code_base64:
                base64_data = img_code_base64.split(",")[1]
            else:
                base64_data = img_code_base64
            
            image_bytes = base64.b64decode(base64_data)
            ocr = ddddocr.DdddOcr()
            recognized_code = ocr.classification(image_bytes)
            
            # 清理验证码：去除空格、换行等空白字符，转换为大写（某些验证码不区分大小写）
            recognized_code = recognized_code.strip().replace(' ', '').replace('\n', '').replace('\r', '')
            
            log.info(f"验证码识别成功（原始: {ocr.classification(image_bytes)}, 清理后: {recognized_code}）")
            
            return {
                "code": recognized_code,
                "guid": verification_code_guid,
                "value": verification_code_value
            }
        except Exception as e:
            log.error(f"OCR识别验证码失败: {str(e)}")
            return None
            
    except Exception as e:
        log.error(f"获取验证码失败: {str(e)}")
        return None


def auto_get_sid(detail_url: str) -> Optional[str]:
    """
    自动获取sid（需要浏览器自动化）
    
    注意：此函数需要安装DrissionPage
    安装命令：
        pip install DrissionPage
    
    Args:
        detail_url: 详情页URL
    
    Returns:
        sid字符串，失败返回None
    """
    if not DRISSIONPAGE_AVAILABLE:
        log.error("DrissionPage未安装，无法自动获取sid。请安装: pip install DrissionPage")
        return None
    
    options = ChromiumOptions()
    options.headless()
    page = ChromiumPage(options)
    
    try:
        log.info("正在加载目标页面...")
        page.get(detail_url)
        import time
        time.sleep(3)
        log.info("页面加载完成")
        
        # 点击下载链接
        log.info("正在定位下载链接...")
        link = page.ele('@title=招标文件正文.pdf')
        if link:
            link.click()
            time.sleep(3)
            log.info("已点击下载链接")
        else:
            log.warning("未找到下载链接")
            return None
        
        # 输入验证码（任意值即可，目的是获取sid）
        log.info("正在定位验证码输入框...")
        put = page.ele('@id=yzm')
        if put:
            put.input('1234')  # 输入任意验证码
            time.sleep(1)
            
            # 点击确认按钮
            confirm_btn = page.ele('@class=layui-layer-btn0')
            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)
                log.info("已点击确认按钮")
        
        # 提取sid
        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get('name')] = c.get('value')
        else:
            cookie_dict = cookies
        
        sid = cookie_dict.get('sid')
        if not sid:
            log.error("未提取到sid")
            return None
        
        log.info(f"成功提取sid: {sid}")
        return sid
        
    except Exception as e:
        log.error(f"自动获取sid失败: {str(e)}", exc_info=True)
        return None
    finally:
        page.quit()


def auto_get_sid_and_verification_code(detail_url: str) -> Optional[Dict]:
    """
    自动获取sid和验证码（需要浏览器自动化）
    
    注意：此函数需要安装DrissionPage和ddddocr
    安装命令：
        pip install DrissionPage ddddocr
    
    Args:
        detail_url: 详情页URL
    
    Returns:
        dict: {"sid": "...", "verification_code": "...", "verification_guid": "..."} 或 None
    """
    if not DRISSIONPAGE_AVAILABLE:
        log.error("DrissionPage未安装，无法自动获取sid。请安装: pip install DrissionPage")
        return None
    
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr未安装，无法自动识别验证码。请安装: pip install ddddocr")
        return None
    
    options = ChromiumOptions()
    options.headless()
    page = ChromiumPage(options)
    
    try:
        log.info("正在加载目标页面...")
        page.get(detail_url)
        import time
        time.sleep(3)
        log.info("页面加载完成")
        
        # 点击下载链接
        log.info("正在定位下载链接...")
        link = page.ele('@title=招标文件正文.pdf')
        if link:
            link.click()
            time.sleep(3)
            log.info("已点击下载链接")
        else:
            log.warning("未找到下载链接")
            return None
        
        # 输入验证码（任意值即可，目的是获取sid）
        log.info("正在定位验证码输入框...")
        put = page.ele('@id=yzm')
        if put:
            put.input('1234')  # 输入任意验证码
            time.sleep(1)
            
            # 点击确认按钮
            confirm_btn = page.ele('@class=layui-layer-btn0')
            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)
                log.info("已点击确认按钮")
        
        # 提取sid
        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get('name')] = c.get('value')
        else:
            cookie_dict = cookies
        
        sid = cookie_dict.get('sid')
        if not sid:
            log.error("未提取到sid")
            return None
        
        log.info(f"成功提取sid: {sid}")
        
        # 获取验证码并识别
        verification_info = get_verification_code_with_ocr(sid)
        if not verification_info:
            return None
        
        return {
            "sid": sid,
            "verification_code": verification_info["code"],
            "verification_guid": verification_info["guid"]
        }
        
    except Exception as e:
        log.error(f"自动获取sid和验证码失败: {str(e)}", exc_info=True)
        return None
    finally:
        page.quit()
