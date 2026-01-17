"""杭州市招标平台配置"""

import random

def generate_random_key():
    """生成jy-random-key（格式：数字-数字-数字-数字）"""
    return f"{random.randint(100, 999)}-{random.randint(1, 9)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

PLATFORM_CONFIG = {
    "name": "杭州市公共资源交易网",
    "code": "hangzhou",
    "base_url": "https://ggzy.hzctc.hangzhou.gov.cn",
    "api_list_url": "https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/list",
    "api_detail_url": "https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/find",
    "api_download_url": "https://ggzy.hzctc.hangzhou.gov.cn/api/file/download",
    
    # 请求头配置
    "headers": {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://ggzy.hzctc.hangzhou.gov.cn/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    
    # Cookie配置（需要定期更新）
    "cookies": {
        "ASP.NET_SessionId": "rixjwgu3jck4hddflnwp01ax",  # 需要定期更新
    },
    
    # 默认请求参数
    "default_params": {
        "size": "10",
        "area": "0",  # 0表示全部区域
        "tradeType": "5",  # 5表示建设工程
        "afficheType": "21",  # 21表示招标公告
    },
    
    # 爬取配置
    "max_pages": 50,
    "page_size": 10,
    "request_interval": 2,
}
