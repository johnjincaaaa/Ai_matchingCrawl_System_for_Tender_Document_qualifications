#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单平台采集入口的公共逻辑（被各 run_<平台>.py 复用）。

只做三件事：爬取列表 → 下载标书文件 → 入库去重。不含 AI 分析 / 文件解析 / 报告。
打包成 onefile exe 后，数据库、tender_files/、logs/ 会落在 exe 所在目录（见 config.py
的 frozen 分支），每个平台 exe 各自独立一份。
"""

import sys
import os
import io
import argparse


def _force_utf8_console():
    """Windows 控制台默认 GBK，中文日志会乱码/报错。尽量切到 UTF-8。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
            elif stream and hasattr(stream, "buffer"):
                setattr(sys, stream_name,
                        io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))
        except Exception:
            pass


def run_platform(platform_code: str, platform_title: str, default_limit: int = 100):
    """运行指定平台的爬虫。返回进程退出码（0 成功，1 异常）。"""
    _force_utf8_console()

    parser = argparse.ArgumentParser(
        description=f"{platform_title} 标书采集（仅爬取+下载，不做AI分析）")
    parser.add_argument("--limit", type=int, default=default_limit,
                        help=f"本次最多采集数量（默认 {default_limit}）")
    parser.add_argument("--days", type=int, default=1,
                        help="采集最近 N 天内的公告（默认 1=仅当天；如 7=最近7天）")
    parser.add_argument("--no-pause", action="store_true",
                        help="结束后不暂停（用于定时任务/无人值守）")
    args, _unknown = parser.parse_known_args()

    days_before = args.days if args.days and args.days > 0 else None

    print("=" * 60)
    print(f"  {platform_title}  标书采集程序")
    print(f"  采集数量上限: {args.limit}    时间范围: "
          f"{'最近 %d 天' % args.days if days_before else '仅当天'}")
    print("=" * 60)
    sys.stdout.flush()

    exit_code = 0
    try:
        # 延迟导入：确保 config 的 frozen 路径分支、日志已就绪后再拉起 spider
        from spider import SpiderManager
        from utils.log import log
        from utils.db import get_db, TenderProject
        from sqlalchemy import func

        # 记录采集前的最大 id，用于事后精确圈出「本次新入库」的项目。
        # 不直接用 spider.run() 的返回值：宁波/丽水等会在 run() 末尾 close 掉 db，
        # 其 ORM 对象在 session 关闭后可能失效，无法安全读字段。
        db0 = next(get_db())
        try:
            max_id_before = db0.query(func.max(TenderProject.id)).scalar() or 0
        finally:
            db0.close()

        spider = SpiderManager.create_spider(
            platform_code, daily_limit=args.limit, days_before=days_before)
        projects = spider.run()
        count = len(projects) if projects else 0

        try:
            from config import BASE_DIR
            out_dir = os.path.join(BASE_DIR, "tender_files", platform_code)
        except Exception:
            out_dir = "(见 tender_files 目录)"

        print("-" * 60)
        print(f"✅ 采集完成：本次入库 {count} 个项目。")
        print(f"📁 标书文件目录：{out_dir}")

        # 用新 session 查出本次新增项目，写入跨城市「采集总表」
        try:
            from spider_entries.master_table import append_projects
            db1 = next(get_db())
            try:
                new_projects = (
                    db1.query(TenderProject)
                    .filter(TenderProject.id > max_id_before)
                    .order_by(TenderProject.id.asc())
                    .all()
                )
                written, master_path = append_projects(new_projects, platform_title)
            finally:
                db1.close()
            if written:
                print(f"📊 已记录 {written} 条到采集总表：{master_path}")
        except Exception as e:
            print(f"⚠️ 写入采集总表时出错（不影响已下载文件）：{e}")

        print("-" * 60)
        log.info(f"[{platform_code}] 独立采集完成，入库 {count} 个项目")
    except KeyboardInterrupt:
        print("\n⚠️ 已被用户中断。")
        exit_code = 1
    except Exception as e:
        import traceback
        print("-" * 60)
        print(f"❌ 采集失败：{e}")
        traceback.print_exc()
        print("-" * 60)
        exit_code = 1

    if not args.no_pause:
        try:
            input("\n按回车键关闭窗口...")
        except Exception:
            pass
    return exit_code
