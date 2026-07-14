#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政采云 exe 下载脚本（独立于系统，每日 19:00 定时执行）

流程：gui_app.exe 获取当日项目编号 → 复制到剪贴板 → 政采云.exe 粘贴批量下载
      → 合并进 tender_files/zcy/total_下载记录.csv

本脚本【只负责下载与累积记录表】，不做入库。系统的爬取/入库（流程执行、定时爬取任务）
另行按数量/时间范围读取 total_下载记录.csv 入库，与本脚本互不干扰。

依赖交互式桌面（坐标点击 GUI），必须在已登录、未锁屏的会话中运行。
阿里云 Windows Server 部署：保持一个 RDP 控制台会话不锁屏（方案二）。

用法：
    python run_zcy_download.py
计划任务（每天 19:00）见文件末尾说明。
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.log import log as logger
from loguru import logger as loguru_logger

# 专门的下载日志文件
_log_file = f'logs/zcy_download_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
loguru_logger.add(sink=_log_file, level="INFO",
                  format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


def main() -> int:
    logger.info("=" * 60)
    logger.info("🕷️ 政采云 exe 下载任务开始（获取编号 → 批量下载 → 合并累积表）")
    logger.info(f"📝 日志文件: {_log_file}")
    logger.info("=" * 60)

    try:
        from spider.zcy_external import run_zcy_download_pipeline

        total_path = run_zcy_download_pipeline()
        logger.info(f"✅ 政采云下载完成，累积记录表: {total_path}")
        return 0
    except Exception as e:
        logger.error(f"❌ 政采云下载任务失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

# ============================================================
# 每日 19:00 定时任务（Windows 计划任务）
# ------------------------------------------------------------
# 在项目根目录用管理员 PowerShell/CMD 执行（一次性）：
#
#   schtasks /Create /TN "ZCY_DailyDownload" /SC DAILY /ST 19:00 /F ^
#     /TR "cmd /c cd /d \"<项目根目录>\" && \"<python.exe>\" run_zcy_download.py"
#
# 例（按实际路径替换）：
#   schtasks /Create /TN "ZCY_DailyDownload" /SC DAILY /ST 19:00 /F ^
#     /TR "cmd /c cd /d \"E:\标书ai匹配系统ByJohnjincaaa\a\" && \"E:\...\python.exe\" run_zcy_download.py"
#
# 说明：
#   - 不要加 /RU SYSTEM 或"不管用户是否登录都运行"——那会跑在无桌面的 Session 0，
#     坐标点击 GUI 会静默失效。必须"只在用户登录时运行"（schtasks 默认即此）。
#   - 运行账户需保持已登录、未锁屏的交互会话（见部署说明/方案二）。
# ============================================================
