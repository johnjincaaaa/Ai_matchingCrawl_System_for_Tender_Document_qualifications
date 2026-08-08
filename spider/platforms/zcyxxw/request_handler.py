"""浙江企业采购信息网（b.zhengcaiyun.cn）请求封装


站点接口位于阿里云 WAF 之后，且每个请求都需前端注入 X-Sign 签名（MD5+隐藏密钥，
藏在深度混淆的 WAF SDK 里）。缺签名的纯 requests 请求会被直接判为异常流量、弹出
阿里云滑块验证，无法绕过。

【方案：浏览器驱动】用 DrissionPage 无头 Chromium 打开站点，让页面自带的签名逻辑
和 WAF 校验全部由真实浏览器完成——列表/详情接口通过页面内的 axios 调用取回 JSON。
附件是 OSS 直链（无鉴权），仍用 requests 直接下载（见 download_file）。

浏览器实例封装在 ZcyBrowser，供 spider 在一次 run() 内复用、结束时 close()。
"""

import os
import re
import json
import time
from typing import Dict, List, Optional

import requests
from utils.log import log
from spider.platforms.zcyxxw.config import (
    BASE_URL,
    LIST_CATEGORY_CODE,
    DETAIL_PARENT_ID,
    HEADERS_DOWNLOAD,
)

# 复用全平台统一的“无附件”哨兵
from spider.base_spider import NO_ATTACHMENT

# SPA 入口页：加载后页面内 axios 已初始化并带 X-Sign 签名拦截器
_ENTRY_URL = f"{BASE_URL}/luban/category?parentId={DETAIL_PARENT_ID}&childrenCode=ZcyAnnouncement"


class ZcyBrowser:
    """DrissionPage 无头浏览器封装：通过页面内已签名的 axios 调用站点接口。

    用法：
        br = ZcyBrowser(); br.open()
        data = br.api_post('/portal/category', {...})
        br.close()
    """

    def __init__(self, headless: bool = False, load_wait: float = 4.0):
        self.headless = headless
        self.load_wait = load_wait
        self.page = None

    def open(self):
        from DrissionPage import ChromiumPage, ChromiumOptions
        co = ChromiumOptions().headless(self.headless)
        for arg in ("--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"):
            co.set_argument(arg)
        self.page = ChromiumPage(co)
        self.page.get(_ENTRY_URL)
        time.sleep(self.load_wait)  # 等 SPA 加载 + 签名拦截器就绪
        log.info("zcyxxw 浏览器已就绪")
        return self

    def _call_once(self, axios_expr: str, timeout: int = 25):
        """执行一次 axios 调用。返回 (status, value)：
        status: 'ok' 数据可用 / 'challenge' 命中WAF滑块 / 'fail' 其它失败 / 'timeout'。
        """
        self.page.run_js(
            "window.__zcy=null;(async()=>{try{const v=await (%s);"
            "window.__zcy=JSON.stringify({ok:1,v:v});}catch(e){"
            "window.__zcy=JSON.stringify({ok:0,e:String(e)});}})();" % axios_expr
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.5)
            r = self.page.run_js("return window.__zcy;")
            if r:
                try:
                    obj = json.loads(r)
                except Exception:
                    return "fail", None
                if obj.get("ok"):
                    return "ok", obj.get("v")
                err = str(obj.get("e") or "")
                # axios 收到 WAF 挑战页(HTML)时通常报解析错/状态异常
                return "fail", err
        return "timeout", None

    def _call(self, axios_expr: str, timeout: int = 25) -> Optional[Dict]:
        """执行 axios 调用；命中滑块则自动滑过后重试。"""
        if not self.page:
            raise RuntimeError("ZcyBrowser 未 open()")
        for attempt in range(3):
            status, val = self._call_once(axios_expr, timeout=timeout)
            if status == "ok":
                return val
            # 失败/超时：可能是命中滑块。检测并尝试自动滑过。
            if self._is_slider_present() or status in ("fail", "timeout"):
                if self._solve_slider():
                    log.info("zcyxxw 滑块验证已通过，重试接口调用")
                    continue
            if status == "fail":
                log.warning(f"zcyxxw 页面接口调用失败：{str(val)[:150]}")
                return None
            log.warning("zcyxxw 页面接口调用超时")
            return None
        return None

    def _is_slider_present(self) -> bool:
        try:
            return bool(self.page.run_js(
                "return !!document.querySelector('#aliyunCaptcha-sliding-slider');"
            ))
        except Exception:
            return False

    def _solve_slider(self, rounds: int = 4) -> bool:
        """检测并拖动阿里云滑块。成功返回 True。

        接口 XHR 被 WAF 拦截时，SPA 会就地渲染滑块（页面 URL 不变），
        因此无需导航，直接定位 #aliyunCaptcha-sliding-slider 拖动即可。

        经实测：一次性 hold→right(大距离)→release 能过，分步缓动轨迹反被风控判失败。
        move_distance 用远超轨道宽的固定值（900）一口气拉到底即可。
        """
        if not self._is_slider_present():
            return False  # 没有滑块，交由上层按普通失败处理
        for rnd in range(rounds):
            if not self._is_slider_present():
                return True  # 已放行
            try:
                time.sleep(0.6)  # 等滑块渲染稳定，避免 element has no location
                slider = self.page.ele("#aliyunCaptcha-sliding-slider")
                # 一次性按住→右移→松开（距离取 900，远超轨道宽，直接拉到底）
                self.page.actions.hold(slider).right(900).release()
                time.sleep(2.0)
                if not self._is_slider_present():
                    return True
                log.warning(f"zcyxxw 滑块第{rnd+1}次未通过，重试")
            except Exception as e:
                log.warning(f"zcyxxw 滑块拖动异常：{str(e)[:120]}")
                time.sleep(1.0)
        return False

    def api_post(self, path: str, body: Dict, timeout: int = 25) -> Optional[Dict]:
        return self._call(
            "window.axios.post(%s,%s)" % (json.dumps(path), json.dumps(body)),
            timeout=timeout,
        )

    def api_get(self, path: str, params: Dict, timeout: int = 25) -> Optional[Dict]:
        return self._call(
            "window.axios.get(%s,{params:%s})" % (json.dumps(path), json.dumps(params)),
            timeout=timeout,
        )

    def close(self):
        try:
            if self.page:
                self.page.quit()
        except Exception:
            pass
        self.page = None


def get_project_list(
    browser: ZcyBrowser,
    page: int = 1,
    page_size: int = 15,
    **_ignored,
) -> Optional[Dict]:
    """获取「公开招标公告」列表。返回 API JSON（含 result.data.data[]），失败返回 None。"""
    body = {
        "pageNo": page,
        "pageSize": page_size,
        "categoryCode": LIST_CATEGORY_CODE,
        "_t": int(time.time() * 1000),
    }
    try:
        return browser.api_post("/portal/category", body)
    except Exception as e:
        log.error(f"zcyxxw 列表请求异常：{str(e)}")
        return None


def get_doc_detail(
    browser: ZcyBrowser,
    article_id: str,
    **_ignored,
) -> Optional[Dict]:
    """获取详情页数据（result.data，含 content 正文与 attachmentVO 附件）。失败返回 None。"""
    params = {
        "articleId": article_id,
        "parentId": DETAIL_PARENT_ID,
        "timestamp": int(time.time() * 1000),
    }
    try:
        data = browser.api_get("/portal/detail", params)
        return (data or {}).get("result", {}).get("data") if data else None
    except Exception as e:
        log.error(f"zcyxxw 详情请求异常：{str(e)}")
        return None


def parse_attachments(detail_data: Dict) -> list:
    """从详情数据解析附件列表，返回 [{"url","name","fileId"}...]。无附件返回 []。"""
    if not detail_data:
        return []
    av = detail_data.get("attachmentVO")
    if not av or not isinstance(av, dict):
        return []
    domain = (av.get("domain") or "").rstrip("/")
    result = []
    for a in (av.get("attachments") or []):
        file_id = a.get("fileId")
        if not file_id:
            continue
        if a.get("isShow") is False:
            continue
        url = f"{domain}/{file_id.lstrip('/')}" if domain else file_id
        result.append({"url": url, "name": a.get("name") or "", "fileId": file_id})
    return result


def download_file(
    url: str,
    save_path: str,
    headers: Optional[Dict] = None,
    timeout: int = 120,
    retry_times: int = 3,
) -> Optional[str]:
    """下载附件（OSS 直链，无需 WAF/鉴权）。返回文件扩展名（不含点），失败返回 None。

    扩展名优先取 URL/fileId 中的后缀，其次 magic bytes 兜底。
    """
    req_headers = headers.copy() if headers else HEADERS_DOWNLOAD.copy()
    # OSS 直链为国内地址，不走系统/科学上网代理（避免本机代理未开时 ProxyError）
    dl_session = requests.Session()
    dl_session.trust_env = False
    for attempt in range(retry_times + 1):
        try:
            resp = dl_session.get(url, headers=req_headers, timeout=timeout, stream=True)
            resp.raise_for_status()
            content = resp.content

            # 1) 从 URL 路径取后缀（fileId 通常自带正确后缀，如 .doc/.docx/.pdf/.xlsx/.zip）
            file_ext = ""
            path = url.split("?", 1)[0].lower()
            m = re.search(r"\.([a-z0-9]{2,5})$", path)
            if m and m.group(1) in ("pdf", "doc", "docx", "xls", "xlsx", "zip", "rar", "ppt", "pptx"):
                file_ext = m.group(1)

            # 2) magic bytes 兜底/校正
            if not file_ext:
                if content[:4] == b"%PDF":
                    file_ext = "pdf"
                elif content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                    file_ext = "doc"  # OLE 复合文档
                elif content[:2] == b"PK":
                    file_ext = "docx" if b"word/" in content[:4000] else "zip"
                elif content[:4] == b"Rar!":
                    file_ext = "rar"
                else:
                    file_ext = "pdf"

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(content)

            size_kb = os.path.getsize(save_path) / 1024
            log.info(f"zcyxxw 文件下载成功：{save_path}（大小：{size_kb:.2f} KB，类型：{file_ext}）")
            return file_ext
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"zcyxxw 文件下载超时/连接失败（第{attempt+1}次），{wait}秒后重试")
                time.sleep(wait)
            else:
                log.error("zcyxxw 文件下载失败，已达最大重试次数")
                return None
        except Exception as e:
            if attempt < retry_times:
                wait = 3 * (attempt + 1)
                log.warning(f"zcyxxw 文件下载异常（第{attempt+1}次），{wait}秒后重试：{str(e)}")
                time.sleep(wait)
            else:
                log.error(f"zcyxxw 文件下载异常，已达最大重试次数：{str(e)}")
                return None
    return None


def extract_body_text(detail_data: Dict) -> Optional[str]:
    """从详情数据的 content（HTML）提取正文纯文本，用于无附件的纯正文公告。"""
    if not detail_data:
        return None
    html = detail_data.get("content")
    if not html:
        return None
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
        return text or None
    except Exception as e:
        log.warning(f"zcyxxw 正文提取失败：{str(e)}")
        return None
