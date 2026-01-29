"""衢州市阳光交易服务平台配置"""

PLATFORM_NAME = "衢州市阳光交易服务平台"
PLATFORM_CODE = "quzhou"

BASE_URL = "https://qzygjy.com"
LIST_URL_TEMPLATE = f"{BASE_URL}/jyxx/001004/001004001/001004001001/{{page}}.html"  # 第一页是sec.html，第二页是2.html
CAPTCHA_INIT_URL = f"{BASE_URL}/EWB-FRONT/rest/shellcaptcha/initAndCheckCaptcha"
CAPTCHA_CHECK_URL = f"{BASE_URL}/EWB-FRONT/rest/shellcaptcha/initAndCheckCaptcha"
DOWNLOAD_URL = f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"

# 列表请求头
HEADERS_LIST = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# 验证码请求头
HEADERS_CAPTCHA = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/EWB-FRONT/frame/pages/login/pageVerify.html",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# 详情页请求头
HEADERS_DETAIL = HEADERS_LIST.copy()

# 下载请求头
HEADERS_DOWNLOAD = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryx17IciPvRg6OIOK9",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Cookies（需要从浏览器获取，demo中使用的cookies）
COOKIES = {
    "oauthClientId": "echo",
    "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
    "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
    "oauthLogoutUrl": "",
    # 注意：noOauthRefreshToken和noOauthAccessToken需要定期更新
    # "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
    # "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c",
}

# OCR验证码服务配置（使用云码平台）
OCR_API_URL = "http://api.jfbym.com/api/YmServer/customApi"
OCR_TOKEN = "U3M3KPtPNOQmNJj_fIKOmRms0gxvHbZnOiRSetcDOJ8"  # 需要替换为实际的token
OCR_TYPE = "88888"  # 点击验证码类型

# 爬虫整体配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "list_url_template": LIST_URL_TEMPLATE,
    "captcha_init_url": CAPTCHA_INIT_URL,
    "captcha_check_url": CAPTCHA_CHECK_URL,
    "download_url": DOWNLOAD_URL,
    "headers_list": HEADERS_LIST,
    "headers_captcha": HEADERS_CAPTCHA,
    "headers_detail": HEADERS_DETAIL,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "ocr_api_url": OCR_API_URL,
    "ocr_token": OCR_TOKEN,
    "ocr_type": OCR_TYPE,
    "max_pages": 50,
    "request_interval": 2,
}
