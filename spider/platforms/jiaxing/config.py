"""嘉兴市招标平台配置"""

PLATFORM_CONFIG = {
    "name": "嘉兴禾采联综合采购服务平台",
    "code": "jiaxing",
    "base_url": "https://hcl.jxcqgs.cn",
    "api_list_url": "https://hcl.jxcqgs.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew",
    "api_detail_url": "https://hcl.jxcqgs.cn",
    "api_captcha_url": "https://hcl.jxcqgs.cn/EpointWebBuilder/rest/shellcaptcha/initAndCheckCaptcha",
    "api_download_url": "https://hcl.jxcqgs.cn/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action",
    
    # 请求头配置（列表页）
    "headers_list": {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://hcl.jxcqgs.cn",
        "Pragma": "no-cache",
        "Referer": "https://hcl.jxcqgs.cn/jyxx/001001/001001003/trade.html",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    
    # 请求头配置（详情页）
    "headers_detail": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://hcl.jxcqgs.cn/jyxx/001001/001001003/trade.html",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    
    # Cookie配置（需要定期更新）
    "cookies": {
        "userGuid": "777375320",
        "oauthClientId": "wzds",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "6bc3742e938397f6942afa30f1416428",
        "noOauthAccessToken": "2e14d7582cfc33b3198100d441ee2859",
        "arialoadData": "false",
    },
    
    # 爬取配置
    "max_pages": 100,
    "page_size": 10,
    "request_interval": 2,
    
    # 列表查询参数（固定值）
    "list_params_template": {
        "token": "",
        "sdt": "",
        "edt": "",
        "wd": "",
        "inc_wd": "",
        "exc_wd": "",
        "fields": "titlenew",
        "cnum": "005",
        "sort": '{"webdate":"0"}',
        "ssort": "title",
        "cl": 200,
        "terminal": "",
        "condition": [{"fieldName": "bidmethodcode", "isLike": True, "likeType": 2, "equal": "公"}],
        "time": [],
        "highlights": "",
        "statistics": None,
        "unionCondition": [
            {"fieldName": "categorynum", "isLike": True, "likeType": 2, "equal": "001001002001"},
            {"fieldName": "categorynum", "isLike": True, "likeType": 2, "equal": "001002002001"}
        ],
        "accuracy": "",
        "noParticiple": "1",
        "searchRange": None,
        "isBusiness": "1",
    },
    
    # 验证码相关配置（需要时使用）
    "captcha_enabled": True,  # 下载文件时需要验证码
    "validate_code_fallback": "blockpuzzle@1323af89-d52d-4962-ada2-5f68a79ec31e@fcbdc4b5-a72e-4491-b0f3-1095a19c5d36",  # 备用验证码（如果验证码获取失败）
}

# 导出配置
PLATFORM_NAME = PLATFORM_CONFIG["name"]
PLATFORM_CODE = PLATFORM_CONFIG["code"]
BASE_URL = PLATFORM_CONFIG["base_url"]
API_LIST_URL = PLATFORM_CONFIG["api_list_url"]
API_DETAIL_URL = PLATFORM_CONFIG["api_detail_url"]
API_CAPTCHA_URL = PLATFORM_CONFIG["api_captcha_url"]
API_DOWNLOAD_URL = PLATFORM_CONFIG["api_download_url"]
HEADERS_LIST = PLATFORM_CONFIG["headers_list"]
HEADERS_DETAIL = PLATFORM_CONFIG["headers_detail"]
COOKIES = PLATFORM_CONFIG["cookies"]
