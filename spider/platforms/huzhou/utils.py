"""湖州市平台辅助工具函数

严格对齐 demo（spider/crawl_tests/湖州市/demo_huzhoushi.py）的两步：
1. auto_get_sid：用浏览器打开详情页，点击“招标文件正文.pdf”弹出验证码框，
   随便填几个字符提交（不要求填对），从 cookie 里取到 sid。
2. get_verification_code_with_ocr：拿 sid 去 getVerificationCode 接口领验证码图，
   再用 ddddocr 识别。
"""

import base64
import requests
from typing import Optional, Dict

from utils.log import log
from spider.platforms.huzhou.config import API_VERIFICATION_CODE_URL, HEADERS_CAPTCHA, COOKIES

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
    "auto_get_sid",
    "get_verification_code_with_ocr",
    "DDDDOCR_AVAILABLE",
    "DRISSIONPAGE_AVAILABLE",
]


def auto_get_sid(detail_url: str) -> Optional[str]:
    """打开详情页 → 点击下载 → 弹验证码框随便填几个字提交 → 从 cookie 取 sid。

    与 demo 一致：填的验证码不要求正确，目的只是触发服务端下发 sid。
    """
    if not DRISSIONPAGE_AVAILABLE:
        log.error("DrissionPage 未安装，无法获取 sid。请安装: pip install DrissionPage")
        return None

    import time

    # 与 demo 保持一致：不开 headless。实测无头模式下拿到的 sid 会导致后续验证码
    # 校验 100% 失败（服务端对无头会话下发的 sid 受限）；demo 用可见浏览器点选才有效。
    options = ChromiumOptions()
    page = ChromiumPage(options)
    try:
        page.get(detail_url)
        time.sleep(3)

        link = page.ele('@title=招标文件正文.pdf')
        if not link:
            log.warning("未找到“招标文件正文.pdf”下载链接")
            return None
        link.click()
        time.sleep(3)

        # 弹出验证码框：随便填几个字符并确认（不要求填对，只为拿 sid）
        put = page.ele('@id=yzm')
        if put:
            put.input('1234')
            time.sleep(1)
            confirm_btn = page.ele('@class=layui-layer-btn0')
            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)

        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get('name')] = c.get('value')
        else:
            cookie_dict = cookies

        sid = cookie_dict.get('sid')
        if not sid:
            log.error("未提取到 sid")
            return None
        log.info(f"获取 sid 成功: {sid[:20]}...")
        return sid
    except Exception as e:
        log.error(f"获取 sid 失败: {str(e)}", exc_info=True)
        return None
    finally:
        page.quit()


def get_verification_code_with_ocr(sid: str) -> Optional[Dict]:
    """用 sid 领验证码图并用 ddddocr 识别，返回 {"code":..., "guid":...}。"""
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr 未安装，无法识别验证码。请安装: pip install ddddocr")
        return None

    try:
        cookies = {
            "sid": sid,
            "oauthClientId": COOKIES.get("oauthClientId", "admin"),
            "oauthPath": COOKIES.get("oauthPath", "http://127.0.0.1:8080/EpointWebBuilder"),
            "oauthLoginUrl": COOKIES.get("oauthLoginUrl", "http://127.0.0.1:1112/membercenter/login.html?redirect_uri="),
            "oauthLogoutUrl": COOKIES.get("oauthLogoutUrl", ""),
        }
        data = {
            "params": "{\"width\":\"100\",\"height\":\"40\",\"codeNum\":\"4\",\"interferenceLine\":\"1\",\"codeGuid\":\"\"}"
        }

        response = requests.post(API_VERIFICATION_CODE_URL, headers=HEADERS_CAPTCHA.copy(), cookies=cookies, data=data, timeout=15)
        response.raise_for_status()
        custom = (response.json() or {}).get("custom")
        if not custom:
            log.error(f"领取验证码失败: {response.text[:200]}")
            return None

        img_code_base64 = custom.get("imgCode", "")
        guid = custom.get("verificationCodeGuid", "")
        base64_data = img_code_base64.split(",")[1] if "," in img_code_base64 else img_code_base64
        image_bytes = base64.b64decode(base64_data)

        ocr = ddddocr.DdddOcr()
        code = ocr.classification(image_bytes).strip().replace(" ", "").replace("\n", "").replace("\r", "")
        log.info(f"验证码识别成功: {code}")
        return {"code": code, "guid": guid}
    except Exception as e:
        log.error(f"领取/识别验证码失败: {str(e)}")
        return None
