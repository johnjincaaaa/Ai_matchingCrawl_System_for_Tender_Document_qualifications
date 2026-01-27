"""义乌市阳光招标采购平台配置"""

PLATFORM_NAME = "义乌市阳光招标采购平台"
PLATFORM_CODE = "yiwu"

BASE_URL = "https://www.ywygzc.com"
API_LIST_URL = f"{BASE_URL}/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"

# 列表请求头
HEADERS_LIST = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/jyxx/002001/second_page.html",
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
HEADERS_DETAIL = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/jyxx/002001/second_page.html",
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

# 下载请求头
HEADERS_DOWNLOAD = HEADERS_DETAIL.copy()

COOKIES = {}

# 默认列表参数
DEFAULT_LIST_PARAMS = {
    "token": "",
    "pn": 0,  # 页数，第一页为0，第二页为10，第三页为20，以此类推
    "rn": 10,  # 每页数量
    "sdt": "",
    "edt": "",
    "wd": "",
    "inc_wd": "",
    "exc_wd": "",
    "fields": "title;infoa",
    "cnum": "077",
    "sort": '{"ordernum":0,"webdate":0}',
    "ssort": "title",
    "cl": 500,
    "terminal": "",
    "condition": [
        {
            "equal": "002001",
            "fieldName": "categorynum",
            "isLike": "true",
            "likeType": "2"
        }
    ],
    "time": None,
    "highlights": "content",
    "statistics": None,
    "unionCondition": None,
    "accuracy": "",
    "noParticiple": "",
    "searchRange": None,
    "isBusiness": "1"
}

# 爬虫整体配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "api_list_url": API_LIST_URL,
    "headers_list": HEADERS_LIST,
    "headers_detail": HEADERS_DETAIL,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "default_params": DEFAULT_LIST_PARAMS,
    "max_pages": 50,
    "page_size": 10,  # 每页显示的项目数
    "request_interval": 2,
}
