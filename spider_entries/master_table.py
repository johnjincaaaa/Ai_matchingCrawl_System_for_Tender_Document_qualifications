#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨城市「采集总表」写入。

每个平台 exe 跑完后，把本次新入库的项目（文件路径、名称、来源等）追加到一张
放在【各城市文件夹的父目录】的 CSV 总表里，方便统一查看所有城市采集到了什么。

为什么放父目录：冻结运行时 config.BASE_DIR = 城市 exe 所在目录，其父目录即
「浙江标书自动采集系统\」根目录；随整个文件夹搬移到别处仍然正确。

为什么用 CSV(utf-8-sig) 而非 xlsx：8 个 exe 可能同时写这张表，CSV 追加更耐并发；
utf-8-sig 让 Excel 双击打开中文不乱码。若总表正被 Excel 打开导致写入被锁，
自动重试，多次失败则退回写一个带时间戳的旁路文件并告警，绝不丢数据。
"""

import os
import csv
import time
from datetime import datetime

# 总表列（顺序即 Excel 里的列顺序）
_FIELDS = [
    "采集时间", "城市", "来源平台", "项目名称", "项目编号",
    "发布时间", "文件名", "文件格式", "本地文件路径", "状态",
    "所属区域", "详情/下载链接",
]

_MASTER_NAME = "采集总表.csv"


def _master_path():
    """总表绝对路径：城市文件夹(BASE_DIR)的父目录 / 采集总表.csv。

    源码运行时 BASE_DIR 是项目目录 a\，父目录也能写，仅用于本地自测。
    """
    from config import BASE_DIR
    parent = os.path.dirname(os.path.abspath(BASE_DIR))
    return os.path.join(parent, _MASTER_NAME)


def _fmt_dt(value):
    if not value:
        return ""
    try:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def _row_from_project(p, city_title):
    """把一条已入库项目(ORM对象或字段dict)转成总表行 dict。"""
    def g(name):
        if isinstance(p, dict):
            return p.get(name)
        return getattr(p, name, None)

    file_path = g("file_path") or ""
    status = g("status")
    status_str = getattr(status, "value", None) or (str(status) if status else "")

    return {
        "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "城市": city_title,
        "来源平台": g("site_name") or "",
        "项目名称": g("project_name") or "",
        "项目编号": g("project_id") or "",
        "发布时间": _fmt_dt(g("publish_time")),
        "文件名": os.path.basename(file_path) if file_path else "",
        "文件格式": g("file_format") or "",
        "本地文件路径": file_path,
        "状态": status_str,
        "所属区域": g("region") or "",
        "详情/下载链接": g("download_url") or "",
    }


def _write_rows(path, rows):
    """把行追加到 CSV；文件不存在则先写表头。返回是否成功。"""
    need_header = not os.path.exists(path) or os.path.getsize(path) == 0
    # newline="" 避免 Windows 下多出空行
    with open(path, "a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        if need_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return True


def append_projects(projects, city_title):
    """把本次新入库项目写入总表。projects 为 ORM 对象或字段 dict 的列表。

    返回 (写入条数, 总表路径)。异常时不抛出（不影响采集主流程），仅打印告警。
    """
    if not projects:
        return 0, _master_path()

    rows = []
    for p in projects:
        try:
            rows.append(_row_from_project(p, city_title))
        except Exception:
            continue
    if not rows:
        return 0, _master_path()

    path = _master_path()
    # 重试应对 Excel 占用 / 多 exe 并发写锁
    last_err = None
    for attempt in range(5):
        try:
            _write_rows(path, rows)
            return len(rows), path
        except PermissionError as e:  # 多为总表被 Excel 打开
            last_err = e
            time.sleep(0.6 * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(0.3 * (attempt + 1))

    # 多次失败：退回旁路文件，保证数据不丢
    try:
        fallback = os.path.join(
            os.path.dirname(path),
            f"采集总表_临时_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        _write_rows(fallback, rows)
        print(f"⚠️ 总表写入失败（{last_err}）。可能总表正被 Excel 打开；"
              f"本次记录已暂存到：{fallback}，关闭总表后可手动合并。")
        return len(rows), fallback
    except Exception as e:
        print(f"⚠️ 总表写入失败且旁路也失败：{e}。本次未记录到总表（不影响已下载的文件）。")
        return 0, path
