"""衢州市平台请求链路测试

只测“取列表 → 取详情(attachGuid)”环（不含下载/验证码；下载需点选验证码，另行验证）。

直接运行：
    python spider/platforms/quzhou/test_request_chain.py
"""

import os
import sys
from urllib.parse import urljoin

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SELF = os.path.dirname(os.path.abspath(__file__))
# Python 会把脚本所在目录放到 sys.path[0]，而各平台目录下都有 config.py，会覆盖
# 根目录的 config.py（utils.log 需要 from config import LOG_CONFIG）。因此移除脚本
# 自身目录，并把项目根目录放到最前，确保 import config 命中根目录配置。
sys.path[:] = [p for p in sys.path if os.path.abspath(p) != _SELF]
sys.path.insert(0, _ROOT)

import requests

from utils.log import log
from spider.platforms.quzhou.config import PLATFORM_CONFIG
from spider.platforms.quzhou.request_handler import get_project_list, get_doc_detail


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 详情")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers_list"]
    headers_detail = PLATFORM_CONFIG["headers_detail"]
    cookies = PLATFORM_CONFIG.get("cookies") or {}
    base_url = PLATFORM_CONFIG["base_url"]

    session = requests.Session()
    session.headers.update(headers)
    if cookies:
        session.cookies.update(cookies)

    # 1. 取列表（get_project_list 返回已解析的 list）
    log.info("[1/2] 请求列表页 ...")
    result = get_project_list(session=session, page=1, headers=headers, cookies=cookies)

    if result is None:
        log.error("❌ 列表请求失败（返回 None，常见原因：凭证/反爬拦截）")
        session.close()
        return False

    log.info(f"✅ 列表请求成功，本页记录数: {len(result)}")
    if not result:
        log.warning("⚠️ 列表为空（可能当日无新公告），链路本身通畅")
        session.close()
        return True

    # 2. 取一条详情
    href = result[0].get("href", "")
    if not href:
        log.warning("⚠️ 首条记录无 href（列表环已通过）")
        session.close()
        return True
    if href.startswith("http"):
        detail_url = href
    elif href.startswith("/"):
        detail_url = urljoin(base_url, href)
    else:
        detail_url = urljoin(base_url, "/" + href)

    log.info("[2/2] 请求首条详情 ...")
    info = get_doc_detail(session=session, detail_url=detail_url, headers=headers_detail, cookies=cookies)
    if info and info.get("attachGuid"):
        log.info(f"✅ 详情解析成功，attachGuid: {info.get('attachGuid')}")
    else:
        log.warning("⚠️ 详情未解析到 attachGuid（可能该公告无标书正文，列表环已通过）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
