"""丽水市平台请求链路测试

只测“取列表 → 取详情(attachGuid)”环（不含下载；下载需 sid+验证码）。

丽水站点有 TLS 指纹反爬：request_handler.create_session() 优先用 curl_cffi
(impersonate=chrome) 建会话；未安装 curl_cffi 时回退标准 requests，可能被拦截。

直接运行：
    python spider/platforms/lishui/test_request_chain.py
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

from utils.log import log
from spider.platforms.lishui.config import PLATFORM_CONFIG
from spider.platforms.lishui.request_handler import (
    create_session,
    get_doc_list,
    get_doc_detail,
    CURL_CFFI_AVAILABLE,
)


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 详情")
    log.info("=" * 60)

    if PLATFORM_CONFIG.get("use_curl_cffi") and not CURL_CFFI_AVAILABLE:
        log.warning("⚠️ 配置启用了 curl_cffi 但未安装，将回退标准 requests，可能被 TLS 指纹反爬拦截")

    headers = PLATFORM_CONFIG["headers_list"]
    cookies = PLATFORM_CONFIG["cookies"]

    session = create_session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    # 1. 取列表
    log.info("[1/2] 请求列表页 ...")
    items = get_doc_list(session=session, page=1, headers=headers, cookies=cookies)

    if items is None:
        log.error("❌ 列表请求失败（网络异常/反爬拦截/重试耗尽）")
        session.close()
        return False

    log.info(f"✅ 列表请求成功，本页记录数: {len(items)}")
    if not items:
        log.warning("⚠️ 列表为空（可能当日无新公告），链路本身通畅")
        session.close()
        return True

    # 2. 取一条详情（提取 attachGuid）
    detail_url = items[0].get("url")
    log.info("[2/2] 请求首条详情 ...")
    attach_guid = get_doc_detail(session=session, detail_url=detail_url, headers=headers, cookies=cookies)
    if attach_guid:
        log.info(f"✅ 详情解析成功，attachGuid: {attach_guid}")
    else:
        log.warning("⚠️ 详情未解析到 attachGuid（可能该公告无招标文件正文.pdf，列表环已通过）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
