#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""义乌市公共资源电子招标采购平台独立采集入口。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from spider_entries._runner import run_platform

if __name__ == "__main__":
    sys.exit(run_platform("yiwu", "义乌市"))
