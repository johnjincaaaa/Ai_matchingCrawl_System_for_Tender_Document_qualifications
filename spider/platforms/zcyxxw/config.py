"""浙江企业采购信息网（b.zhengcaiyun.cn）配置

爬取范围：采购公告 -> 公开招标公告（categoryCode = ZcyAnnouncement3001）。

注意：该站点接口全部位于阿里云 WAF（acw_sc__v2 JS 挑战）之后。首次请求会返回一个
挑战页（内含 arg1 与一段混淆 JS），需执行该 JS 计算出 acw_sc__v2 cookie 才能拿到
真实 JSON。解算逻辑见 request_handler.solve_waf_cookie（用本机 Node 执行页面 JS）。
"""

PLATFORM_NAME = "浙江企业采购信息网"
PLATFORM_CODE = "zcyxxw"

BASE_URL = "https://b.zhengcaiyun.cn"
API_LIST_URL = f"{BASE_URL}/portal/category"
API_DETAIL_URL = f"{BASE_URL}/portal/detail"

# 采购公告 -> 公开招标公告
LIST_CATEGORY_CODE = "ZcyAnnouncement3001"
# 详情页请求所需的固定 parentId（栏目根）
DETAIL_PARENT_ID = 550016

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

# 列表请求头（POST JSON）
HEADERS_LIST = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/luban/category?parentId={DETAIL_PARENT_ID}&childrenCode=ZcyAnnouncement",
    "User-Agent": USER_AGENT,
}

# 详情页请求头（GET JSON）
HEADERS_DETAIL = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/luban/detail?parentId={DETAIL_PARENT_ID}",
    "User-Agent": USER_AGENT,
}

# 附件下载请求头（OSS 直链，无需鉴权）
HEADERS_DOWNLOAD = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "User-Agent": USER_AGENT,
}

COOKIES = {}

# 爬虫整体配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "api_list_url": API_LIST_URL,
    "api_detail_url": API_DETAIL_URL,
    "list_category_code": LIST_CATEGORY_CODE,
    "detail_parent_id": DETAIL_PARENT_ID,
    "headers_list": HEADERS_LIST,
    "headers_detail": HEADERS_DETAIL,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "max_pages": 50,
    "page_size": 15,
    "request_interval": 2,
}
