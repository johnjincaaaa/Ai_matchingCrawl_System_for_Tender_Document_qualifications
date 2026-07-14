"""湖州市平台请求链路测试

测“取列表 → 取详情(附件列表)”环。基于 HAR 逆向的纯 requests 实现，无需 cookie/sid/浏览器。

直接运行：
    python spider/platforms/huzhou/test_request_chain.py
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
from spider.platforms.huzhou.config import PLATFORM_CONFIG
from spider.platforms.huzhou.request_handler import get_doc_list, get_doc_detail


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 详情")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers_list"]

    session = requests.Session()
    session.headers.update(headers)

    # 1. 取列表
    log.info("[1/2] 请求列表页 ...")
    items = get_doc_list(session=session, page=1, headers=headers)

    if items is None:
        log.error("❌ 列表请求失败（网络异常/重试耗尽）")
        session.close()
        return False

    log.info(f"✅ 列表请求成功，本页记录数: {len(items)}")
    if not items:
        log.warning("⚠️ 列表为空（可能当日无新公告），链路本身通畅")
        session.close()
        return True

    # 2. 取一条详情（解析附件列表：attach_guid 完整 A@B + site_guid）
    detail_url = items[0].get("url")
    log.info("[2/2] 请求首条详情 ...")
    attachments = get_doc_detail(session=session, detail_url=detail_url, headers=headers)
    if attachments:
        log.info(f"✅ 详情解析成功，附件数: {len(attachments)}")
        for a in attachments[:3]:
            log.info(f"    - {a['name']}  attachGuid={a['attach_guid'][:40]}... siteGuid={a['site_guid'][:12]}...")
    else:
        log.warning("⚠️ 详情未解析到附件（可能该公告无附件，列表环已通过）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
