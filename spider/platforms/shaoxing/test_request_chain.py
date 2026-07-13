"""绍兴市平台请求链路测试

只测“取公告列表”环（下载直接用 bulletin_id，无独立详情接口；下载环需另行验证）。

直接运行：
    python spider/platforms/shaoxing/test_request_chain.py
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
from spider.platforms.shaoxing.config import PLATFORM_CONFIG
from spider.platforms.shaoxing.request_handler import get_bulletin_list


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：公告列表")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers_list"]
    cookies = PLATFORM_CONFIG.get("cookies") or {}
    default_params = PLATFORM_CONFIG.get("default_params", {})

    session = requests.Session()
    session.headers.update(headers)
    if cookies:
        session.cookies.update(cookies)

    log.info("[1/1] 请求公告列表 ...")
    result = get_bulletin_list(
        session=session,
        page_index=1,
        page_size=PLATFORM_CONFIG.get("page_size", 8),
        info_type_id=default_params.get("InfoTypeId", "D01"),
        class_id=default_params.get("classID", "21"),
        headers=headers,
        cookies=cookies,
    )

    if not result:
        log.error("❌ 列表请求失败或返回为空（常见原因：COOKIES 为空/过期，需运维刷新）")
        session.close()
        return False

    records = ((result.get("body") or {}).get("data") or {}).get("bulletinList") or []
    log.info(f"✅ 列表请求成功，本页记录数: {len(records)}")
    if records:
        first = records[0]
        bid = first.get("bulletinId") or first.get("BulletinId") or first.get("id")
        log.info(f"   首条 bulletinId: {bid}")
    else:
        log.warning("⚠️ 列表为空（可能当日无新公告或凭证无效）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
