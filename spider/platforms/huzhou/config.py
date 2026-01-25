"""湖州市招标平台配置"""

PLATFORM_NAME = "湖州市绿色采购服务平台"
PLATFORM_CODE = "huzhou"

BASE_URL = "https://www.hzlscgfw.cn"
# 列表页URL模板：第一页是sec.html，第二页是2.html，以此类推
LIST_URL_TEMPLATE = f"{BASE_URL}/jyxx/001001/001001002/001001002001"
# 详情页URL（从列表页提取）
# 下载相关URL
API_VERIFICATION_CODE_URL = f"{BASE_URL}/EpointWebBuilder/rest/frontAppNotNeedLoginAction/getVerificationCode"
API_DOWNLOAD_URL = f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"

# 请求头（列表页）
HEADERS_LIST = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/jyxx/001001/001001002/001001002001/sec.html",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"'
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
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}

# Cookie配置（需要定期更新，特别是sid）
COOKIES = {
    "HWWAFSESID": "3569e762748b0b1ec8",
    "HWWAFSESTIME": "1768788769793",
    "noOauthRefreshToken": "84980a8a79443c10c253aa16d113ecc5",
    "noOauthAccessToken": "5f6c90f7bf0561293f048da6b2958e4a",
    "oauthClientId": "admin",
    "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
    "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
    "oauthLogoutUrl": "",
    # sid需要从浏览器自动化获取，这里提供一个占位符
    # 实际使用时需要通过浏览器自动化获取或手动配置
    "sid": "",  # 需要动态获取
}

# 平台配置
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
    # 爬取配置
    "max_pages": 50,
    "page_size": 10,  # 每页显示的项目数（从HTML中观察）
    "request_interval": 2,
    # 验证码相关配置
    "captcha_enabled": True,  # 下载文件时需要验证码
    "ocr_enabled": True,  # 是否启用OCR识别验证码（需要安装ddddocr和DrissionPage）
    # 配置说明：
    # 方式1（推荐）：手动配置备用值
    #   - sid_fallback: 通过浏览器访问任意详情页，点击"招标文件正文.pdf"，在浏览器开发者工具中查看Cookie中的sid值
    #   - verification_code_fallback: 可以暂时使用任意4位数字（如"1234"），实际下载时会自动获取新的验证码
    # 方式2：启用自动获取（需要安装依赖）
    #   - 安装: pip install ddddocr DrissionPage
    #   - 设置: ocr_enabled = True
    #   - 系统会自动获取sid和识别验证码
    "sid_fallback": "",  # 备用sid（手动配置，从浏览器Cookie中获取）
    "verification_code_fallback": "",  # 备用验证码（可以暂时使用"1234"等任意值）
}
