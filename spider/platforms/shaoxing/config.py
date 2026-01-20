"""绍兴市阳光采购服务平台配置"""

PLATFORM_NAME = "绍兴市阳光采购服务平台"
PLATFORM_CODE = "shaoxing"

BASE_URL = "https://ygcg.sxjypt.com"
API_LIST_URL = f"{BASE_URL}/siteapi/api/Portal/GetBulletinList"
API_DOWNLOAD_URL = f"{BASE_URL}/fileserver/api/download"

# 列表请求头
HEADERS_LIST = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/home",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# 文件下载请求头
HEADERS_DOWNLOAD = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/home",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

COOKIES = {}

# 默认列表参数
DEFAULT_LIST_PARAMS = {
    "InfoTypeId": "D01",
    "classID": "21",
    "pageIndex": 1,
    "pageSize": 8,
}

# 爬虫整体配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "api_list_url": API_LIST_URL,
    "api_download_url": API_DOWNLOAD_URL,
    "headers_list": HEADERS_LIST,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "default_params": DEFAULT_LIST_PARAMS,
    "max_pages": 50,
    "page_size": 8,
    "request_interval": 2,
}

