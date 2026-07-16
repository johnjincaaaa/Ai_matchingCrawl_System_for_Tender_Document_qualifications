#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政采云 exe 坐标交互式校准脚本（每台机器跑一次）

背景：两个 exe 是 Tkinter 程序，按钮无文字、坐标因机器/字体/DPI 而异。本脚本让你
     把鼠标依次移到各按钮上，自动记录该机的窗口相对坐标，写入 zcy_coords.local.json
     （不进 git）。config.py 启动时会用该文件覆盖默认坐标。换机器只需重跑本脚本。

用法（先把要校准的 exe 窗口打开、完整显示、不要遮挡）：
    python calibrate_zcy.py           # 校准两个 exe
    python calibrate_zcy.py A         # 只校准 EXE A（gui_app.exe 项目编号获取）
    python calibrate_zcy.py B         # 只校准 EXE B（政采云.exe 批量下载）

每一项：把鼠标移到提示的控件中心，保持不动，按回车即记录。
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import win32gui  # noqa: E402
import win32api  # noqa: E402

from config import ZCY_CONFIG, ZCY_COORDS_FILE  # noqa: E402
from spider.zcy_external import _find_window  # noqa: E402


# 每个 exe 需要采集的坐标项：(config键, 中文提示)
TARGETS = {
    "code_exe": [
        ("fetch_button_xy", "「获取当日项目编号」按钮中心"),
        ("copy_button_xy", "「复制全部项目编号」按钮中心"),
    ],
    "download_exe": [
        ("save_dir_xy", "「保存目录」输入框中心"),
        ("codes_xy", "「项目编号」文本框中心（大输入区）"),
        ("start_button_xy", "「开始批量处理」按钮中心"),
    ],
}


def _capture(prompt: str, win_left: int, win_top: int):
    """提示用户把鼠标移到目标上，回车后返回相对窗口左上角的坐标。"""
    input(f"    → 把鼠标移到 {prompt}，保持不动后按回车…")
    x, y = win32api.GetCursorPos()
    rel = (x - win_left, y - win_top)
    print(f"      已记录: 窗口相对坐标 = {rel}  (屏幕={x},{y})")
    return rel


def calibrate_one(exe_key: str, cfg: dict) -> dict:
    title = cfg["window_title"]
    print("=" * 70)
    print(f"[{exe_key}] 窗口: {title!r}")
    hwnd = _find_window(title)
    if not hwnd:
        print(f"  ✗ 未找到窗口，请先打开该 exe（标题需含: {title}）。跳过。")
        return {}

    # 置前并读取窗口位置/尺寸
    try:
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
    except Exception:
        pass
    wr = win32gui.GetWindowRect(hwnd)
    win_left, win_top = wr[0], wr[1]
    ref_size = (wr[2] - wr[0], wr[3] - wr[1])
    print(f"  窗口位置=({win_left},{win_top}) 尺寸(ref_size)={ref_size}")
    print("  请依次把鼠标移到下列控件上（窗口保持当前大小不要改）：")

    section = {"ref_size": list(ref_size)}
    for key, prompt in TARGETS[exe_key]:
        rel = _capture(prompt, win_left, win_top)
        section[key] = list(rel)
    return section


def main() -> int:
    which = sys.argv[1].upper() if len(sys.argv) > 1 else "AB"

    # 读取已有校准，保留未校准的部分
    data = {}
    if os.path.isfile(ZCY_COORDS_FILE):
        try:
            with open(ZCY_COORDS_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {}

    if "A" in which:
        sec = calibrate_one("code_exe", ZCY_CONFIG["code_exe"])
        if sec:
            data["code_exe"] = sec
    if "B" in which:
        sec = calibrate_one("download_exe", ZCY_CONFIG["download_exe"])
        if sec:
            data["download_exe"] = sec

    if not data:
        print("未采集到任何坐标，未写入文件。")
        return 1

    with open(ZCY_COORDS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print("=" * 70)
    print(f"✓ 校准完成，已写入: {ZCY_COORDS_FILE}")
    print("  该文件不进 git，仅本机生效。下次运行下载脚本会自动使用这些坐标。")
    print("  验证坐标：python probe_zcy_coords.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
