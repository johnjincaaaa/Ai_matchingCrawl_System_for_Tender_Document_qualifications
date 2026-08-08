#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""杭州市（中国政府采购网-杭州）独立采集入口。"""
import os
import sys

# 兼容 onefile 冻结运行与源码运行：把项目根目录加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from spider_entries._runner import run_platform

if __name__ == "__main__":
    sys.exit(run_platform("hangzhou", "杭州市"))
