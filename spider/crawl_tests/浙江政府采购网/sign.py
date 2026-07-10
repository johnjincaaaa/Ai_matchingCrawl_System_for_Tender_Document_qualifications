"""政采云 zcygov.cn 接口 X-Sign 纯 Python 实现"""

import hashlib
import time
from urllib.parse import unquote


CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
SIGN_SALT = "zcy@148946"


def decode_url_path(path: str) -> str:
    """对应 JS _0x198416：trim + '+' 转空格 + decodeURIComponent"""
    if not path:
        return ""
    text = path.strip().replace("+", " ")
    try:
        return unquote(text)
    except Exception:
        return text


def gen_nonce(seed: int) -> str:
    """对应 JS _0x2cd9a4：LCG 伪随机生成 16 位 nonce"""
    nonce = ""
    state = seed
    for _ in range(16):
        state = (0x2455 * state + 0xC091) % 0x38F40
        nonce += CHARSET[int(state / 0x38F40 * len(CHARSET))]
    return nonce


def build_sign_string(
    method: str,
    path: str,
    body: str,
    timestamp_ms: int,
    nonce: str,
    uid: str,
    sign_salt: str = SIGN_SALT,
) -> str:
    """对应 JS _0x403680：6 行用 \\n 拼接"""
    body_part = "" if method.upper() == "GET" else (body or "")
    return "\n".join([
        method.upper(),
        decode_url_path(path),
        body_part,
        str(timestamp_ms),
        nonce,
        f"{sign_salt}:{uid}",
    ])


def md5_hex(text: str) -> str:
    """对应 JS _0x483bcf + _0x4e5bc8：UTF-8 MD5 后转 hex"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def generate_sign_headers(
    method: str,
    path: str,
    *,
    body: str = "",
    uid: str = "10008527321",
    sign_salt: str = SIGN_SALT,
    timestamp_ms: int | None = None,
    url_timestamp_sec: int | None = None,
    nonce: str | None = None,
) -> dict:
    """
    生成 X-Nonce / X-Timestamp / X-Sign 三个请求头。

    path 必须与实际请求的 path+query 完全一致，例如：
    /api/biz-tender/tender-center/acquirePurFile/precisionSearch?timestamp=1783234881&projectNameOrProjectCode=330106261010010000011

    注意 URL 查询参数 timestamp 为秒级（10 位），请求头 X-Timestamp 为毫秒级（13 位）。
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if url_timestamp_sec is None:
        url_timestamp_sec = timestamp_ms // 1000
    if nonce is None:
        nonce = gen_nonce(timestamp_ms)

    sign_str = build_sign_string(method, path, body, timestamp_ms, nonce, uid, sign_salt)
    return {
        "X-Nonce": nonce,
        "X-Timestamp": str(timestamp_ms),
        "X-Sign": md5_hex(sign_str),
        "X-Sign-Version": "v1",
        "_url_timestamp_sec": url_timestamp_sec,
        "_sign_string": sign_str,
    }
