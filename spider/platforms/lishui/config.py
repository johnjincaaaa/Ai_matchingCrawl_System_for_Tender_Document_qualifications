"""丽水市阳光采购服务平台配置"""

PLATFORM_NAME = "丽水市阳光采购服务平台"
PLATFORM_CODE = "lishui"

BASE_URL = "https://lsygcg.com"

# 列表页URL模板：第一页是sec.html，第二页是2.html，以此类推
LIST_URL_TEMPLATE = f"{BASE_URL}/jyxx/001001/001001002/001001002001"

# 下载相关URL（EpointWebBuilder）
API_VERIFICATION_CODE_URL = f"{BASE_URL}/EpointWebBuilder/rest/frontAppNotNeedLoginAction/getVerificationCode"
API_DOWNLOAD_URL = f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"

# 下载 multipart boundary（demo 里固定写死）
DOWNLOAD_BOUNDARY = "----WebKitFormBoundaryXD323ilkjsRlOQc3"

# 请求头（列表页）
HEADERS_LIST = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{LIST_URL_TEMPLATE}/sec.html",
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

# 请求头（详情页）
HEADERS_DETAIL = HEADERS_LIST.copy()

# 请求头（验证码）
HEADERS_CAPTCHA = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Authorization": "Bearer 3de949139690d85d287dd91f10a50840",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}

# 请求头（下载）
HEADERS_DOWNLOAD = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": f"multipart/form-data; boundary={DOWNLOAD_BOUNDARY}",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Cookie配置（部分值会过期；sid 需要动态获取）
COOKIES = {
    # demo 里使用 demoClient
    "oauthClientId": "demoClient",
    "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
    "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
    "oauthLogoutUrl": "",
    # 这些 token 可能会变；留空也可以跑列表
    "noOauthRefreshToken": "",
    "noOauthAccessToken": "",
    "_CSRFCOOKIE": "",
    "EPTOKEN": "",
    # sid 必须动态获取（或手工配置）
    "sid": "",
}

# 下载参数（demo 固定）
DOWNLOAD_APP_URL_FLAG = "ztb001"
DOWNLOAD_SITE_GUID = "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a"

PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "list_url_template": LIST_URL_TEMPLATE,
    "api_verification_code_url": API_VERIFICATION_CODE_URL,
    "api_download_url": API_DOWNLOAD_URL,
    "headers_list": HEADERS_LIST,
    "headers_detail": HEADERS_DETAIL,
    "headers_captcha": HEADERS_CAPTCHA,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "download_boundary": DOWNLOAD_BOUNDARY,
    "download_app_url_flag": DOWNLOAD_APP_URL_FLAG,
    "download_site_guid": DOWNLOAD_SITE_GUID,
    "max_pages": 50,
    "page_size": 10,
    "request_interval": 2,
    "captcha_enabled": True,
    "ocr_enabled": True,
    "sid_fallback": "",
    "verification_code_fallback": "",
}

