"""湖州市招标平台配置

下载链条基于 HAR 逆向（见 spider/crawl_tests/湖州市/hzlscgfw_downloader.py）：
全程无需 cookie / sid / 浏览器，验证码答案由服务端在 getVerificationCode 里直接回传。
"""

PLATFORM_NAME = "湖州市绿色采购服务平台"
PLATFORM_CODE = "huzhou"

BASE_URL = "https://www.hzlscgfw.cn"
# 采购公告栏目根路径；列表页第一页是 sec.html，其余是 2.html/3.html...
LIST_CHANNEL = "/jyxx/001001/001001002/001001002001"
LIST_URL_TEMPLATE = f"{BASE_URL}{LIST_CHANNEL}"

API_VERIFICATION_CODE_URL = f"{BASE_URL}/EpointWebBuilder/rest/frontAppNotNeedLoginAction/getVerificationCode"
API_DOWNLOAD_URL = f"{BASE_URL}/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"

# 下载请求体的 multipart boundary（HAR 中为空 body，仅需结束分隔符）
DOWNLOAD_BOUNDARY = "----WebKitFormBoundaryZBgd51WalrM7i5YR"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")

# 请求头（列表页 / 详情页）
HEADERS_LIST = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{LIST_URL_TEMPLATE}/sec.html",
    "User-Agent": _UA,
}
HEADERS_DETAIL = HEADERS_LIST.copy()

# 平台配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "list_channel": LIST_CHANNEL,
    "list_url_template": LIST_URL_TEMPLATE,
    "api_verification_code_url": API_VERIFICATION_CODE_URL,
    "api_download_url": API_DOWNLOAD_URL,
    "download_boundary": DOWNLOAD_BOUNDARY,
    "headers_list": HEADERS_LIST,
    "headers_detail": HEADERS_DETAIL,
    # 爬取配置
    "max_pages": 50,
    "page_size": 10,
    "request_interval": 2,
    # 只下载“招标文件正文.pdf”这类正文附件；关键词匹配附件名
    "attach_keyword": "招标文件正文",
    # 验证码走服务端回传答案的捷径；失败时用 ddddocr 兜底重试
    "max_captcha_retries": 3,
}
