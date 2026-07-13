"""嘉兴市平台请求链路测试

只测“取列表 → 取详情(attachGuid)”环（不含下载/无需验证码），用于快速判断：
    配置加载 / 网络连通 / 鉴权 Cookie / 接口返回结构 / 解析是否正常。

直接运行：
    python spider/platforms/jiaxing/test_request_chain.py
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SELF = os.path.dirname(os.path.abspath(__file__))
# Python 会把脚本所在目录放到 sys.path[0]，而各平台目录下都有 config.py，会覆盖
# 根目录的 config.py（utils.log 需要 from config import LOG_CONFIG）。因此移除脚本
# 自身目录，并把项目根目录放到最前，确保 import config 命中根目录配置。
sys.path[:] = [p for p in sys.path if os.path.abspath(p) != _SELF]
sys.path.insert(0, _ROOT)

import requests

from utils.log import log
from spider.platforms.jiaxing.config import PLATFORM_CONFIG
from spider.platforms.jiaxing.request_handler import get_doc_list, get_doc_detail


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 详情")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers_list"]
    cookies = PLATFORM_CONFIG["cookies"]

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    # 1. 取列表
    log.info("[1/2] 请求列表页 ...")
    result = get_doc_list(
        session=session,
        page=0,
        page_size=PLATFORM_CONFIG.get("page_size", 10),
        headers=headers,
        cookies=cookies,
    )

    if not result or "result" not in result:
        log.error(f"❌ 列表请求失败或返回结构异常: {str(result)[:200]}")
        session.close()
        return False

    records = (result.get("result") or {}).get("records", [])
    log.info(f"✅ 列表请求成功，本页记录数: {len(records)}")
    if not records:
        log.warning("⚠️ 列表为空（可能当日无新公告），链路本身通畅")
        session.close()
        return True

    # 2. 取一条详情（提取 attachGuid）
    first = records[0]
    link_url = first.get("linkurl", "")
    if not link_url:
        log.warning("⚠️ 首条记录无 linkurl 字段（列表环已通过）")
        session.close()
        return True
    base_url = PLATFORM_CONFIG["base_url"]
    detail_url = link_url if link_url.startswith("http") else base_url + link_url

    log.info(f"[2/2] 请求首条详情 ...")
    attach_guid = get_doc_detail(session=session, detail_url=detail_url, headers=headers, cookies=cookies)
    if attach_guid:
        log.info(f"✅ 详情解析成功，attachGuid: {attach_guid}")
    else:
        log.warning("⚠️ 详情未解析到 attachGuid（可能该公告无标书正文，列表环已通过）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
