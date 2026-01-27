"""丽水市平台辅助工具函数

用于获取 sid 和验证码（OCR）。
"""

import base64
import requests
from typing import Optional, Dict

from utils.log import log
from spider.platforms.lishui.config import (
    API_VERIFICATION_CODE_URL,
    HEADERS_CAPTCHA,
    COOKIES,
)

try:
    import ddddocr
    DDDDOCR_AVAILABLE = True
except ImportError:
    DDDDOCR_AVAILABLE = False

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSIONPAGE_AVAILABLE = True
except ImportError:
    DRISSIONPAGE_AVAILABLE = False

__all__ = [
    "get_sid_from_cookies",
    "get_verification_code_with_ocr",
    "auto_get_sid",
    "auto_get_sid_and_verification_code",
    "DDDDOCR_AVAILABLE",
    "DRISSIONPAGE_AVAILABLE",
]


def get_sid_from_cookies(cookies: Dict) -> Optional[str]:
    if isinstance(cookies, dict):
        return cookies.get("sid")
    return None


def _build_min_cookies(sid: str) -> Dict:
    """构建验证码/下载一致的 cookie 集合（必要 + demo 常用的 token 可选带上）"""
    cookies = {
        "sid": sid,
        "oauthClientId": COOKIES.get("oauthClientId", "demoClient"),
        "oauthPath": COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder"),
        "oauthLoginUrl": COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri="),
        "oauthLogoutUrl": COOKIES.get("oauthLogoutUrl", ""),
    }
    # demo 里还有一些 token（可能过期）；有值就带上
    for k in ("noOauthRefreshToken", "noOauthAccessToken", "_CSRFCOOKIE", "EPTOKEN"):
        v = COOKIES.get(k)
        if v:
            cookies[k] = v
    return cookies


def get_verification_code_with_ocr(sid: str) -> Optional[Dict]:
    """获取验证码并使用 OCR 识别，返回 {"code":..., "guid":..., "value":...}"""
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr未安装，无法自动识别验证码")
        return None

    try:
        headers = HEADERS_CAPTCHA.copy()
        cookies = _build_min_cookies(sid)
        log.debug(f"获取验证码请求 - sid: {sid[:20] if sid else 'None'}..., cookies keys: {list(cookies.keys())}")

        data = {"params": '{"width":"100","height":"40","codeNum":"4","interferenceLine":"1","codeGuid":""}'}
        resp = requests.post(API_VERIFICATION_CODE_URL, headers=headers, cookies=cookies, data=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        custom = result.get("custom") or {}
        img_code_base64 = custom.get("imgCode", "")
        verification_code_guid = custom.get("verificationCodeGuid", "")
        verification_code_value = custom.get("verificationCodeValue", "")

        if not img_code_base64 or not verification_code_guid:
            log.error(f"验证码API响应缺少字段: {result}")
            return None

        if "," in img_code_base64:
            base64_data = img_code_base64.split(",")[1]
        else:
            base64_data = img_code_base64

        image_bytes = base64.b64decode(base64_data)
        ocr = ddddocr.DdddOcr()
        recognized_code = ocr.classification(image_bytes)
        recognized_code = recognized_code.strip().replace(" ", "").replace("\n", "").replace("\r", "")

        log.info(f"验证码识别成功: {recognized_code}, guid: {verification_code_guid[:20]}...")
        return {"code": recognized_code, "guid": verification_code_guid, "value": verification_code_value}
    except Exception as e:
        log.error(f"获取验证码失败: {str(e)}", exc_info=True)
        return None


def auto_get_sid(detail_url: str) -> Optional[str]:
    """自动获取 sid（需要 DrissionPage）"""
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

        # 点击“招标文件正文.pdf”触发 sid 生成
        link = page.ele("@title=招标文件正文.pdf")
        if link:
            link.click()
            time.sleep(3)
        else:
            log.warning("未找到下载链接（@title=招标文件正文.pdf）")
            # 继续尝试提取 sid（有时已存在）

        put = page.ele("@id=yzm")
        if put:
            put.input("1234")
            time.sleep(1)
            confirm_btn = page.ele("@class=layui-layer-btn0")
            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)

        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get("name")] = c.get("value")
        else:
            cookie_dict = cookies

        sid = cookie_dict.get("sid")
        if not sid:
            log.error("未提取到sid")
            return None
        log.info(f"成功提取sid: {sid[:20]}...")
        return sid
    except Exception as e:
        log.error(f"自动获取sid失败: {str(e)}", exc_info=True)
        return None
    finally:
        page.quit()


def auto_get_sid_and_verification_code(detail_url: str) -> Optional[Dict]:
    """自动获取 sid + OCR 验证码"""
    if not DRISSIONPAGE_AVAILABLE:
        log.error("DrissionPage未安装，无法自动获取sid。请安装: pip install DrissionPage")
        return None
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr未安装，无法自动识别验证码。请安装: pip install ddddocr")
        return None

    sid = auto_get_sid(detail_url)
    if not sid:
        return None
    info = get_verification_code_with_ocr(sid)
    if not info:
        return None
    return {"sid": sid, "verification_code": info["code"], "verification_guid": info["guid"]}

