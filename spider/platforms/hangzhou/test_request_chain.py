"""杭州市平台请求链路测试

只测“取列表 → 取详情”环（不含下载/无需验证码），用于快速判断：
    配置加载 / 网络连通 / 鉴权 Cookie / 接口返回结构 / 解析是否正常。

直接运行：
    python spider/platforms/hangzhou/test_request_chain.py
或作为模块：
    python -m spider.platforms.hangzhou.test_request_chain
"""

import os
import sys

# 允许直接以脚本方式运行（把项目根目录加入 sys.path）
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SELF = os.path.dirname(os.path.abspath(__file__))
# Python 会把脚本所在目录放到 sys.path[0]，而各平台目录下都有 config.py，会覆盖
# 根目录的 config.py（utils.log 需要 from config import LOG_CONFIG）。因此移除脚本
# 自身目录，并把项目根目录放到最前，确保 import config 命中根目录配置。
sys.path[:] = [p for p in sys.path if os.path.abspath(p) != _SELF]
sys.path.insert(0, _ROOT)

import requests

from utils.log import log
from spider.platforms.hangzhou.config import PLATFORM_CONFIG
from spider.platforms.hangzhou.request_handler import get_doc_list, get_doc_detail


def test_request_chain():
    """列表环为主，能拿到项目就顺带测一条详情。返回 True/False。"""
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 详情")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers"]
    cookies = PLATFORM_CONFIG["cookies"]
    default_params = PLATFORM_CONFIG.get("default_params", {})

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    # 1. 取列表
    log.info("[1/2] 请求列表页 ...")
    result = get_doc_list(
        session=session,
        current=1,
        size=PLATFORM_CONFIG.get("page_size", 10),
        area=default_params.get("area", 0),
        tradeType=default_params.get("tradeType", 5),
        afficheType=default_params.get("afficheType", 21),
        headers=headers,
        cookies=cookies,
    )

    if not result or result.get("code") != 200:
        log.error(f"❌ 列表请求失败或返回非200: {str(result)[:200]}")
        session.close()
        return False

    records = (result.get("data") or {}).get("records", [])
    log.info(f"✅ 列表请求成功，本页记录数: {len(records)}")
    if not records:
        log.warning("⚠️ 列表为空（可能是当日无新公告或筛选参数所致），链路本身通畅")
        session.close()
        return True

    # 2. 取一条详情
    doc_id = records[0].get("id")
    log.info(f"[2/2] 请求首条详情 id={doc_id} ...")
    detail = get_doc_detail(session=session, doc_id=doc_id, headers=headers, cookies=cookies)
    if detail and detail.get("code") == 200:
        file_list = (detail.get("data") or {}).get("list", [])
        log.info(f"✅ 详情请求成功，附件数: {len(file_list)}")
    else:
        log.warning(f"⚠️ 详情请求未返回200（列表环已通过）: {str(detail)[:200]}")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
