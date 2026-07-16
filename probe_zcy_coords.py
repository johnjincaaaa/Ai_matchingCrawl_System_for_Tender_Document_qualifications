#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政采云 exe 坐标探测脚本（跨机器校准用）

用途：打印 exe 窗口内每个控件相对窗口左上角的坐标/尺寸/中心点，
     用于对比本机与服务器坐标是否一致；若不一致，据此更新 config.py 里的
     ZCY_CONFIG['code_exe'] / ['download_exe'] 中的 *_xy 与 ref_size。

用法（先把要探测的 exe 窗口打开）：
    python probe_zcy_coords.py            # 探测两个 exe
    python probe_zcy_coords.py A          # 只探测 EXE A（gui_app.exe 项目编号获取）
    python probe_zcy_coords.py B          # 只探测 EXE B（政采云.exe 批量下载）

输出中每行的 center=(x,y) 就是可直接填进 config 的相对坐标；
size=(宽x高) 是窗口整体尺寸，对应 ref_size。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 保证中文正常输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import win32gui  # noqa: E402

from config import ZCY_CONFIG  # noqa: E402
from spider.zcy_external import (  # noqa: E402
    _find_window,
    _enumerate_all_children,
    _get_control_rect,
    _get_control_text,
)


def probe(tag: str, cfg: dict) -> None:
    title = cfg["window_title"]
    print("=" * 70)
    print(f"[{tag}] 目标窗口标题: {title!r}")
    hwnd = _find_window(title)
    if not hwnd:
        print(f"  ✗ 未找到窗口。请确认 {tag} 已打开。")
        print("  (若标题不符，上方日志会列出所有可见窗口标题，据此更正 config 里的 window_title)")
        return

    # 窗口当前尺寸（对应 ref_size）
    wr = win32gui.GetWindowRect(hwnd)
    w, h = wr[2] - wr[0], wr[3] - wr[1]
    print(f"  ✓ 找到窗口 hwnd={hwnd}")
    print(f"  窗口尺寸(可作 ref_size) = ({w}, {h})   屏幕位置={wr}")
    print(f"  config 里当前 ref_size = {cfg.get('ref_size')}")
    print("  --- 可见控件（center 即可填入 config 的相对坐标）---")

    seen = set()
    items = []
    for ch in _enumerate_all_children(hwnd):
        if ch in seen:
            continue
        seen.add(ch)
        try:
            cls = win32gui.GetClassName(ch)
        except Exception:
            cls = "?"
        r = _get_control_rect(ch)
        if not r or not win32gui.IsWindowVisible(ch):
            continue
        cw, chh = r[2] - r[0], r[3] - r[1]
        rx, ry = r[0] - wr[0], r[1] - wr[1]       # 相对窗口左上角
        cx, cy = rx + cw // 2, ry + chh // 2       # 中心点
        txt = _get_control_text(ch)
        items.append((ry, rx, cx, cy, cw, chh, cls, txt))

    items.sort()
    for ry, rx, cx, cy, cw, chh, cls, txt in items:
        line = f"  center=({cx:4},{cy:4})  rel=({rx:4},{ry:4}) size=({cw:4}x{chh:3}) class={cls:12}"
        if txt:
            line += f" text={txt!r}"
        print(line)


def main() -> int:
    which = sys.argv[1].upper() if len(sys.argv) > 1 else "AB"
    if "A" in which:
        probe("EXE A 项目编号获取", ZCY_CONFIG["code_exe"])
    if "B" in which:
        probe("EXE B 批量下载", ZCY_CONFIG["download_exe"])
    print("=" * 70)
    print("对比方法：把上面的 center=(x,y) 与 config.py 里 ZCY_CONFIG 的 *_xy 对照。")
    print("  - 完全一致 → 无需改动。")
    print("  - 整体等比例偏移 → 多半是 DPI 缩放不同，改 ref_size 或联系我加 DPI 感知。")
    print("  - 个别控件位置不同 → 直接把对应 *_xy 改成这里的 center 值。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
