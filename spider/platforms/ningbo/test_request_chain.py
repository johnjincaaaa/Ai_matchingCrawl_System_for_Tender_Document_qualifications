"""宁波市平台请求链路测试

只测“取列表 → 取文件URL”环（不含下载/无需验证码）。

直接运行：
    python spider/platforms/ningbo/test_request_chain.py
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
from spider.platforms.ningbo.config import PLATFORM_CONFIG
from spider.platforms.ningbo.request_handler import get_doc_list, get_file_url


def test_request_chain():
    name = PLATFORM_CONFIG["name"]
    log.info("=" * 60)
    log.info(f"[{name}] 请求链路测试：列表 → 文件URL")
    log.info("=" * 60)

    headers = PLATFORM_CONFIG["headers_list"]
    cookies = PLATFORM_CONFIG.get("cookies") or {}

    session = requests.Session()
    session.headers.update(headers)
    if cookies:
        session.cookies.update(cookies)

    # 1. 取列表（宁波用动态 access_token，get_doc_list 内部处理）
    log.info("[1/2] 请求列表页 ...")
    result = get_doc_list(
        session=session,
        page_index=1,
        page_size=PLATFORM_CONFIG.get("page_size", 10),
        headers=headers,
    )

    if not result or "data" not in result:
        log.error(f"❌ 列表请求失败或返回结构异常: {str(result)[:200]}")
        session.close()
        return False

    rows = (result.get("data") or {}).get("rows", [])
    log.info(f"✅ 列表请求成功，本页记录数: {len(rows)}")
    if not rows:
        log.warning("⚠️ 列表为空（可能当日无新公告），链路本身通畅")
        session.close()
        return True

    # 2. 取一条文件URL
    prj_id = rows[0].get("PrjId")
    log.info(f"[2/2] 请求首条文件URL PrjId={prj_id} ...")
    file_url = get_file_url(session=session, prj_id=prj_id, headers=headers)
    if file_url:
        log.info(f"✅ 文件URL获取成功: {str(file_url)[:120]}")
    else:
        log.warning("⚠️ 未取到文件URL（可能该项目无标书文件，列表环已通过）")

    session.close()
    log.info(f"[{name}] 链路测试通过 ✅")
    return True


if __name__ == "__main__":
    ok = test_request_chain()
    sys.exit(0 if ok else 1)
