#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丽水市阳光采购服务平台独立采集入口。

注意：本平台下载环节需自动获取 sid（DrissionPage 驱动本机 Chrome）+ OCR 验证码，
终端机需安装 Google Chrome。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from spider_entries._runner import run_platform

if __name__ == "__main__":
    sys.exit(run_platform("lishui", "丽水市"))
